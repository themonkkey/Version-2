"""Score the voyage-4-nano index on the same 180 hard questions as the baseline.

Only the embedding model changed -- chunks, retrieval code, questions and metric are all
identical to run_hard_retrieval.py's dense_only configuration. Queries are re-embedded
with voyage locally (the cached vectors are Cohere's and live in a different vector space,
so they cannot be reused).

Baseline to beat: recall@10 = 40.0% (72/180), doc-level 74%. See PHASE1_BASELINE.md.

Usage:  EMBED_DEVICE=cpu venv/bin/python eval_voyage.py
"""
import json
import os
import pickle
from collections import defaultdict

import numpy as np

os.environ.setdefault("EMBED_PROVIDER", "voyage_local")

import st_stub  # noqa: F401,E402  (must precede app import)
import app  # noqa: E402
import embeddings as emb  # noqa: E402
from run_hard_retrieval import KS, doc_rank_of_gold, rank_of_gold, wilson  # noqa: E402

# CRITICAL: importing run_hard_retrieval executes its module body, which monkeypatches
# embeddings.embed_query with a Cohere key-rotating function backed by query_emb_cache.pkl.
# Left in place, every query here would return a CACHED COHERE VECTOR scored against a
# VOYAGE index -- two unrelated vector spaces, which silently produces 0% recall rather
# than an error. Restore the real implementation and verify it took.
emb.embed_query = lambda text: emb.embed([text], is_query=True)[0]
assert emb.provider() == "voyage_local", f"wrong provider: {emb.provider()}"

HARD = "hard_retrieval.jsonl"
BASE = "hard_retrieval_results.jsonl"
OUT = "voyage_results.jsonl"
IDX_DIR = os.environ.get("VOYAGE_OUT", "voyage_out")


def load_voyage_index():
    with open(os.path.join(IDX_DIR, "voyage_chunks.pkl"), "rb") as f:
        meta = pickle.load(f)
    mat = np.load(os.path.join(IDX_DIR, "voyage_index.npz"))["matrix"].astype(np.float32)
    assert len(meta["chunks"]) == mat.shape[0], "chunk/matrix length mismatch"
    return {"mode": "embed", "chunks": meta["chunks"], "matrix": mat,
            "model_id": meta.get("model_id")}


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


def mcnemar(base, new, k):
    """Exact two-sided McNemar on paired per-prompt outcomes."""
    from math import comb
    b = {r["id"]: r for r in base}
    p = {r["id"]: r for r in new}
    ids = [i for i in p if i in b]
    hit = lambda r: bool(r["rank"] and r["rank"] <= k)  # noqa: E731
    gain = sum(1 for i in ids if not hit(b[i]) and hit(p[i]))
    loss = sum(1 for i in ids if hit(b[i]) and not hit(p[i]))
    n = gain + loss
    if n == 0:
        return gain, loss, 1.0
    pv = sum(comb(n, x) for x in range(0, min(gain, loss) + 1)) / 2 ** n * 2
    return gain, loss, min(pv, 1.0)


if __name__ == "__main__":
    prompts = [json.loads(l) for l in open(HARD)]
    base = [json.loads(l) for l in open(BASE)
            if json.loads(l)["config"] == "dense_only"]

    index = load_voyage_index()
    print(f"Voyage index: {len(index['chunks'])} chunks, model={index.get('model_id')}")
    print(f"Embedding {len(prompts)} queries locally...")

    # the two hand-tuned rules stay off, matching the dense_only baseline this is
    # compared against -- leaving them on would confound the model change
    app.ABLATE_FORCE, app.ABLATE_RESCUE = True, True

    rows = []
    for i, g in enumerate(prompts, 1):
        hits = app.retrieve(g["prompt"], index, district_folder=None)
        rows.append({**g,
                     "rank": rank_of_gold(hits, g["gold_source"], g["gold_page"]),
                     "doc_rank": doc_rank_of_gold(hits, g["gold_source"])})
        if i % 40 == 0:
            print(f"  {i}/{len(prompts)}")

    with open(OUT, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    table("BASELINE  cohere embed-english-v3.0 (dense_only)", base)
    table("VOYAGE    voyage-4-nano 1024d (dense_only)", rows)

    print("\n===== paired comparison (exact McNemar) =====")
    n = len(rows)
    for k in KS:
        gain, loss, pv = mcnemar(base, rows, k)
        bh = sum(1 for r in base if r["rank"] and r["rank"] <= k)
        nh = sum(1 for r in rows if r["rank"] and r["rank"] <= k)
        print(f"  R@{k:<2d}: {bh/n*100:5.1f}% -> {nh/n*100:5.1f}%   "
              f"gained={gain:3d} lost={loss:3d}  p={pv:.4f}")

    nh = sum(1 for r in rows if r["rank"] and r["rank"] <= 10)
    p_, lo, hi = wilson(nh, n)
    print(f"\n  voyage recall@10 = {nh}/{n} = {p_*100:.1f}%  "
          f"CI[{lo*100:.1f}, {hi*100:.1f}]   (baseline 40.0%)")
    print(f"\nPer-prompt results -> {OUT}")
