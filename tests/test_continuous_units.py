"""ContinuousHandler unit logic, end to end through compute_structural and decide().

Unit pairs are taken from the TIME-CHF evaluation outputs.
Run from the repository root:  python -m unittest tests.test_continuous_units
"""
import math
import unittest
from types import SimpleNamespace
from unittest import mock

from src import constraints
from src.constraints import compute_structural
from src.data_model import (ContextMatchType, MappingType, MatchLevel, Statistics,
                            StatisticalType, TransformationType, VariableNode)
from src.policy import decide
from src.verdict import LLMEvidence, TimepointInfo

NO_LLM = SimpleNamespace(llm_matcher=None)
WITH_LLM = SimpleNamespace(llm_matcher=object())
EXACT = ContextMatchType.EXACT.value
PENDING = ContextMatchType.PENDING.value
TP = TimepointInfo(aligned=True, status="aligned")


def node(name, unit, unit_id=None, ctx=EXACT, lo=None, hi=None):
    return VariableNode(name=name, description=name, unit=unit, unit_concept_id=unit_id,
                        statistical_type=StatisticalType.CONTINUOUS.value,
                        statistics=Statistics(min_val=lo, max_val=hi),
                        context_match_type=ctx, visit="baseline")


class FakeOmopGraph:
    """The UCUM concepts of graph_nx.pkl.gz that these tests use."""
    CODES = {9444: "10*9/L", 8848: "10*3/uL", 8636: "g/L", 8713: "g/dL", 8645: "[U]/L"}

    def get_node_attr(self, nid, attr):
        if nid not in self.CODES:
            return ""
        return {"vocabulary": "ucum", "concept_code": self.CODES[nid]}.get(attr, "")


WITH_GRAPH = SimpleNamespace(llm_matcher=None, graph=FakeOmopGraph())


def structural(src_unit, tgt_unit, *, src_id=None, tgt_id=None, ctx=EXACT, matcher=NO_LLM,
               mode=MappingType.OEH.value):
    return compute_structural(node("src", src_unit, src_id, ctx), node("tgt", tgt_unit, tgt_id, ctx),
                              mapping_mode=mode, matcher=matcher)


class WithoutLLM(unittest.TestCase):
    """Structural verdict is final (OO, or OEH without an LLM)."""

    def test_scalable_is_compatible_with_factor(self):
        s = structural("ucum:g/L", "ucum:g/dL", src_id=8636, tgt_id=8713)   # hemoglobin
        self.assertEqual(s.level, MatchLevel.COMPATIBLE)
        self.assertEqual(s.transformation, TransformationType.UNIT_CONVERSION)
        self.assertEqual(s.ceiling, MatchLevel.COMPATIBLE)
        self.assertTrue(math.isclose(s.extra["unit_factor"], 0.1, rel_tol=1e-9))
        self.assertIn("multiply source values by 0.1", s.extra["transformation_rule"])

    def test_equivalent_spelling_is_identical(self):
        s = structural("ucum:ng/mL", "ucum:ug/L", src_id=8842, tgt_id=8748)  # ferritin
        self.assertEqual(s.level, MatchLevel.IDENTICAL)
        self.assertEqual(s.transformation, TransformationType.NONE)
        self.assertEqual(s.extra["unit_relation"], "equivalent")
        self.assertIsNone(s.ceiling)

    def test_dose_percent_vs_mg_is_partial(self):
        s = structural("ucum:%", "ucum:mg")
        self.assertEqual(s.level, MatchLevel.PARTIAL)
        self.assertEqual(s.ceiling, MatchLevel.PARTIAL)
        self.assertIn("target dose", s.reason)

    def test_molar_mass_dependent_is_compatible(self):
        s = structural("ucum:mmol/L", "ucum:mg/dL")                       # LDL
        self.assertEqual(s.level, MatchLevel.COMPATIBLE)
        self.assertEqual(s.transformation, TransformationType.UNIT_CONVERSION)
        self.assertEqual(s.ceiling, MatchLevel.COMPATIBLE)
        # 0.1 x 386.65 g/mol = 38.665, the textbook LDL factor.
        self.assertIn("by 0.1 x the analyte's molar mass", s.extra["transformation_rule"])

    def test_calendar_variables_are_not_unit_converted(self):
        # Year of MI diagnosis (datetime, ucum:a) vs month of MI (int, ucum:mo):
        # calendar parts, not durations of 12x each other.
        src = VariableNode(name="src", unit="ucum:a", statistical_type=StatisticalType.CONTINUOUS.value,
                           context_match_type=EXACT, visit="baseline", data_type="datetime")
        tgt = node("tgt", "ucum:mo")
        s = compute_structural(src, tgt, mapping_mode=MappingType.OEH.value, matcher=NO_LLM)
        self.assertEqual(s.level, MatchLevel.PARTIAL)
        self.assertIsNone(s.ceiling)
        self.assertNotIn("unit_factor", s.extra)
        # Not compared, so not labelled "equivalent" either.
        self.assertNotIn("unit_relation", s.extra)

    def test_indexed_vs_absolute_volume_is_partial(self):
        s = structural("ucum:ml/m2", "ucum:mL")                            # LVEDV index vs LVEDV
        self.assertEqual(s.level, MatchLevel.PARTIAL)
        self.assertEqual(s.extra["unit_relation"], "incommensurable")

    def test_unparseable_unit_has_no_ceiling(self):
        s = structural("DD-MM-YYYY", "ucum:mg")
        self.assertEqual(s.level, MatchLevel.PARTIAL)
        self.assertIsNone(s.ceiling)


class UnitConceptCodes(unittest.TestCase):
    """The OMOP unit concept, not the (possibly lower-cased) label, is read."""

    def compare(self, a, b):
        return compute_structural(a, b, mapping_mode=MappingType.OEH.value, matcher=WITH_GRAPH)

    def test_lowercased_giga_per_litre(self):
        # Article run: Vienna leukozyten "g/l" (concept 9444, 10*9/L) vs
        # TIME-CHF Lc "10^3/ul" (8848, 10*3/uL): the same count.
        s = self.compare(node("lc", "10^3/ul", 8848), node("leukozyten", "g/l", 9444))
        self.assertEqual(s.level, MatchLevel.IDENTICAL)
        self.assertEqual(s.extra["target_unit_code"], "ucum:10*9/L")

    def test_lowercased_gram_per_litre(self):
        # Vienna albumin "g/l" is concept 8636, gram per litre.
        s = self.compare(node("alb", "g/l", 8636), node("alb", "g/dl", 8713))
        self.assertEqual(s.level, MatchLevel.COMPATIBLE)
        self.assertTrue(math.isclose(s.extra["unit_factor"], 0.1, rel_tol=1e-9))

    def test_without_concept_the_label_is_used(self):
        s = self.compare(node("x", "ucum:g/L", None), node("y", "ucum:g/dL", None))
        self.assertEqual(s.level, MatchLevel.COMPATIBLE)
        self.assertNotIn("source_unit_code", s.extra)


class ValueRanges(unittest.TestCase):
    """Recorded min/max must fit the factor the units claim."""

    def hb_pair(self):
        # Article run: TIME-CHF Hb "g/dl" 75-178 vs GISSI-HF EMOGLOB g/dl 5-19.9.
        return compute_structural(node("Hb", "g/dl", 8713, lo=75, hi=178),
                                  node("EMOGLOB", "g/dl", 8713, lo=5, hi=19.9),
                                  mapping_mode=MappingType.OEH.value, matcher=NO_LLM)

    def test_range_conflict_is_reported_not_enforced_by_default(self):
        # The ground truth followed the dictionary labels, so by default the
        # verdict does too; the conflict travels in the output for review.
        s = self.hb_pair()
        self.assertEqual(s.level, MatchLevel.IDENTICAL)
        self.assertIsNone(s.ceiling)
        self.assertEqual(s.extra["unit_range_check"], "contradicted")
        self.assertIn("probable unit annotation error", s.extra["unit_range_note"])

    def test_range_conflict_caps_verdict_when_enabled(self):
        with mock.patch.object(constraints, "RANGE_CONFLICT_CAPS_VERDICT", True):
            s = self.hb_pair()
        self.assertEqual(s.level, MatchLevel.PARTIAL)
        self.assertEqual(s.ceiling, MatchLevel.PARTIAL)
        self.assertIn("probable unit annotation error", s.reason)
        # Even an LLM "complete" cannot merge them as-is.
        v = decide(MappingType.OEH.value, s, LLMEvidence("COMPLETE", 0.9), True, TP)
        self.assertEqual(v.level, MatchLevel.PARTIAL)
        self.assertIn("unit/value-range conflict", v.description)

    def test_correct_units_and_ranges_confirmed(self):
        s = compute_structural(node("Hb", "ucum:g/L", 8636, lo=75, hi=178),
                               node("EMOGLOB", "ucum:g/dL", 8713, lo=5, hi=19.9),
                               mapping_mode=MappingType.OEH.value, matcher=NO_LLM)
        self.assertEqual(s.level, MatchLevel.COMPATIBLE)
        self.assertEqual(s.extra["unit_range_check"], "confirmed")

    def test_missing_ranges_keep_the_factor_unverified(self):
        s = structural("ucum:g/L", "ucum:g/dL")
        self.assertEqual(s.level, MatchLevel.COMPATIBLE)
        self.assertEqual(s.extra["unit_range_check"], "unverified")


class WithLLM(unittest.TestCase):
    """Pending context defers meaning to the LLM; units still bound the result."""

    def test_same_units_pending_reason(self):
        # PENDING == 0 used to be read as "no context" and fell through to
        # "cannot verify equivalence".
        s = structural("ucum:mg/dL", "ucum:mg/dL", src_id=8840, tgt_id=8840,
                       ctx=PENDING, matcher=WITH_LLM)
        self.assertEqual(s.level, MatchLevel.PARTIAL)
        self.assertIn("Same units", s.reason)
        self.assertTrue(s.needs_review)

    def test_scalable_pending_then_llm_complete_is_compatible(self):
        s = structural("ucum:g/dL", "ucum:g/L", ctx=PENDING, matcher=WITH_LLM)
        self.assertEqual(s.level, MatchLevel.PARTIAL)
        self.assertTrue(s.needs_review)
        v = decide(MappingType.OEH.value, s, LLMEvidence("COMPLETE", 0.9, transform="x10"), True, TP)
        self.assertEqual(v.level, MatchLevel.COMPATIBLE)
        self.assertEqual(v.transformation, TransformationType.UNIT_CONVERSION)
        self.assertIn("multiply source values by 10", v.extra["transformation_rule"])

    def test_equivalent_units_pending_then_llm_complete_is_identical(self):
        s = structural("ucum:10*3/uL", "ucum:/nL", ctx=PENDING, matcher=WITH_LLM)  # leukocytes
        v = decide(MappingType.OEH.value, s, LLMEvidence("COMPLETE", 0.9), True, TP)
        self.assertEqual(v.level, MatchLevel.IDENTICAL)
        self.assertEqual(v.transformation, TransformationType.NONE)

    def test_dose_llm_compatible_capped_at_partial(self):
        s = structural("ucum:%", "ucum:mg", ctx=PENDING, matcher=WITH_LLM)
        v = decide(MappingType.OEH.value, s, LLMEvidence("COMPATIBLE", 0.9), True, TP)
        self.assertEqual(v.level, MatchLevel.PARTIAL)
        self.assertIn("Capped at Partial Match", v.description)


if __name__ == "__main__":
    unittest.main()
