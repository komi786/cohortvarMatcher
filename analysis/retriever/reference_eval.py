"""Evaluate embedding models on the reference pairs (Supplementary Tables S3-S5).

The reference pairs are the external set used to choose tau and alpha; they are
not the test set (TIME-CHF). Source labels are embedded as queries and target
labels as passages, so instruction-tuned retrievers (BMRetriever, e5) get their
intended prompts. For models without prefixes (SapBERT, BioLORD, OpenAI) both
sides are identical and the published S4/S5 numbers are reproduced.

Output rows (one column per model):
    tau90, ret_tau90, ret_0.45, cos_*, mrr, R@k   Table S4
    gold_ret_aX, set_aX                           Table S5 (tau = 0.45, gap rule not applied)
    lost_to_cap      gold >= tau but ranked below L      (cap cost recall)
    gold_rank_6_10   gold ranked 6..10                   (lost if L were 5)
    cap_binds_tau    % queries with > L candidates >= tau
    cap_binds_eff    % queries with > L candidates >= max(tau, 0.80 * s_1)
    pool_cos_median  median cosine over all candidates (high = compressed scores)

Run from the repo root:
    .venv/bin/python -m analysis.retriever.reference_eval sapbert biolord openai
    .venv/bin/python -m analysis.retriever.reference_eval sapbert --pairs data/clinVar_E.csv --out data/output/sensitivity_results
    .venv/bin/python -m analysis.retriever.reference_eval sapbert --modes data/clinVar_OE.csv
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
PAIRS = REPO / "data/clinVar_E.csv"
CACHE = REPO / "data/output/embed_cache"          # written here
# Read-only: embeddings computed for the submitted tables (never written to)
LEGACY_CACHE = Path.home() / "phd_projects/CohortVarLinker/.embed_cache"
LEGACY_PAIRS = Path.home() / "phd_projects/CohortVarLinker/conformal/clinVar.csv"
TAU = 0.45
ALPHA = 0.80
ALPHAS = (0.0, 0.80, 0.85, 0.90)
L = 10


def load_reference_pairs(path: Path = PAIRS):
    """Pairs, text index, per-target-study pools and the embedding-cache hash."""
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    df = df[df["class_label"].str.strip().str.lower() != "not applicable"]
    p = pd.DataFrame({"source_study": df.source_study.str.strip().str.lower(),
                      "target_study": df.target_study.str.strip().str.lower(),
                      "text1": df.source_var_label.str.strip(),
                      "text2": df.target_var_label.str.strip()})
    p = p[(p.text1 != "") & (p.text2 != "")].drop_duplicates().reset_index(drop=True)
    texts = sorted(set(p.text1) | set(p.text2))
    idx = {t: i for i, t in enumerate(texts)}
    h = hashlib.md5(json.dumps(texts, ensure_ascii=False).encode("utf-8")).hexdigest()[:10]
    pools = p.groupby("target_study")["text2"].apply(
        lambda x: [idx[t] for t in sorted(set(x))]).to_dict()
    return p, idx, pools, h


def _legacy_vectors(model_key: str) -> dict:
    """Text -> vector from the read-only cache behind the submitted S4/S5 (symmetric models only)."""
    from src.embed_model import INSTRUCTION_MODELS, PASSAGE_PREFIXES
    if model_key in INSTRUCTION_MODELS or model_key in PASSAGE_PREFIXES or not LEGACY_PAIRS.exists():
        return {}
    _, idx, _, h = load_reference_pairs(LEGACY_PAIRS)
    f = LEGACY_CACHE / f"{model_key}_calibration_embeddings_{h}.npy"
    if not f.exists():
        return {}
    E = np.load(f)
    return {t: E[i] for t, i in idx.items()}


def embed(model_key: str, texts: list, side: str, h: str = "") -> np.ndarray:
    """Embeddings for one side (query/passage); only texts not yet cached are embedded."""
    store = CACHE / f"{model_key}_{side}.npz"
    known = {}
    if store.exists():
        z = np.load(store, allow_pickle=False)
        known = dict(zip(z["texts"].tolist(), z["vecs"]))
    missing = [t for t in texts if t not in known]
    if missing:
        legacy = _legacy_vectors(model_key)
        known.update({t: legacy[t] for t in missing if t in legacy})
        missing = [t for t in missing if t not in known]
    if missing:
        from src.embed_model import get_model
        model, _ = get_model(model_key)
        E = np.asarray(model.embed_batch(missing, is_query=(side == "query")), dtype=np.float32)
        E /= np.clip(np.linalg.norm(E, axis=1, keepdims=True), 1e-12, None)
        known.update(zip(missing, E))
    if missing or not store.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        np.savez(store, texts=np.array(list(known)), vecs=np.stack(list(known.values())))
    return np.stack([known[t] for t in texts])


def tau_90(gold: np.ndarray, target: float = 0.90, step: float = 0.01) -> float:
    """Highest threshold on a 0.01 grid keeping >= target of gold pairs (as in S4)."""
    for t in np.round(np.arange(1.0, -step, -step), 2):
        if (gold >= t).mean() >= target:
            return float(t)
    return 0.0


def full_cutoff(s_desc: np.ndarray, tau: float, alpha: float = ALPHA, limit: int = L) -> int:
    """k* of the deployed retriever (vector_db.adaptive_retrieval at tag paper-script-review).

    Hits are the top `limit` scores >= tau (Qdrant score_threshold = tau). The gap
    median is taken over all of those hits, not only those above tau_eff, so tau
    changes the gap cut as well as the floor.
    """
    hits = s_desc[s_desc >= tau][:limit]
    if hits.size == 0:
        return 0
    k_thr = int((hits >= max(tau, alpha * hits[0])).sum())
    if k_thr < 2:
        return k_thr
    d = hits[:-1] - hits[1:]
    sig = d > 2 * float(np.median(d))
    k_gap = int(np.argmax(sig)) + 1 if sig.any() else k_thr
    return min(k_gap, k_thr)


def cutoff_metrics(scores: list, gold: np.ndarray, ranks: np.ndarray, taus=(0.45, 0.50)) -> dict:
    """Gold retention under the floor only (as in S5) and under the full cut-off, per tau."""
    row, ks = {}, {}
    for t in taus:
        bar = np.array([max(t, ALPHA * s[0]) for s in scores])
        floor_kept = (gold >= bar) & (ranks <= L)
        ks[t] = np.array([full_cutoff(s, t) for s in scores])
        full_kept = ranks <= ks[t]
        row[f"ret_floor_{t:.2f}"] = 100 * floor_kept.mean()
        row[f"ret_full_{t:.2f}"] = 100 * full_kept.mean()
        row[f"lost_to_gap_{t:.2f}"] = int((floor_kept & ~full_kept).sum())
        row[f"set_full_{t:.2f}"] = float(ks[t].mean())
    lo, hi = min(taus), max(taus)
    row[f"k_shrinks_at_{lo:.2f}"] = int((ks[lo] < ks[hi]).sum())
    row[f"gold_lost_at_{lo:.2f}_kept_at_{hi:.2f}"] = int(((ranks > ks[lo]) & (ranks <= ks[hi])).sum())
    row[f"gold_gained_at_{lo:.2f}"] = int(((ranks <= ks[lo]) & (ranks > ks[hi])).sum())
    return row


def evaluate(model_key: str, pairs: Path = PAIRS) -> dict:
    p, idx, pools, h = load_reference_pairs(pairs)
    texts = sorted(idx, key=idx.get)
    Q = embed(model_key, texts, "query", h)
    P = embed(model_key, texts, "passage", h)

    gold, ranks, scores, smax = [], [], [], []
    for r in p.itertuples():
        pool = pools[r.target_study]
        s = np.sort(P[pool] @ Q[idx[r.text1]])[::-1]
        g = float((P[pool] @ Q[idx[r.text1]])[pool.index(idx[r.text2])])
        gold.append(g)
        ranks.append(int((s > g).sum()) + 1)
        scores.append(s)
        smax.append(float(s[0]))
    gold, ranks, smax = np.array(gold), np.array(ranks), np.array(smax)

    # Table S4
    t90 = tau_90(gold)
    row = {"model": model_key, "n": len(p),
           "tau90": t90, "ret_tau90": 100 * (gold >= t90).mean(),
           "ret_0.45": 100 * (gold >= TAU).mean(),
           "cos_mean": 100 * gold.mean(), "cos_median": 100 * np.median(gold),
           "cos_sd": 100 * gold.std(ddof=1), "mrr": 100 * (1 / ranks).mean()}
    for k in (1, 3, 5, 10):
        row[f"R@{k}"] = 100 * (ranks <= k).mean()

    # Table S5: relative bound alpha at tau = 0.45 (gap rule not applied)
    for a in ALPHAS:
        bar = np.maximum(TAU, a * smax)
        row[f"gold_ret_a{a:.2f}"] = 100 * ((gold >= bar) & (ranks <= L)).mean()
        row[f"set_a{a:.2f}"] = np.mean([min(L, int((s >= b).sum())) for s, b in zip(scores, bar)])

    # Cap L
    above = gold >= TAU
    row["lost_to_cap"] = int((above & (ranks > L)).sum())
    row["gold_rank_6_10"] = int((above & (ranks > 5) & (ranks <= L)).sum())
    row["cap_binds_tau"] = 100 * np.mean([(s >= TAU).sum() > L for s in scores])
    row["cap_binds_eff"] = 100 * np.mean([(s >= max(TAU, ALPHA * s[0])).sum() > L for s in scores])

    # Full cut-off (floor + gap rule), tau 0.45 vs 0.50
    row.update(cutoff_metrics(scores, gold, ranks))

    row["pool_cos_median"] = 100 * float(np.median(np.concatenate(scores)))
    row = {k: (round(float(v), 2) if isinstance(v, (float, np.floating)) else v)
           for k, v in row.items()}

    pairs = p.assign(cosine=np.round(gold, 5), rank=ranks,
                     **{f"r@{k}": ranks <= k for k in (1, 3, 5, 10)})
    return row, pairs


# ── Mode comparison: label-only (NE) vs label + concept names (OEH) ─────────────
# Only pairs whose two variables are found in a concept-annotated dictionary are used
# (Aachen-HF -> ARIC / ViennaHF-Register). Texts are built as at tag paper-script-review:
#   NE  query = index = cleaned label
#   OEH query = cleaned label, concept name, context names   (NeuroSymbolicMatcher._vector_query)
#       index = label + concept name + context, fuzzy-deduplicated (get_csv_text, EH)

def _dictionary(path: Path) -> dict:
    d = pd.read_csv(path, dtype=str, keep_default_na=False, encoding_errors="ignore")
    d.columns = [c.lower().strip() for c in d.columns]
    d = d.rename(columns={"variablename": "variable name", "variablelabel": "variable label"})
    return {r["variable name"].strip().lower(): r for r in d.to_dict("records")}


def _texts(label: str, row: dict, mode: str):
    from src.fuzz_match import FuzzyMatcher
    from src.utils import clean_label_remove_temporal_context as clean
    lab = clean(label.strip())
    if mode == "label":
        return lab.lower(), lab.lower()
    concept = row.get("variable concept name", "").strip()
    context = [c.strip() for c in row.get("additional context concept name", "").split("|") if c.strip()]
    query = lab
    for part in [concept] + context:
        if part and part not in query:
            query += f", {part}"
    parts = [lab.lower()]
    if concept and concept.lower() != lab.lower():
        parts.append(concept.lower())
    parts += [c.lower() for c in context if c.lower() not in (lab.lower(), concept.lower())]
    passage = " ".join(FuzzyMatcher._deduplicate_parts(parts=parts, threshold=0.8))
    return clean(query).lower(), passage


def _concept_row(concept: str) -> dict:
    """clinVar_2 concept field 'concept || context || ...' -> dictionary-style row."""
    parts = [p.strip().strip('"').strip() for p in str(concept).split("||") if p.strip()]
    return {"variable concept name": parts[0] if parts else "",
            "additional context concept name": "|".join(parts[1:])}


def _pairs_with_concepts(source: Path) -> list:
    """(target_study, src_label, src_row, tgt_label, tgt_row) from a clinVar_2 CSV or a dictionary folder."""
    if source.suffix == ".csv":
        df = pd.read_csv(source, dtype=str, keep_default_na=False)
        df = df[df["class_label"].str.strip().str.lower() != "not applicable"]
        return [(r.target_study.strip().lower(), r.source_var_label, _concept_row(r.source_concept_name),
                 r.target_var_label, _concept_row(r.target_concept_name)) for r in df.itertuples()]
    dicts = {f.parent.name.lower(): _dictionary(f) for f in source.rglob("*.csv")}
    df = pd.read_csv(PAIRS, dtype=str, keep_default_na=False)
    df = df[df["class_label"].str.strip().str.lower() != "not applicable"]
    keep, seen = [], set()
    for r in df.itertuples():
        s, t = dicts.get(r.source_study.strip().lower()), dicts.get(r.target_study.strip().lower())
        sr = s.get(r.source_var_name.strip().lower()) if s else None
        tr = t.get(r.target_var_name.strip().lower()) if t else None
        key = (r.target_study.strip().lower(), r.source_var_label.strip(), r.target_var_label.strip())
        if sr is not None and tr is not None and key not in seen:
            seen.add(key)
            keep.append((key[0], r.source_var_label, sr, r.target_var_label, tr))
    return keep


def mode_comparison(model_key: str, source: Path, n_boot: int = 2000, seed: int = 0) -> pd.DataFrame:
    """tau90 (bootstrap 95% CI), retention and ranking for NE vs OEH text on the same pairs."""
    keep = _pairs_with_concepts(source)
    rng = np.random.default_rng(seed)
    boot = rng.integers(0, len(keep), size=(n_boot, len(keep)))
    out = []
    for mode in ("label", "hybrid"):
        q = [_texts(sl, sr, mode)[0] for _, sl, sr, _, _ in keep]
        g = [_texts(tl, tr, mode)[1] for _, _, _, tl, tr in keep]
        texts = sorted(set(q) | set(g))
        idx = {t: i for i, t in enumerate(texts)}
        h = hashlib.md5(json.dumps(texts, ensure_ascii=False).encode("utf-8")).hexdigest()[:10]
        Q, P = embed(model_key, texts, "query", h), embed(model_key, texts, "passage", h)
        pools = {}
        for (ts, *_), gt in zip(keep, g):
            pools.setdefault(ts, set()).add(idx[gt])
        pools = {k: sorted(v) for k, v in pools.items()}
        gold, ranks, scores = [], [], []
        for (ts, *_), qt, gt in zip(keep, q, g):
            s = P[pools[ts]] @ Q[idx[qt]]
            gs = float(s[pools[ts].index(idx[gt])])
            gold.append(gs)
            ranks.append(int((s > gs).sum()) + 1)
            scores.append(np.sort(s)[::-1])
        gold, ranks = np.array(gold), np.array(ranks)
        cut = {k: round(float(v), 1) for k, v in cutoff_metrics(scores, gold, ranks).items()}
        bt = np.array([tau_90(gold[b]) for b in boot])
        out.append({"model": model_key, "text": "NE (label)" if mode == "label" else "OEH (label + concept)",
                    "n_pairs": len(keep), "tau90": tau_90(gold),
                    "tau90_ci": f"{np.percentile(bt, 2.5):.2f}-{np.percentile(bt, 97.5):.2f}",
                    "ret_0.45": round(100 * (gold >= 0.45).mean(), 1),
                    "ret_0.50": round(100 * (gold >= 0.50).mean(), 1),
                    "gold_median": round(float(np.median(gold)), 3),
                    "R@1": round(100 * (ranks <= 1).mean(), 1),
                    "mrr": round(100 * (1 / ranks).mean(), 1),
                    "pool_size_median": int(np.median([len(pools[ts]) for ts, *_ in keep])),
                    **cut})
    return pd.DataFrame(out)


# ── Alternative cut-offs: tail-referenced gap rule and calibrated selector ──────
# Both are calibrated on one half of the reference queries and scored on the other
# (splits grouped by source text), repeated n_splits times.
#   current   tau + alpha floor + gap at 2x median of all hits >= tau (deployed)
#   floor     tau + alpha floor only
#   tailgap   tau + alpha floor; cut at first drop inside the floor set > c * sigma,
#             sigma = median consecutive drop over ranks 11-30 (known-irrelevant tail)
#   selector  logistic P(gold | features) over hits >= tau; keep p >= p0
# Operating points: "@90" = calibrated to >= 90% retention on the calibration half;
# "@size" = matched to the current method's mean set size on the calibration half.

TAIL = (10, 30)          # 0-based slice -> ranks 11..30
TARGET = 0.90


def _tail_stats(s: np.ndarray):
    t = s[TAIL[0]:TAIL[1]]
    if t.size < 3:
        return None, None, None
    d = t[:-1] - t[1:]
    return float(np.median(d)), float(t.mean()), float(t.std() or 1e-6)


def _query_table(scores: list, ranks: np.ndarray, tau: float) -> list:
    """Per query: hits >= tau (<= L), floor count, tail stats, gold position among hits."""
    out = []
    for s, r in zip(scores, ranks):
        hits = s[s >= tau][:L]
        k_thr = int((hits >= max(tau, ALPHA * hits[0])).sum()) if hits.size else 0
        sig, mu, sd = _tail_stats(s)
        out.append(dict(hits=hits, k_thr=k_thr, sig=sig, mu=mu, sd=sd,
                        gold_pos=int(r) if r <= hits.size else None,
                        k_cur=full_cutoff(s, tau)))
    return out


def _k_tailgap(q: dict, c: float) -> int:
    k, h = q["k_thr"], q["hits"]
    if k < 2 or q["sig"] is None or not np.isfinite(c):
        return k
    d = h[:k - 1] - h[1:k]
    cut = np.nonzero(d > c * max(q["sig"], 1e-6))[0]
    return int(cut[0]) + 1 if cut.size else k


def _features(q: dict) -> np.ndarray:
    h = q["hits"]
    if h.size == 0:
        return np.zeros((0, 5))
    sig = max(q["sig"] or 1e-3, 1e-6)
    nxt = np.append(h[1:], h[-1] if q["mu"] is None else q["mu"])
    return np.column_stack([h, h[0] - h, np.log1p(np.arange(h.size)),
                            (h - (q["mu"] if q["mu"] is not None else h.min())) / (q["sd"] or 1.0),
                            (h - nxt) / sig])


def _evaluate_k(table, idxs, kfun):
    ks = np.array([kfun(table[i]) for i in idxs])
    kept = np.array([table[i]["gold_pos"] is not None and table[i]["gold_pos"] <= k for i, k in zip(idxs, ks)])
    return kept.mean(), ks.mean(), ks


def _calibrate_c(table, idxs, size_target=None):
    """Smallest c (most cutting) reaching TARGET retention, or the given mean set size."""
    for c in list(np.geomspace(0.5, 200, 80)) + [np.inf]:
        ret, size, _ = _evaluate_k(table, idxs, lambda q, c=c: _k_tailgap(q, c))
        if (ret >= TARGET) if size_target is None else (size >= size_target):
            return c
    return np.inf


def _predict(clf, feats, idxs) -> dict:
    """Per-query P(gold) for every hit, one batched predict per split."""
    rows = [i for i in idxs if len(feats[i])]
    if not rows:
        return {i: np.zeros(0) for i in idxs}
    p = clf.predict_proba(np.vstack([feats[i] for i in rows]))[:, 1]
    out, at = {i: np.zeros(0) for i in idxs}, 0
    for i in rows:
        out[i] = p[at:at + len(feats[i])]
        at += len(feats[i])
    return out


def _selector_sets(table, idxs, probs, p0):
    kept = [table[i]["gold_pos"] is not None and probs[i][table[i]["gold_pos"] - 1] >= p0 for i in idxs]
    sizes = [int((probs[i] >= p0).sum()) for i in idxs]
    return np.mean(kept), np.mean(sizes)


def cutoff_comparison(model_key: str, pairs: Path = PAIRS, taus=(0.45, 0.50),
                      n_splits: int = 50, seed: int = 0) -> pd.DataFrame:
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    p, idx, pools, h = load_reference_pairs(pairs)
    texts = sorted(idx, key=idx.get)
    Q, P = embed(model_key, texts, "query", h), embed(model_key, texts, "passage", h)
    scores, ranks = [], []
    for r in p.itertuples():
        pool = pools[r.target_study]
        raw = P[pool] @ Q[idx[r.text1]]
        g = float(raw[pool.index(idx[r.text2])])
        scores.append(np.sort(raw)[::-1])
        ranks.append(int((raw > g).sum()) + 1)
    ranks = np.array(ranks)
    groups = p.text1.values
    uniq = np.unique(groups)
    rng = np.random.default_rng(seed)
    rows = []
    for tau in taus:
        table = _query_table(scores, ranks, tau)
        feats = [_features(q) for q in table]
        acc = {}
        for _ in range(n_splits):
            cal_g = set(rng.choice(uniq, size=len(uniq) // 2, replace=False))
            cal = [i for i, g in enumerate(groups) if g in cal_g]
            test = [i for i, g in enumerate(groups) if g not in cal_g]
            res = {}
            res["current"] = _evaluate_k(table, test, lambda q: q["k_cur"])[:2]
            res["floor"] = _evaluate_k(table, test, lambda q: q["k_thr"])[:2]
            cur_size_cal = _evaluate_k(table, cal, lambda q: q["k_cur"])[1]
            c90 = _calibrate_c(table, cal)
            cs = _calibrate_c(table, cal, size_target=cur_size_cal)
            res["tailgap@90"] = _evaluate_k(table, test, lambda q: _k_tailgap(q, c90))[:2]
            res["tailgap@size"] = _evaluate_k(table, test, lambda q: _k_tailgap(q, cs))[:2]
            # selector
            Xc = np.vstack([feats[i] for i in cal if len(feats[i])])
            yc = np.concatenate([np.arange(1, table[i]["hits"].size + 1) == (table[i]["gold_pos"] or -1)
                                 for i in cal if len(feats[i])])
            clf = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000)).fit(Xc, yc)
            pc, pt = _predict(clf, feats, cal), _predict(clf, feats, test)
            # split-conformal p0: the floor((1-target)(n+1))-th smallest gold probability
            gold_p = np.sort([pc[i][table[i]["gold_pos"] - 1] if table[i]["gold_pos"] else -np.inf
                              for i in cal])
            j = max(int(np.floor((1 - TARGET) * (len(gold_p) + 1))) - 1, 0)
            fin = gold_p[np.isfinite(gold_p)]
            p90 = gold_p[j] if np.isfinite(gold_p[j]) else fin.min()
            allp = np.sort(np.concatenate([pc[i] for i in cal]))[::-1]
            sizes = np.arange(1, allp.size + 1) / len(cal)       # mean set size if p0 = allp[k]
            psize = allp[min(np.searchsorted(sizes, cur_size_cal), allp.size - 1)]
            res["selector@90"] = _selector_sets(table, test, pt, p90)
            res["selector@size"] = _selector_sets(table, test, pt, psize)
            for k, (ret, size) in res.items():
                acc.setdefault(k, []).append((ret, size))
        for k, v in acc.items():
            v = np.array(v)
            rows.append({"model": model_key, "tau": tau, "method": k,
                         "retention": round(100 * v[:, 0].mean(), 1), "ret_sd": round(100 * v[:, 0].std(), 1),
                         "set_size": round(v[:, 1].mean(), 2)})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("models", nargs="+", help="keys from src/embed_model.MODEL_MAP")
    ap.add_argument("--pairs", type=Path, default=PAIRS, help="reference pairs CSV (default: data/clinVar_E.csv)")
    ap.add_argument("--out", type=Path, help="folder (or .csv path) for the results")
    ap.add_argument("--modes", type=Path, metavar="PAIRS_OR_DIR",
                    help="compare NE vs OEH text: a clinVar_2-style CSV with concept names, "
                         "or a folder of concept-annotated dictionaries")
    ap.add_argument("--cutoffs", action="store_true",
                    help="compare current cut-off with tail-referenced gap and calibrated selector")
    a = ap.parse_args()
    if a.cutoffs:
        df = pd.concat([cutoff_comparison(m, a.pairs) for m in a.models], ignore_index=True)
        print(df.to_string(index=False))
        if a.out:
            a.out.mkdir(parents=True, exist_ok=True)
            df.to_csv(a.out / "cutoff_comparison.csv", index=False)
        raise SystemExit
    if a.modes:
        df = pd.concat([mode_comparison(m, a.modes) for m in a.models], ignore_index=True)
        print(df.to_string(index=False))
        if a.out:
            a.out.mkdir(parents=True, exist_ok=True)
            df.to_csv(a.out / "mode_comparison.csv", index=False)
        raise SystemExit
    results = {m: evaluate(m, a.pairs) for m in a.models}
    df = pd.DataFrame([row for row, _ in results.values()]).set_index("model").T
    pd.set_option("display.width", 200)
    print(df.to_string())
    if a.out:
        out = a.out if a.out.suffix == ".csv" else a.out / "reference_eval.csv"
        out.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out)
        for m, (_, pairs) in results.items():
            pairs.to_csv(out.parent / f"{m}_pairs.csv", index=False)
        print(f"saved: {out} and one <model>_pairs.csv per model in {out.parent}")
