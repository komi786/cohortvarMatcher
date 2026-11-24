"""Generate the Results tables and the residual-error figure of the article from
evaluator outputs (evaluate_cross_study.run_full_evaluation on the frozen article
snapshot), so every reported number traces back to one evaluation run.

Inputs (read-only):
  --eval-dir  evaluator output folder, e.g.
              data/output/cross_mapping/evaluation_article_rerun/eval_article_corrected_gt
  --gt        ground-truth workbook used for that run
  --dicts     data dictionaries used for the article runs: the
              cross_mapping_used_in_article.zip archive or its extracted folder
              (only the top-level <Study>/*.csv files are read)
Outputs (--out): one booktabs tabular per table (*.tex, for \\input inside the
paper's table environment), the figure (PNG + PDF), the counts behind the figure
(CSV) and summary.txt with the derived numbers quoted in the text.

Configurations: retrievers x LLM classifiers as in the paper; deepseek-v4-pro is not
reported. Ablation modes: G = OO, E / E+L = NE, G+E / G+E+L = OEH; withheld symbolic
evidence = the *_ng runs.

Table 8 strata (defined on the benchmark pair, using the article dictionaries):
  abbreviation label  the target label is an abbreviation only (one token, no
                      expansion, each '-'/'/' part has >=2 capitals or a digit or
                      <=2 characters, e.g. ASAT, HbA1c, NT-proBNP, IL-6), or the
                      target variable has no label
  cross-vocabulary    vocabulary prefix of the variable concept codes differs
                      (case-insensitive; ATC vs RxNorm counts)
  study-specific code variable concept code from a non-standard, study-specific
                      scheme (icare, ukbiobank) on either side
Pairs not recovered at candidate generation are scored as not applicable by the
evaluator and therefore count as errors here.

usage: python analysis/paper_results.py --eval-dir <dir> --gt <xlsx> --dicts <zip|dir> --out <dir>
       [--snapshot <cross_mapping_article_output>]
"""
from __future__ import annotations

import argparse
import io
import re
import unicodedata
import zipfile
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import numpy as np
import pandas as pd

RETRIEVERS = {"biolord": "BioLORD", "openai": "text-embedding-3-large", "sapbert": "SapBERT"}
LLMS = {"gemini-3.1-flash-lite": "Gemini-3.1-Flash-Lite", "gpt-oss-120b": "GPT-OSS-120B",
        "deepseek-v4-flash": "DeepSeek-V4-Flash"}
TARGETS = {"aachen-hf": "Aachen-HF", "gissi-hf": "GISSI-HF",
           "viennahf-register": "ViennaHF-Reg.", "biostat-chf": "BIOSTAT-CHF"}
STUDY_DIRS = {"time-chf": "TIME-CHF", "aachen-hf": "Aachen-HF", "gissi-hf": "GISSI-HF",
              "viennahf-register": "ViennaHF-Register", "biostat-chf": "BIOSTAT-CHF"}
DOMAINS = [("condition_occurrence", "Conditions/diagnosis"), ("drug_exposure", "Medication exposure"),
           ("measurement", "Laboratory and physiological measurements"),
           ("observation", "Clinical observation"), ("person", "Demographic"),
           ("procedure_occurrence", "Procedures"), ("death", "Mortality/outcome")]
STUDY_SPECIFIC = {"icare", "ukbiobank"}
SOURCE = "time-chf"
HEADLINE = "biolord+gemini-3.1-flash-lite"           # configuration of Table 8
SERIES_COLORS = ["#2a78d6", "#eb6834", "#1baf7a"]    # categorical slots 1-3, validated


def pct(x: float) -> str:
    """Fraction (4-dp evaluator value) -> percent with one decimal, half-up."""
    # round(.., 6) only removes float noise (0.9065*100 = 90.64999...); a coarser
    # pre-rounding would double-round exact values (95.945 -> 95.95 -> 96.0)
    return str(Decimal(str(round(float(x) * 100, 6))).quantize(Decimal("0.1"), ROUND_HALF_UP))


def pp(a: float, b: float) -> str:
    """Percentage-point difference a - b of two fractions, taken from the DISPLAYED
    (one-decimal) values so every difference can be checked against the tables."""
    v = Decimal(pct(a)) - Decimal(pct(b))
    return str(v.copy_abs() if v == 0 else v)


def norm_var(x) -> str:
    """Variable-name key as written by the evaluator (lower case, no accents, '.'/space/'-' -> '_')."""
    x = unicodedata.normalize("NFKD", str(x)).encode("ascii", "ignore").decode()
    return re.sub(r"[.\s-]+", "_", x.strip().lower())


def combo(ret: str, llm: str) -> str:
    return f"{ret}+{llm}"


def tabular(colspec: str, header: list[str], rows: list[list[str] | str]) -> str:
    out = [f"\\begin{{tabular}}{{{colspec}}}", "\\toprule", " & ".join(header) + " \\\\", "\\midrule"]
    for r in rows:
        out.append(r if isinstance(r, str) else " & ".join(r) + " \\\\")
    out += ["\\bottomrule", "\\end{tabular}", ""]
    return "\n".join(out)


def bold_max(values: list[float], fmt=pct) -> list[str]:
    best = max(float(fmt(v)) for v in values)
    return [f"\\textbf{{{fmt(v)}}}" if float(fmt(v)) == best else fmt(v) for v in values]


# --------------------------------------------------------------------------- loading
def load_eval(eval_dir: Path):
    coll = pd.read_csv(eval_dir / "collective_evaluation_summary.csv")
    master = pd.read_csv(eval_dir / "master_evaluation_summary.csv")
    for df in (coll, master):
        df["model"] = df["model"].fillna("N/A")
    dom = pd.read_csv(eval_dir / "pooled_domain_metrics.csv")
    dom["model"] = dom["model"].fillna("N/A")
    errors = pd.read_csv(eval_dir / "all_incorrect_predictions.csv")
    return coll, master, dom, errors


def load_dictionaries(path: Path) -> dict[str, pd.DataFrame]:
    out = {}
    for study, folder in STUDY_DIRS.items():
        if path.suffix == ".zip":
            with zipfile.ZipFile(path) as z:
                names = [n for n in z.namelist()
                         if re.fullmatch(rf"[^/]+/{re.escape(folder)}/[^/]+\.csv", n)]
                if len(names) != 1:
                    raise ValueError(f"{folder}: expected one top-level csv, found {names}")
                df = pd.read_csv(io.BytesIO(z.read(names[0])))
        else:
            names = sorted((path / folder).glob("*.csv"))
            if len(names) != 1:
                raise ValueError(f"{folder}: expected one top-level csv, found {names}")
            df = pd.read_csv(names[0])
        df.columns = [c.strip().lower() for c in df.columns]
        out[study] = df
    return out


def lookup(dicts: dict[str, pd.DataFrame], study: str, var: str):
    d = dicts[study]
    names = d["variablename"].astype(str)
    hit = d[names == str(var)]
    if hit.empty:
        hit = d[names.str.lower() == str(var).lower()]
    return hit.iloc[0] if len(hit) else None


def mean_of_targets(coll, model, mode):
    r = coll[(coll.model == model) & (coll["mode"] == mode)]
    if len(r) != 1:
        raise KeyError(f"{model} / {mode}: {len(r)} rows")
    return r.iloc[0]


# --------------------------------------------------------------------------- tables
def table_ablation(coll, summary):
    llm_combos = [combo(r, l) for r in RETRIEVERS for l in LLMS]
    noll = [combo(r, "no_llm") for r in RETRIEVERS]

    def best(models, mode):
        sub = coll[coll.model.isin(models) & (coll["mode"] == mode)]
        top = sub.f1_macro.max()
        return top, sorted(sub[sub.f1_macro == top].model)

    full, full_m = best(llm_combos, "OEH")
    rows_def = [("G+E+L (full)", full, full_m), ("G+E",) + best(noll, "OEH"),
                ("E+L",) + best(llm_combos, "NE"), ("E",) + best(noll, "NE"),
                ("G (baseline)", float(coll[coll["mode"] == "OO"].f1_macro.max()), ["graph only"])]
    rows = [[name, pct(v), "---" if i == 0 else f"$-{pp(full, v)}$"]
            for i, (name, v, _) in enumerate(rows_def)]
    el = coll[coll.model.isin(llm_combos) & (coll["mode"] == "NE")].f1_macro
    summary += ["== Table ablation_best"]
    summary += [f"  {n}: {v:.4f} ({', '.join(m)})" for n, v, m in rows_def]
    g = rows_def[4][1]
    summary += [f"  E+L range {pct(el.min())}-{pct(el.max())}; E+L best - G = {pp(rows_def[2][1], g)} pp; "
                f"G+E best - G = {pp(rows_def[1][1], g)} pp; full - best two-component = "
                f"{pp(full, max(rows_def[1][1], rows_def[2][1]))} pp"]
    return tabular("lcc", ["\\textbf{Ablation setting}", "$\\mathbf{F_{1,m}}$", "$\\mathbf{\\Delta}$"], rows)


def table_candidate_recall(master, summary):
    modes = [("\\texttt{G}", "N/A", "OO"), ("\\texttt{E}", "biolord+no_llm", "NE"),
             ("\\texttt{G+E}", "biolord+no_llm", "OEH")]
    rows, tot = [], {m[0]: [0, 0] for m in modes}
    for t, name in TARGETS.items():
        for i, (label, model, mode) in enumerate(modes):
            r = master[(master.model == model) & (master["mode"] == mode) & (master.target_study == t)].iloc[0]
            na, miss = int(r.predicted_not_in_gt), int(r.positive_gt_not_retrieved)
            tot[label][0] += na
            tot[label][1] += miss
            first = f"\\multirow{{3}}{{*}}{{{name}}}" if i == 0 else ""
            rows.append([first, label, str(na), str(miss)])
        rows.append("\\midrule")
    for i, (label, _, _) in enumerate(modes):
        first = "\\multirow{3}{*}{\\textbf{Overall}}" if i == 0 else ""
        rows.append([first, label, f"\\textbf{{{tot[label][0]}}}", f"\\textbf{{{tot[label][1]}}}"])
    summary += ["== Table candidate_recall (BioLORD)"] + \
               [f"  {k}: non-annotated {v[0]}, missed {v[1]}" for k, v in tot.items()]
    return tabular("llrr", ["\\textbf{Target cohort}", "\\textbf{Retrieval mode}",
                            "\\textbf{Non-annotated retrieved pairs}", "\\textbf{Missed annotated pairs}"], rows)


def table_embedding_llm(coll, summary):
    rows, vals = [], {}
    for i, (l, lname) in enumerate(LLMS.items()):
        if i:
            rows.append("\\midrule")
        for r, rname in RETRIEVERS.items():
            m = mean_of_targets(coll, combo(r, l), "OEH")
            vals[(r, l)] = (m.f1_macro, m.f1_weighted)
            rows.append([rname, lname, pct(m.f1_macro), pct(m.f1_weighted)])
    top = max(vals, key=lambda k: vals[k][0])
    rows = [[f"\\textbf{{{c}}}" if j >= 2 and (row[0], row[1]) == (RETRIEVERS[top[0]], LLMS[top[1]]) else c
             for j, c in enumerate(row)] if isinstance(row, list) else row for row in rows]
    f1 = {k: v[0] for k, v in vals.items()}
    ret_eff = {l: pp(max(f1[(r, l)] for r in RETRIEVERS), min(f1[(r, l)] for r in RETRIEVERS)) for l in LLMS}
    cls_eff = {r: pp(max(f1[(r, l)] for l in LLMS), min(f1[(r, l)] for l in LLMS)) for r in RETRIEVERS}
    rank = {l: sorted(RETRIEVERS, key=lambda r: -f1[(r, l)]) for l in LLMS}
    summary += ["== Table embedding_llm_performance",
                f"  range {pct(min(f1.values()))}-{pct(max(f1.values()))}; best {top} "
                f"{pct(vals[top][0])} / {pct(vals[top][1])}",
                "  retriever effect per LLM: " + ", ".join(f"{l} {v}" for l, v in ret_eff.items()),
                "  classifier effect per retriever: " + ", ".join(f"{r} {v}" for r, v in cls_eff.items()),
                "  retriever ranking per LLM: " + "; ".join(f"{l}: {' > '.join(v)}" for l, v in rank.items())]
    return tabular("llcc", ["\\textbf{Retriever}", "\\textbf{LLM}", "$\\mathbf{F_{1,m}}$",
                            "$\\mathbf{F_{1,w}}$"], rows)


def table_by_cohort(master, summary):
    full = master[master["mode"] == "OEH"].set_index(["model", "target_study"]).f1_macro
    best = {t: max(float(pct(full[(combo(r, l), t)])) for r in RETRIEVERS for l in LLMS) for t in TARGETS}
    rows = []
    summary += ["== Table macro_f1_by_target_cohort"]
    for i, (l, lname) in enumerate(LLMS.items()):
        if i:
            rows.append("\\addlinespace")
        rows.append(f"\\multicolumn{{5}}{{@{{}}l}}{{\\textit{{{lname}}}}} \\\\")
        for r, rname in RETRIEVERS.items():
            cells = []
            for t in TARGETS:
                v = pct(full[(combo(r, l), t)])
                cells.append(f"\\textbf{{{v}}}" if float(v) == best[t] else v)
            rows.append([rname] + cells)
        spread = {t: pp(max(full[(combo(r, l), t)] for r in RETRIEVERS), min(full[(combo(r, l), t)] for r in RETRIEVERS))
                  for t in TARGETS}
        summary.append(f"  {l} retriever spread per cohort: " + ", ".join(f"{t} {v}" for t, v in spread.items()))
    for t in TARGETS:
        winners = [combo(r, l) for r in RETRIEVERS for l in LLMS if float(pct(full[(combo(r, l), t)])) == best[t]]
        vals = [full[(combo(r, l), t)] for r in RETRIEVERS for l in LLMS]
        summary.append(f"  best {t}: {best[t]} ({', '.join(winners)}); range {pct(min(vals))}-{pct(max(vals))}")
    return tabular("@{}lcccc@{}", ["\\textbf{Retriever}"] + [f"\\textbf{{{n}}}" for n in TARGETS.values()], rows)


def table_graph_evidence(coll, summary):
    rows, withheld = [], []
    for l, lname in LLMS.items():
        w = mean_of_targets(coll, combo("biolord", l) + "_ng", "OEH").f1_macro
        s = mean_of_targets(coll, combo("biolord", l), "OEH").f1_macro
        withheld.append(w)
        rows.append([lname, pct(w), pct(s), f"+{pp(s, w)}" if s >= w else f"$-{pp(w, s)}$"])
    summary += ["== Table graph_evidence (BioLORD)",
                f"  withheld range {pct(min(withheld))}-{pct(max(withheld))}"]
    return tabular("lccc", ["\\textbf{Classifier}", "\\textbf{Withheld}", "\\textbf{Supplied}",
                            "\\textbf{$\\Delta$}"], rows)


def pair_predictions(gt: pd.DataFrame, errors: pd.DataFrame, model: str) -> pd.DataFrame:
    """One row per benchmark pair with reference and predicted class for a full-pipeline
    configuration: the evaluator's error list gives the wrong predictions (pairs missed at
    candidate generation appear there as not applicable); every other pair was correct."""
    e = errors[(errors.model == model) & (errors["mode"] == "OEH")]
    wrong = dict(zip(zip(e.target_study, e.src_var.map(norm_var), e.tgt_var.map(norm_var)), e["predicted class"]))
    out = pd.DataFrame({
        "target_study": gt.target_study,
        "key": list(zip(gt.target_study, gt.source_var_name.map(norm_var), gt.target_var_name.map(norm_var))),
        "domain": gt.domain.astype(str).str.strip().str.lower(),
        "y_true": gt["harmonization level"].astype(str).str.strip().str.lower()})
    out["y_pred"] = [wrong.get(k, y) for k, y in zip(out.key, out.y_true)]
    matched = int(out.key.isin(wrong.keys()).sum())
    if matched != len(e):
        raise ValueError(f"{model}: {len(e)} evaluator errors but {matched} matched to benchmark pairs")
    return out


def table_domain(gt, errors, dom, summary):
    """Macro-F1 per clinical domain computed over all benchmark pairs of that domain
    (pooled across the four target cohorts). The evaluator's pooled_domain_metrics
    averages per-cohort macro-F1 instead, which tiny cohort x domain cells dominate;
    it is kept in summary.txt for reference only."""
    from sklearn.metrics import f1_score
    preds = {l: pair_predictions(gt, errors, combo("biolord", l)) for l in LLMS}
    ev = dom[dom["mode"] == "OEH"]
    rows = []
    summary.append("== Table domain_ablation (BioLORD; macro-F1 over all pairs per domain | accuracy | errors"
                   " | evaluator mean of per-cohort macro-F1)")
    for key, name in DOMAINS:
        vals, notes = [], []
        for l in LLMS:
            g = preds[l][preds[l].domain == key]
            f1 = f1_score(g.y_true, g.y_pred, average="macro", zero_division=0)
            vals.append(f1)
            e = ev[(ev.model == combo("biolord", l)) & (ev.domain.str.lower() == key)].mean_f1_macro
            notes.append(f"{l} {pct(f1)} | {pct((g.y_true == g.y_pred).mean())} | {int((g.y_true != g.y_pred).sum())}"
                         f" | {pct(e.iloc[0]) if len(e) else 'n/a'}")
        n = int((preds[next(iter(LLMS))].domain == key).sum())
        rows.append([name, str(n)] + bold_max(vals))
        summary.append(f"  {key} (n={n}): " + "; ".join(notes))
    return tabular("p{4.0cm}cccc", ["\\textbf{Clinical domain}", "\\textbf{Pairs}"] +
                   [f"\\textbf{{{n}}}" for n in LLMS.values()], rows)


# --------------------------------------------------------------------------- Table 8
def is_abbreviation(label) -> bool:
    if label is None or pd.isna(label) or not str(label).strip():
        return True
    x = re.sub(r"\b(yes/no|y/n)\b|\?", "", str(label), flags=re.I).strip()
    if "(" in x or len(x.split()) != 1:
        return False
    parts = [p for p in re.split(r"[-/]", x) if p]
    return all(sum(c.isupper() for c in p) >= 2 or any(c.isdigit() for c in p) or len(p) <= 2 for p in parts)


def vocab(row) -> str:
    if row is None or pd.isna(row.get("variable concept code")):
        return ""
    return str(row["variable concept code"]).split("|")[0].split(":")[0].strip().lower()


def unit_missing(row) -> bool:
    return pd.isna(row.get("units")) or not str(row.get("units")).strip()


def is_continuous(row) -> bool:
    return str(row.get("vartype")).upper() in ("FLOAT", "INT") and pd.isna(row.get("categorical"))


def annotate_pairs(gt: pd.DataFrame, dicts) -> pd.DataFrame:
    recs = []
    for g in gt.itertuples(index=False):
        s = lookup(dicts, SOURCE, g.source_var_name)
        t = lookup(dicts, g.target_study, g.target_var_name)
        sv, tv = vocab(s), vocab(t)
        # label the matcher saw; derived variables absent from the dictionary fall back to the GT label
        tlabel = t["variablelabel"] if t is not None else (g.target_var_label or g.target_var_name)
        recs.append(dict(
            target_study=g.target_study, src=norm_var(g.source_var_name), tgt=norm_var(g.target_var_name),
            found=s is not None and t is not None,
            abbreviation=is_abbreviation(tlabel),
            cross_vocabulary=bool(sv and tv and sv != tv),
            study_specific=sv in STUDY_SPECIFIC or tv in STUDY_SPECIFIC,
            missing_unit=(s is not None and t is not None and is_continuous(s) and is_continuous(t)
                          and (unit_missing(s) or unit_missing(t))),
            domain=str(g.domain).lower()))
    return pd.DataFrame(recs)


def table_heterogeneity(gt, pairs, errors, dicts, summary):
    e = errors[(errors.model == HEADLINE) & (errors["mode"] == "OEH")]
    wrong = set(zip(e.target_study, e.src_var.map(norm_var), e.tgt_var.map(norm_var)))
    pairs = pairs.copy()
    pairs["correct"] = [(t, s, g) not in wrong for t, s, g in zip(pairs.target_study, pairs.src, pairs.tgt)]
    n_wrong_matched = int((~pairs.correct).sum())
    strata = [("All pairs", None), ("Abbreviation target label", "abbreviation"),
              ("Cross-vocabulary", "cross_vocabulary"), ("Study-specific code", "study_specific")]
    rows = []
    summary.append(f"== Table heterogeneity_accuracy ({HEADLINE}); errors in evaluator file: {len(e)}, "
                   f"matched to benchmark pairs: {n_wrong_matched}; pairs without dictionary entry: "
                   f"{int((~pairs.found).sum())}")
    for name, col in strata:
        sub = pairs if col is None else pairs[pairs[col]]
        cells = []
        for t in TARGETS:
            s = sub[sub.target_study == t]
            cells.append(f"{int(s.correct.sum())}/{len(s)}")
        pooled = f"{int(sub.correct.sum())}/{len(sub)}"
        cells.append(f"{pooled} ({pct(sub.correct.mean())})" if len(sub) >= 10 else pooled)
        rows.append([name] + cells)
        summary.append(f"  {name}: {' | '.join(cells)}")
    mu = pairs[pairs.missing_unit]
    lab = mu[mu.domain.isin(["measurement", "person"])]
    summary.append(f"  missing unit (continuous on both sides, unit empty on either side): {len(mu)} pairs, "
                   f"{len(lab)} in measurement/person domains: "
                   + "; ".join(f"{r.target_study}:{r.src}->{r.tgt}" for r in mu.itertuples()))
    summary.append("  continuous measurement-domain variables without a unit, per cohort dictionary:")
    for study, d in dicts.items():
        meas = d[(d["domain"].astype(str).str.lower() == "measurement")
                 & d.apply(is_continuous, axis=1)]
        k = int(meas.apply(unit_missing, axis=1).sum()) if len(meas) else 0
        summary.append(f"    {study}: {k}/{len(meas)} ({pct(k / len(meas)) if len(meas) else 'n/a'}%)")
    return tabular("lccccl", ["\\textbf{Stratum}", "\\textbf{T1}", "\\textbf{T2}", "\\textbf{T3}",
                              "\\textbf{T4}", "\\textbf{Pooled (\\%)}"], rows)


# --------------------------------------------------------------------------- Section 2.6 text
def heterogeneity_text(dicts, snapshot: Path, summary):
    """Variable-level shares per cohort dictionary and candidate-pair counts for the
    headline configuration, as quoted in the heterogeneity paragraph."""
    summary.append("== Heterogeneity text (variables per cohort dictionary)")
    for study, d in dicts.items():
        n = len(d)
        labels = d["variablelabel"]
        words = labels.fillna("").astype(str).str.split().str.len()
        abbr = int(labels.map(is_abbreviation).sum())
        vocabs = d.apply(vocab, axis=1)
        spec = int(vocabs.isin(STUDY_SPECIFIC).sum())
        summary.append(f"  {study} (n={n}): labels <=2 words {int((words <= 2).sum())} ({pct((words <= 2).mean())}%); "
                       f"abbreviation-only labels {abbr} ({pct(abbr / n)}%); "
                       f"study-specific code {spec} ({pct(spec / n)}%)")
    if snapshot is None:
        return
    cand = []
    for t in TARGETS:
        f = snapshot / HEADLINE / "OEH" / f"{SOURCE}_{t}_{HEADLINE}_OEH_full.csv"
        cand.append(pd.read_csv(f).assign(target_study=t))
    c = pd.concat(cand, ignore_index=True)
    pre = lambda s: s.fillna("").astype(str).str.split("|").str[0].str.split(":").str[0].str.strip().str.lower()
    sp, tp = pre(c.scode), pre(c.tcode)
    cross = (sp != "") & (tp != "") & (sp != tp)
    atc_rx = cross & pd.Series([{a, b} == {"atc", "rxnorm"} for a, b in zip(sp, tp)], index=c.index)
    match = c.harmonization_status.str.lower() != "not applicable"
    summary += [f"== Heterogeneity text (candidate pairs, {HEADLINE}, full pipeline)",
                f"  candidate pairs {len(c)}; cross-vocabulary {int(cross.sum())} ({pct(cross.mean())}%), "
                f"of which classified as a match {int((cross & match).sum())}; "
                f"ATC<->RxNorm among them {int(atc_rx.sum())} (matches {int((atc_rx & match).sum())})",
                "  cross-vocabulary pairs by prefix: " + ", ".join(
                    f"{a}/{b} {n}" for (a, b), n in
                    pd.Series(list(zip(sp[cross], tp[cross]))).value_counts().head(8).items())]

    def cont(dt, cats):
        return dt.astype(str).str.lower().isin(["float", "int"]) & cats.isna()

    def nounit(u):
        return u.isna() | (u.astype(str).str.strip() == "")

    s_nu = cont(c.source_data_type, c.source_categories_labels) & nounit(c.source_unit)
    t_nu = cont(c.target_data_type, c.target_categories_labels) & nounit(c.target_unit)
    nu = c[s_nu | t_nu]
    summary.append(f"  candidate pairs with a continuous variable without a unit on either side: {len(nu)}; "
                   "verdicts: " + ", ".join(f"{k} {v}" for k, v in nu.harmonization_status.value_counts().items()))
    ex = c[(c.target_study == "biostat-chf") & c.source.astype(str).str.lower().str.contains("6mwt_distance")
           & (c.harmonization_status.str.lower() != "not applicable")]
    for r in ex.itertuples():
        summary.append(f"  example: {r.source} [{r.source_unit}] -> {r.target} [{r.target_unit}] "
                       f"'{r.target_label}': {r.harmonization_status}")


# --------------------------------------------------------------------------- Figure
def residual_errors(errors, out: Path, summary):
    e = errors[(errors["mode"] == "OEH") & errors.model.isin([combo("biolord", l) for l in LLMS])]
    counts = (e.groupby(["model", "correct class", "predicted class"]).size()
              .unstack("model").reindex(columns=[combo("biolord", l) for l in LLMS]).fillna(0).astype(int))
    counts.columns = list(LLMS.values())
    counts = counts.reset_index()
    counts["_total"] = counts[list(LLMS.values())].sum(axis=1)   # most frequent confusion first
    counts = counts.sort_values("_total", ascending=False, kind="stable").drop(columns="_total")
    counts.to_csv(out / "residual_errors_biolord.csv", index=False)

    totals = counts[list(LLMS.values())].sum()
    pm = counts[counts["correct class"].isin(["partial match", "not applicable"])
                & counts["predicted class"].isin(["partial match", "not applicable"])]
    pm_tot = pm[list(LLMS.values())].sum()

    def cell(tc, pc):
        r = counts[(counts["correct class"] == tc) & (counts["predicted class"] == pc)]
        return r[list(LLMS.values())].sum() if len(r) else pd.Series(0, index=list(LLMS.values()))

    comp = counts[counts["correct class"] == "compatible match"][list(LLMS.values())].sum()
    summary += ["== Residual errors (BioLORD, full pipeline)",
                "  total: " + ", ".join(f"{k} {v}" for k, v in totals.items()),
                "  PM<->NA: " + ", ".join(f"{k} {pm_tot[k]} ({pct(pm_tot[k] / totals[k])}%)" for k in totals.index),
                "  NA->PM: " + ", ".join(f"{k} {v}" for k, v in cell("not applicable", "partial match").items()),
                "  PM->NA: " + ", ".join(f"{k} {v}" for k, v in cell("partial match", "not applicable").items()),
                "  IM->PM: " + ", ".join(f"{k} {v}" for k, v in cell("identical match", "partial match").items()),
                "  IM->NA: " + ", ".join(f"{k} {v}" for k, v in cell("identical match", "not applicable").items()),
                "  NA->IM: " + ", ".join(f"{k} {v}" for k, v in cell("not applicable", "identical match").items()),
                "  compatible misassigned: " + ", ".join(f"{k} {v}" for k, v in comp.items())]

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    labels = [f"{a.replace(' match', '').replace('not applicable', 'NA').capitalize() if a != 'not applicable' else 'NA'}"
              f" → {b.replace(' match', '').capitalize() if b != 'not applicable' else 'NA'}"
              for a, b in zip(counts["correct class"], counts["predicted class"])]
    n, k = len(counts), len(LLMS)
    y = np.arange(n)
    h = 0.8 / k
    plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False})
    fig, ax = plt.subplots(figsize=(7.0, 0.42 * n + 1.0))
    for i, name in enumerate(LLMS.values()):
        vals = counts[name].to_numpy()
        pos = y + (i - (k - 1) / 2) * h
        ax.barh(pos, vals, height=h * 0.9, color=SERIES_COLORS[i], label=f"{name} (n={totals[name]})",
                edgecolor="white", linewidth=1)
        for p, v in zip(pos, vals):
            if v:
                ax.text(v + 0.3, p, str(v), va="center", fontsize=7, color="#3d3d3a")
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_xlabel("Misclassified benchmark pairs (reference → predicted)")
    ax.xaxis.grid(True, color="#e6e5e0", linewidth=0.6)
    ax.set_axisbelow(True)
    ax.set_xlim(0, counts[list(LLMS.values())].to_numpy().max() * 1.08)
    ax.legend(frameon=False, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=k, fontsize=8)
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(out / f"residual_error_across_classes.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)


# --------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--eval-dir", required=True, type=Path)
    ap.add_argument("--gt", required=True, type=Path)
    ap.add_argument("--dicts", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--snapshot", type=Path, default=None,
                    help="article snapshot folder (cross_mapping_article_output) for the candidate-pair "
                         "counts of the heterogeneity text; optional")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)

    coll, master, dom, errors = load_eval(a.eval_dir)
    gt = pd.read_excel(a.gt)
    dicts = load_dictionaries(a.dicts)
    summary = [f"eval_dir={a.eval_dir}", f"gt={a.gt}", f"dicts={a.dicts}", ""]

    tables = {
        "tab_ablation_best": table_ablation(coll, summary),
        "tab_candidate_recall": table_candidate_recall(master, summary),
        "tab_embedding_llm_performance": table_embedding_llm(coll, summary),
        "tab_macro_f1_by_target_cohort": table_by_cohort(master, summary),
        "tab_graph_evidence": table_graph_evidence(coll, summary),
        "tab_domain_ablation": table_domain(gt, errors, dom, summary),
        "tab_heterogeneity_accuracy": table_heterogeneity(gt, annotate_pairs(gt, dicts), errors, dicts, summary),
    }
    for name, tex in tables.items():
        (a.out / f"{name}.tex").write_text(tex)
    residual_errors(errors, a.out, summary)
    heterogeneity_text(dicts, a.snapshot, summary)
    (a.out / "summary.txt").write_text("\n".join(summary) + "\n")
    print("\n".join(summary))
    print(f"\nwritten to {a.out}")


if __name__ == "__main__":
    main()
