"""Score the patched pilot index on the same 180 hard questions as the baseline.

Only the extraction of 127 documents changed. Model, retrieval code, questions and
metric are identical to run_hard_retrieval.py, and every query vector comes from the
cache built during the baseline run -- so this costs no API calls and the comparison
is like-for-like.

Usage:  venv/bin/python eval_pilot.py
"""
import json
import os
import pickle
from collections import defaultdict

import numpy as np

import st_stub  # noqa: F401  (must precede app import)
import app
import embeddings as _emb
from run_hard_retrieval import KS, doc_rank_of_gold, rank_of_gold, wilson

HARD = "hard_retrieval.jsonl"
BASE = "hard_retrieval_results.jsonl"
OUT = "pilot_results.jsonl"

# every hard-set query was embedded during the baseline run; reuse those vectors so the
# pilot is scored with byte-identical queries and spends nothing
_QC = pickle.load(open("query_emb_cache.pkl", "rb"))


def _cached(text):
    if text not in _QC:
        raise RuntimeError(f"query not in cache: {text[:60]}")
    return _QC[text]


_emb.embed_query = _cached


def load_pilot_index():
    with open("pilot_chunks.pkl", "rb") as f:
        meta = pickle.load(f)
    mat = np.load("pilot_index.npz")["matrix"].astype(np.float32)
    assert len(meta["chunks"]) == mat.shape[0]
    return {"mode": "embed", "chunks": meta["chunks"], "matrix": mat,
            "model_id": meta.get("model_id")}


def score(index, prompts):
    rows = []
    for g in prompts:
        hits = app.retrieve(g["prompt"], index, district_folder=None)
        rows.append({**g,
                     "rank": rank_of_gold(hits, g["gold_source"], g["gold_page"]),
                     "doc_rank": doc_rank_of_gold(hits, g["gold_source"])})
    return rows


def table(name, rows):
    print(f"\n===== {name} =====")
    print(f"  {'stratum':22s} " + "  ".join(f"R@{k:<2d}" for k in KS) + "   docR@10   n")
    by = defaultdict(list)
    for r in rows:
        by[r["stratum"]].append(r)
    for s in sorted(by):
        v = by[s]
        n = len(v)
        cells = [f"{sum(1 for r in v if r['rank'] and r['rank'] <= k) / n * 100:4.0f}"
                 for k in KS]
        d = sum(1 for r in v if r["doc_rank"] and r["doc_rank"] <= 10)
        print(f"  {s:22s} " + "  ".join(cells) + f"    {d / n * 100:4.0f}    {n:3d}")
    n = len(rows)
    cells = [f"{sum(1 for r in rows if r['rank'] and r['rank'] <= k) / n * 100:4.0f}"
             for k in KS]
    d = sum(1 for r in rows if r["doc_rank"] and r["doc_rank"] <= 10)
    print(f"  {'OVERALL':22s} " + "  ".join(cells) + f"    {d / n * 100:4.0f}    {n:3d}")


def mcnemar(base, pilot, k):
    """Exact two-sided McNemar on the paired per-prompt outcomes."""
    from math import comb
    b = {r["id"]: r for r in base}
    p = {r["id"]: r for r in pilot}
    ids = [i for i in p if i in b]
    hit = lambda r: bool(r["rank"] and r["rank"] <= k)
    n01 = sum(1 for i in ids if not hit(b[i]) and hit(p[i]))     # pilot gains
    n10 = sum(1 for i in ids if hit(b[i]) and not hit(p[i]))     # pilot loses
    n = n01 + n10
    if n == 0:
        return n01, n10, 1.0
    pv = sum(comb(n, x) for x in range(0, min(n01, n10) + 1)) / 2 ** n * 2
    return n01, n10, min(pv, 1.0)


if __name__ == "__main__":
    prompts = [json.loads(l) for l in open(HARD)]
    base = [json.loads(l) for l in open(BASE) if json.loads(l)["config"] == "dense_only"]

    # the baseline comparison point is dense_only: the two hand-tuned rules were shown
    # to be net negative, and leaving them on would confound the extraction change
    app.ABLATE_FORCE, app.ABLATE_RESCUE = True, True
    index = load_pilot_index()
    print(f"Pilot index: {len(index['chunks'])} chunks, model={index.get('model_id')}")

    rows = score(index, prompts)
    with open(OUT, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    table("BASELINE  dense_only", base)
    table("PILOT     dense_only + header-bound tables", rows)

    print("\n===== paired comparison (exact McNemar) =====")
    for k in KS:
        gain, loss, pv = mcnemar(base, rows, k)
        bh = sum(1 for r in base if r["rank"] and r["rank"] <= k)
        ph = sum(1 for r in rows if r["rank"] and r["rank"] <= k)
        n = len(rows)
        print(f"  R@{k:<2d}: {bh/n*100:5.1f}% -> {ph/n*100:5.1f}%   "
              f"gained={gain:3d} lost={loss:3d}  p={pv:.4f}")
    k = 10
    ph = sum(1 for r in rows if r["rank"] and r["rank"] <= k)
    p_, lo, hi = wilson(ph, len(rows))
    print(f"\n  pilot recall@10 = {ph}/{len(rows)} = {p_*100:.1f}%  "
          f"CI[{lo*100:.1f}, {hi*100:.1f}]")

    # table-heavy subset is where the fix should show up if it works at all
    import re
    tab = [r for r in rows if r["stratum"] in ("numeric_table", "vision_specific")]
    tb = [r for r in base if r["stratum"] in ("numeric_table", "vision_specific")]
    hb = sum(1 for r in tb if r["rank"] and r["rank"] <= 10)
    hp = sum(1 for r in tab if r["rank"] and r["rank"] <= 10)
    print(f"  table-heavy strata recall@10: {hb/len(tb)*100:.1f}% -> "
          f"{hp/len(tab)*100:.1f}%  (n={len(tab)})")
    print(f"\nPer-prompt results -> {OUT}")
