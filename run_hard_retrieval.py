"""Measure recall@k on the hard retrieval set against the LIVE pipeline.

Unlike run_bench.py -- which scores a hit when the target NUMBER appears anywhere in the
assembled context -- this scores a hit only when the retriever returns the specific
(source, page) chunk that the question was written from. That is a much stricter test and,
unlike the saturated gold set, it has room to move.

Runs four configurations so the contribution of each layer is separable:

  full        current production pipeline
  no_force    district_data force-injection disabled
  no_rescue   numeric-table keyword rescue disabled
  dense_only  both disabled -- what the embeddings alone actually retrieve

Usage:  venv/bin/python run_hard_retrieval.py [configs] [limit]
        configs : comma-separated subset of the four above. Default: all.
        limit   : cap on prompts (for a quick smoke run). Default: all.
"""
import itertools
import json
import math
import os
import pickle
import sys
import time
from collections import defaultdict

import st_stub  # noqa: F401  (must precede app import)
import app
import embeddings as _emb

HARD = "hard_retrieval.jsonl"
CONFIGS = {
    "full":       (False, False),
    "no_force":   (True,  False),
    "no_rescue":  (False, True),
    "dense_only": (True,  True),
}
KS = (1, 3, 5, 10)

# ---- Cohere query embeddings: rotate across keys + cache to disk -------------------
# Same approach as run_bench.py: each trial key is capped per month, so rotate across
# them and cache every query vector so repeated runs cost nothing.
_CK = [k.strip() for k in os.environ.get("COHERE_API_KEYS", "").split(",") if k.strip()] \
      or [os.environ.get("COHERE_API_KEY", "")]
_cyc = itertools.cycle(_CK)
_QC_PATH = "query_emb_cache.pkl"
try:
    _QC = pickle.load(open(_QC_PATH, "rb"))
except Exception:
    _QC = {}


def _embed_query_rr(text):
    if text in _QC:
        return _QC[text]
    last = None
    for _ in range(len(_CK)):
        try:
            v = _emb.embed([text], is_query=True, api_key=next(_cyc))[0]
            _QC[text] = v
            pickle.dump(_QC, open(_QC_PATH, "wb"))
            return v
        except RuntimeError as e:
            last = e
            if "429" in str(e):     # this key is spent, try the next
                continue
            raise
    raise RuntimeError(f"all Cohere keys quota/rate limited: {last}")


_emb.embed_query = _embed_query_rr


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (p, max(0.0, c - h), min(1.0, c + h))


def rank_of_gold(hits, gold_source, gold_page):
    """1-based rank of the gold chunk in the returned hits, or None if absent.

    Falls back to matching on source alone when the gold chunk has no page (district_data
    files are a single whole-file chunk, so source identifies them uniquely).
    """
    for i, h in enumerate(hits, 1):
        if h["source"] != gold_source:
            continue
        if gold_page is None or h.get("page") == gold_page:
            return i
    return None


def doc_rank_of_gold(hits, gold_source):
    """1-based rank of the gold DOCUMENT, ignoring which page was returned.

    Reported alongside chunk recall because the two failure modes need different fixes:
    right document / wrong page is a chunking problem, wrong document entirely is an
    embedding or corpus-balance problem.
    """
    for i, h in enumerate(hits, 1):
        if h["source"] == gold_source:
            return i
    return None


def run_config(name, prompts, index):
    app.ABLATE_FORCE, app.ABLATE_RESCUE = CONFIGS[name]
    rows = []
    for i, g in enumerate(prompts, 1):
        q = g["prompt"]
        df = app.detect_district(q)
        for attempt in range(6):
            try:
                hits = app.retrieve(q, index, district_folder=df)
                break
            except RuntimeError as e:
                if "429" in str(e) and attempt < 5:
                    time.sleep(20)
                    continue
                raise
        r = rank_of_gold(hits, g["gold_source"], g["gold_page"])
        dr = doc_rank_of_gold(hits, g["gold_source"])
        rows.append({**g, "config": name, "rank": r, "doc_rank": dr,
                     "n_hits": len(hits),
                     "sources": [h["source"] for h in hits][:5]})
        if i % 25 == 0:
            got = sum(1 for x in rows if x["rank"] and x["rank"] <= 10)
            print(f"    [{name}] {i}/{len(prompts)}  recall@10 so far {got}/{i}")
    app.ABLATE_FORCE, app.ABLATE_RESCUE = False, False
    return rows


def report(name, rows):
    print(f"\n===== {name} =====")
    print(f"  {'stratum':22s} " + "  ".join(f"R@{k:<2d}" for k in KS) + "   docR@10   n")
    by = defaultdict(list)
    for r in rows:
        by[r["stratum"]].append(r)
    for s in sorted(by):
        v = by[s]
        n = len(v)
        cells = []
        for k in KS:
            hit = sum(1 for r in v if r["rank"] and r["rank"] <= k)
            cells.append(f"{hit / n * 100:4.0f}")
        dhit = sum(1 for r in v if r["doc_rank"] and r["doc_rank"] <= 10)
        print(f"  {s:22s} " + "  ".join(cells) + f"    {dhit / n * 100:4.0f}    {n:3d}")
    n = len(rows)
    cells = []
    for k in KS:
        hit = sum(1 for r in rows if r["rank"] and r["rank"] <= k)
        cells.append(f"{hit / n * 100:4.0f}")
    dhit = sum(1 for r in rows if r["doc_rank"] and r["doc_rank"] <= 10)
    print(f"  {'OVERALL':22s} " + "  ".join(cells) + f"    {dhit / n * 100:4.0f}    {n:3d}")
    k10 = sum(1 for r in rows if r["rank"] and r["rank"] <= 10)
    p, lo, hi = wilson(k10, n)
    print(f"  recall@10 = {k10}/{n} = {p*100:.1f}%  CI[{lo*100:.1f}, {hi*100:.1f}]")


if __name__ == "__main__":
    want = sys.argv[1].split(",") if len(sys.argv) > 1 else list(CONFIGS)
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
    bad = [c for c in want if c not in CONFIGS]
    if bad:
        sys.exit(f"unknown config(s): {bad}. choose from {list(CONFIGS)}")

    prompts = [json.loads(l) for l in open(HARD)]
    if limit:
        prompts = prompts[:limit]
    index = app.load_index()
    print(f"Hard set: {len(prompts)} prompts. Index mode={index['mode']} "
          f"model={index.get('model_id')}\nConfigs: {want}")

    out = f"hard_retrieval_results.jsonl"
    all_rows = []
    for cfg in want:
        print(f"\n--- running config: {cfg} ---")
        rows = run_config(cfg, prompts, index)
        report(f"{cfg}  (recall %, by stratum)", rows)
        all_rows.extend(rows)

    with open(out, "w") as f:
        for r in all_rows:
            f.write(json.dumps(r) + "\n")
    print(f"\nPer-prompt results -> {out}")
