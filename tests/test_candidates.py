"""Candidate generation: bugs #5 (relation per pair) and #6 (per-variable search).

#5  The mapping relation was stored once per concept key and taken from
    whichever pair reached the key first, so two targets with the same
    label but different graph relations shared one relation.
#6  One vector search ran per main OMOP id, built from the group's first
    variable only; every other variable with that main id inherited its
    hits. A hit was then paired with every target variable sharing the hit's
    main id, so the target's own additional concepts were ignored too.

The graph, the vector store and the embedding model are replaced by small
stand-ins, so these tests need no Qdrant server and no OMOP graph.

Run from the repository root:  python -m unittest tests.test_candidates
"""
import logging
import unittest
from unittest import mock

import numpy as np

logging.getLogger("cohortvarlinker.llm_matcher").addHandler(logging.NullHandler())
logging.getLogger("cohortvarlinker.llm_logs").addHandler(logging.NullHandler())

from src import neuro_matcher, vector_db  # noqa: E402
from src.data_model import MappingRelation, MappingType, VariableCollection, VariableNode  # noqa: E402

EXACT = MappingRelation.SymbolicExactMatch.value
BROAD = MappingRelation.SymbolicBroadMatch.value
NARROW = MappingRelation.SymbolicNarrowMatch.value
NEURAL = MappingRelation.NeuralMatch.value

ADVERSE_EVENT = 4085220


def var(name, main_id, main_label, description, context=(), visit="baseline"):
    return VariableNode(name=name, main_id=main_id, main_label=main_label, description=description,
                        context_ids=[c for c, _ in context], context_labels=[l for _, l in context],
                        visit=visit)


class FakeGraph:
    def __init__(self, edges):
        self.edges = edges          # {source_id: [(target_id, relation), ...]}

    def source_to_targets_paths(self, sid, others, max_depth=3):
        return [(t, r) for t, r in self.edges.get(sid, []) if t in others]


class FakeEmbed:
    model_name = "fake-embedder"

    def embed_batch(self, texts, is_query=True):
        return [np.zeros(3) for _ in texts]


class FakeSearch:
    """Stands in for search_in_db: hits are chosen by a keyword in the query."""

    def __init__(self, rules):
        self.rules = rules          # [(keyword, [hit, ...]), ...]
        self.queries = []

    def __call__(self, vectordb, embedding_model, query_text, with_names=False, **kw):
        self.queries.append(query_text)
        for keyword, hits in self.rules:
            if keyword in query_text.lower():
                return [h if with_names else h[:2] for h in hits]
        return []


def run(src_vars, tgt_vars, *, graph=None, search=None, mode=MappingType.OEH.value):
    m = neuro_matcher.NeuroSymbolicMatcher(
        vector_db=object() if search else None, embed_model=FakeEmbed() if search else None,
        graph=graph, mapping_mode=mode)
    src = VariableCollection(study="source", variables=src_vars)
    tgt = VariableCollection(study="target", variables=tgt_vars)
    with mock.patch.object(neuro_matcher, "search_in_db", search or FakeSearch([])):
        rows = m.generate_candidates(src, tgt, "target")
    return {(r["source"], r["target"]): r["mapping_relation"] for r in rows}, rows


class RelationPerPair(unittest.TestCase):
    """Bug #5."""

    def test_same_label_targets_keep_their_own_relation(self):
        # Two target variables carry the same concept label (so the same
        # concept key) under different OMOP ids; the graph links one as an
        # exact match and the other as a broader concept.
        src = [var("hf_hosp", 1, "hospitalization for heart failure", "HF hospitalisation")]
        tgt = [var("hosp_a", 10, "hospitalization", "hospital admission"),
               var("hosp_b", 20, "hospitalization", "any hospitalisation")]
        graph = FakeGraph({1: [(10, EXACT), (20, BROAD)]})
        pairs, _ = run(src, tgt, graph=graph)
        self.assertEqual(pairs[("hf_hosp", "hosp_a")], EXACT)
        self.assertEqual(pairs[("hf_hosp", "hosp_b")], BROAD)

    def test_pair_reached_twice_is_emitted_once_with_strongest_relation(self):
        src = [var("s", 1, "x", "x")]
        tgt = [var("t", 10, "y", "y")]
        graph = FakeGraph({1: [(10, BROAD), (10, EXACT), (10, NARROW)]})
        pairs, rows = run(src, tgt, graph=graph)
        self.assertEqual(len(rows), 1)
        self.assertEqual(pairs[("s", "t")], EXACT)


class SearchPerVariable(unittest.TestCase):
    """Bug #6."""

    def setUp(self):
        self.src = [
            var("ae_anemia", ADVERSE_EVENT, "adverse event", "anemia adverse event", [(1, "anemia")]),
            var("ae_bleeding", ADVERSE_EVENT, "adverse event", "bleeding adverse event", [(2, "bleeding")]),
        ]
        # Target uses a different main concept, so only the vector route reaches it.
        self.tgt = [
            var("t_anemia", 900, "complication", "complication: anemia", [(1, "anemia")]),
            var("t_bleeding", 900, "complication", "complication: bleeding", [(2, "bleeding")]),
            var("t_gout", 900, "complication", "complication: gout", [(3, "gout")]),
        ]
        self.search = FakeSearch([
            ("anemia", [(900, 0.91, ("t_anemia",))]),
            ("bleeding", [(900, 0.88, ("t_bleeding",))]),
        ])

    def test_each_variable_gets_its_own_hits(self):
        pairs, _ = run(self.src, self.tgt, search=self.search)
        self.assertEqual(set(pairs), {("ae_anemia", "t_anemia"), ("ae_bleeding", "t_bleeding")})
        self.assertTrue(all(r == NEURAL for r in pairs.values()))

    def test_each_query_carries_the_variables_own_description_and_concepts(self):
        run(self.src, self.tgt, search=self.search)
        self.assertEqual(len(self.search.queries), 2)
        self.assertTrue(any("anemia" in q and "bleeding" not in q for q in self.search.queries))
        self.assertTrue(any("bleeding" in q and "anemia" not in q for q in self.search.queries))

    def test_same_description_and_concepts_are_searched_once(self):
        # Same variable at three visits: one query, every visit paired.
        src = [var(f"sbp_{v}", 3004249, "systolic blood pressure", "systolic blood pressure",
                   visit=v) for v in ("baseline", "month 6", "month 12")]
        tgt = [var(f"sys_{v}", 77, "arterial pressure", "systolic BP", visit=v)
               for v in ("baseline", "month 6", "month 12")]
        search = FakeSearch([("systolic", [(77, 0.9, tuple(t.name for t in tgt))])])
        pairs, _ = run(src, tgt, search=search)
        self.assertEqual(len(search.queries), 1)
        self.assertEqual(set(pairs), {(f"sbp_{v}", f"sys_{v}") for v in ("baseline", "month 6", "month 12")})

    def test_hit_names_missing_from_current_dictionary_fall_back_to_main_id(self):
        # An index built from an older dictionary may name variables that no
        # longer exist; the hit then pairs with every target sharing its id.
        search = FakeSearch([("anemia", [(900, 0.91, ("renamed_variable",))])])
        pairs, _ = run(self.src[:1], self.tgt, search=search)
        self.assertEqual(set(pairs), {("ae_anemia", t.name) for t in self.tgt})

    def test_graph_route_still_pairs_every_member(self):
        tgt = [var("t_ae", ADVERSE_EVENT, "adverse event", "adverse event", [(1, "anemia")])]
        pairs, _ = run(self.src, tgt, graph=FakeGraph({}), search=self.search)
        self.assertEqual(pairs, {("ae_anemia", "t_ae"): EXACT, ("ae_bleeding", "t_ae"): EXACT})

    def test_neural_hit_already_found_by_graph_keeps_graph_relation(self):
        graph = FakeGraph({ADVERSE_EVENT: [(900, BROAD)]})
        pairs, _ = run(self.src, self.tgt, graph=graph, search=self.search)
        self.assertEqual(len(pairs), 6)
        self.assertTrue(all(r == BROAD for r in pairs.values()))


class SearchInDbNames(unittest.TestCase):
    """search_in_db(with_names=True) keeps each hit's own target variables."""

    class Hit:
        def __init__(self, score, omop, names):
            self.score = score
            self.payload = {"variable_omop_id": omop, "variable_name": names.split("|")[0],
                            "variable_names": names}

    def search(self, hits, **kw):
        db = mock.Mock()
        db.search.return_value = hits
        emb = mock.Mock(model_name="fake-search")
        emb.embed_text.return_value = [0.0, 0.0, 0.0]
        return vector_db.search_in_db(db, emb, "query text", min_threshold=0.1, **kw)

    def test_default_output_unchanged(self):
        hits = [self.Hit(0.90, 900, "t_anemia"), self.Hit(0.89, 900, "t_bleeding")]
        self.assertEqual(self.search(hits), [(900, 0.9)])

    def test_with_names_returns_each_point(self):
        hits = [self.Hit(0.90, 900, "t_anemia|t_anemia_m6"), self.Hit(0.89, 900, "t_bleeding")]
        self.assertEqual(self.search(hits, with_names=True),
                         [(900, 0.9, ("t_anemia", "t_anemia_m6")), (900, 0.89, ("t_bleeding",))])


if __name__ == "__main__":
    unittest.main()
