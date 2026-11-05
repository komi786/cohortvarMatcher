# KG quality checks (SHACL)

Checks the cohort metadata knowledge graphs (`data/graphs/<study>_metadata.trig`)
for metadata and data inconsistencies. The checks only report; they never change
the graph or the dictionaries. The report is meant for the data owners.

```bash
python analysis/kg_quality/validate_kg.py            # all studies, ~1 min
python analysis/kg_quality/validate_kg.py --pyshacl  # standard pyshacl run (slow), same results
```

Output in `data/output/kg_quality/`: `<study>_kg_quality.csv`, `kg_quality_report.csv`
(all studies), `kg_quality_summary.csv` (counts per study, check, severity).

## Checks (`kg_quality_shapes.ttl`)

| Check | Severity | Rule |
|---|---|---|
| Q00 legacy term | Violation | the variable and its nodes use CMEO release IRIs, not the made-up ones of graphs built before the 2026-11-04 migration |
| Q01 identifier | Violation | variable has a name |
| Q02 label | Warning | variable has a label |
| Q03 data type | Violation | exactly one data type |
| Q04 statistical type | Violation | exactly one statistical type |
| Q05 concept | Warning | at least one standard concept |
| Q06 domain | Warning | has an OMOP domain |
| Q10 measurement without unit | Warning | continuous numeric Measurement has a unit (counts, scores and ratios legitimately have none) |
| Q11 unit not standardised | Warning | unit label maps to a UCUM unit (date/time variables excluded) |
| Q12 category count | Violation | binary = 2 categories, multi-class ≥ 2 |
| Q13 category without concept | Info | each category maps to a concept |
| Q14 categorical with unit | Warning | binary/multi-class variables carry no unit |
| Q15 text with unit | Warning | `str` variables carry no unit |
| Q20 missing code as bound | Violation | a declared missing code is not the min or max |
| Q21 int with decimals | Violation | `int` variables have whole-number min/max |
| Q22 text with numeric data | Violation | `str` variables have no numeric distribution in the data |
| Q23 numeric with text data | Violation | numeric variables profiled by the EDA have a numeric distribution |
| Q24 percent as fraction | Warning | `%` variables do not hold only values in [0, 1] |
| Q25 fraction above one | Warning | `L/L` / fraction variables do not exceed 1 |
| Q26 min above max | Violation | min ≤ max |
| Q27 more values than categories | Violation | distinct values ≤ categories + missing codes (+1 for empty) |
| Q28 categories not observed | Info | every declared category occurs in the data |

Min, max, median and unique counts in the graph come from the EDA where it has
them, so Q20–Q28 test what the matcher actually sees.

Terms are the CMEO release IRIs (`obo:CMEO_0000009` data element, `obo:STATO_0000129`
has value, …), the same table as `src/utils.py`; the header of the shapes file lists
the ones used. The five count statistics share `STATO_0000047` (count), so the
unique-value count is selected by its label, "number of unique values". The runner
stops if a graph has no node of a shape's target class: on a graph built with the
old IRIs every shape would otherwise pass silently.

## Why the runner does not just call pyshacl

pyshacl runs each SPARQL constraint once per variable on rdflib, which takes
many minutes per study. By default the runner uses pyshacl only for the core
shapes (Q01–Q06) and runs each SPARQL constraint once over the whole graph in
Oxigraph (`pyoxigraph`), with `$this` restricted to the target class. A SPARQL
constraint reports one result per solution per focus node, so the results are
the same; `--pyshacl` runs the standard validation to confirm it. On a whole study
that takes hours; it was checked on a 20-variable extract of Aachen (8 results,
identical in both runners).

Shapes compare literals with `STR(...)`: the graph stores values as
`xsd:string`, which Oxigraph treats as equal to plain strings (RDF 1.1) but
rdflib does not.

## Not covered yet

- Dictionary MIN/MAX vs EDA min/max: the graph holds one value.
- Observed category values: the EDA class balance is not stored in the graph.
- Concept-specific accepted units and plausible ranges: needs a reference table
  per LOINC/SNOMED (OMOP) concept, e.g. the OHDSI Data Quality Dashboard thresholds.
