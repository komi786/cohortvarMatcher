"""Validate the cohort metadata knowledge graphs against kg_quality_shapes.ttl.

Usage (from the repository root):
    python analysis/kg_quality/validate_kg.py
    python analysis/kg_quality/validate_kg.py --graphs data/graphs --out data/output/kg_quality
    python analysis/kg_quality/validate_kg.py --pyshacl     # full pyshacl run (slow)

The shapes file is plain SHACL and works with any SHACL engine. pyshacl runs
every SPARQL constraint once per focus node on rdflib, which takes many
minutes per study (rdflib picks poor join orders for these patterns). By
default this script therefore runs the core (non-SPARQL) shapes with pyshacl
and evaluates each SPARQL constraint once over the whole graph in Oxigraph,
with $this free and bound to the shape's target class. That gives the same
results: a SPARQL constraint reports one result per solution for each focus
node. --pyshacl runs the standard validation instead, to check that claim.

Writes one CSV per study plus kg_quality_report.csv (all studies) and
kg_quality_summary.csv (results per study, check and severity). The graphs
are read only.
"""
import argparse
import glob
import os
import re
import time

import pandas as pd
import pyoxigraph as ox
from pyshacl import validate
from rdflib import Dataset, Graph, Namespace, RDF, RDFS, URIRef
from rdflib.namespace import DC

SH = Namespace("http://www.w3.org/ns/shacl#")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))


def load_graph(path: str) -> Graph:
    """Merge all named graphs of a .trig file into one graph."""
    ds = Dataset()
    ds.parse(path, format="trig")
    g = Graph()
    for s, p, o, _ in ds.quads((None, None, None, None)):
        g.add((s, p, o))
    return g


def _short(node) -> str:
    return str(node).split("#")[-1] if node is not None else ""


def _row(study: str, data: Graph, focus, check: str, severity, message: str, value) -> dict:
    return {
        "study": study,
        "variable": str(data.value(focus, DC.identifier) or ""),
        "label": str(data.value(focus, RDFS.label) or ""),
        "check": check,
        "severity": _short(severity),
        "message": message,
        "value": "" if value is None else str(value),
        "focus_node": str(focus),
    }


def pyshacl_rows(study: str, data: Graph, shapes: Graph) -> list[dict]:
    _, results, _ = validate(data, shacl_graph=shapes, inference="none",
                             allow_warnings=True, allow_infos=True)
    if not isinstance(results, Graph):  # pyshacl returns an error object if the shapes are invalid
        raise RuntimeError(str(results))
    rows = []
    for res in results.subjects(RDF.type, SH.ValidationResult):
        shape = results.value(res, SH.sourceShape)
        # Property shapes and SPARQL constraints are blank nodes; report the node shape that owns them.
        if shape is not None and (shape, RDF.type, SH.NodeShape) not in shapes:
            owner = shapes.value(predicate=SH.property, object=shape)
            shape = owner if owner is not None else shape
        rows.append(_row(study, data, results.value(res, SH.focusNode), _short(shape),
                         results.value(res, SH.resultSeverity),
                         str(results.value(res, SH.resultMessage) or ""), results.value(res, SH.value)))
    return rows


def sparql_prefixes(shapes: Graph, constraint) -> str:
    out = []
    for ont in shapes.objects(constraint, SH.prefixes):
        for decl in shapes.objects(ont, SH.declare):
            out.append(f"PREFIX {shapes.value(decl, SH.prefix)}: <{shapes.value(decl, SH.namespace)}>")
    return "\n".join(out)


def bound_query(select: str, target_class: URIRef) -> str:
    """$this -> ?this, and restrict ?this to the target class right after WHERE {."""
    q = select.replace("$this", "?this")
    return re.sub(r"WHERE\s*\{", f"WHERE {{ ?this a <{target_class}> .", q, count=1)


def fill_message(template: str, row) -> str:
    return re.sub(r"\{\?(\w+)\}", lambda m: str(row.get(m.group(1), "")), template)


def sparql_rows(study: str, data: Graph, store: "ox.Store", shapes: Graph) -> list[dict]:
    rows = []
    for shape in shapes.subjects(RDF.type, SH.NodeShape):
        target = shapes.value(shape, SH.targetClass)
        severity = shapes.value(shape, SH.severity) or SH.Violation
        for constraint in shapes.objects(shape, SH.sparql):
            query = sparql_prefixes(shapes, constraint) + "\n" + bound_query(
                str(shapes.value(constraint, SH.select)), target)
            template = str(shapes.value(constraint, SH.message) or "")
            solutions = store.query(query, use_default_graph_as_union=True)
            names = [v.value for v in solutions.variables]
            for sol in solutions:
                b = {n: (sol[n].value if sol[n] is not None else None) for n in names}
                # Without a ?value, SHACL engines report the focus node as the value (pyshacl does).
                rows.append(_row(study, data, URIRef(b["this"]), _short(shape), severity,
                                 fill_message(template, b), b.get("value") or b["this"]))
    return rows


def core_only(shapes: Graph) -> Graph:
    """The shapes graph without SPARQL constraints (those run in sparql_rows)."""
    g = Graph()
    for t in shapes:
        g.add(t)
    for shape, constraint in list(shapes.subject_objects(SH.sparql)):
        g.remove((shape, None, None))
    return g


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--graphs", default=os.path.join(ROOT, "data", "graphs"))
    ap.add_argument("--shapes", default=os.path.join(HERE, "kg_quality_shapes.ttl"))
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "output", "kg_quality"))
    ap.add_argument("--pyshacl", action="store_true", help="run the full pyshacl validation (slow)")
    args = ap.parse_args()

    shapes = Graph().parse(args.shapes, format="turtle")
    core = core_only(shapes)
    os.makedirs(args.out, exist_ok=True)

    all_rows = []
    for path in sorted(glob.glob(os.path.join(args.graphs, "*_metadata.trig"))):
        study = os.path.basename(path).replace("_metadata.trig", "")
        if study == "studies":  # study-level graph, no variables
            continue
        t0 = time.time()
        data = load_graph(path)
        # A shape with no focus nodes passes silently, e.g. on a graph built before the
        # CMEO IRI migration (variables typed cmeo:data_element instead of CMEO_0000009).
        targets = set(shapes.objects(None, SH.targetClass))
        if not any(data.value(predicate=RDF.type, object=t) is not None for t in targets):
            raise SystemExit(f"{study}: no node of a shape target class {sorted(map(str, targets))}; "
                             "was the graph built with the current code?")
        if args.pyshacl:
            rows = pyshacl_rows(study, data, shapes)
        else:
            store = ox.Store()
            store.load(path=path, format=ox.RdfFormat.TRIG)
            rows = pyshacl_rows(study, data, core) + sparql_rows(study, data, store, shapes)
        pd.DataFrame(rows).to_csv(os.path.join(args.out, f"{study}_kg_quality.csv"), index=False)
        all_rows.extend(rows)
        print(f"{study}: {len(rows)} results ({time.time() - t0:.0f}s)")

    report = pd.DataFrame(all_rows)
    report.to_csv(os.path.join(args.out, "kg_quality_report.csv"), index=False)
    if not report.empty:
        summary = report.groupby(["study", "check", "severity"]).size().rename("n").reset_index()
        summary.to_csv(os.path.join(args.out, "kg_quality_summary.csv"), index=False)
        print(summary.pivot_table(index="check", columns="study", values="n", fill_value=0, aggfunc="sum"))


if __name__ == "__main__":
    main()
