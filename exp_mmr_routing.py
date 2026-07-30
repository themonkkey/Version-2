"""Two experiments against the voyage baseline (47.2% recall@10 on the 180-prompt hard set).

1. MMR (maximal marginal relevance) -- we have no diversity control at all; retrieval is
   pure cosine. The table pilot showed sibling chunks from the same page crowding each other
   out of top-k (5.81 chunks per gold page vs 3.21). MMR penalises near-duplicates.

2. Query routing -- methodology is 253 of 59,388 chunks (0.4%) yet scores only 45%
   recall@10, because it competes for top-k against 57,687 vision chunks. Route methodology
   questions to a methodology-only candidate set so they compete against 253 instead.

Both are pure re-ranking / filtering over the existing index: no re-embed, no corpus change.

Usage:  EMBED_DEVICE=cpu venv/bin/python exp_mmr_routing.py
"""
import json
import os
import re
from collections import defaultdict
from math import comb

import numpy as np

os.environ.setdefault("EMBED_PROVIDER", "voyage_local")

import st_stub  # noqa: F401,E402
import app  # noqa: E402
import embeddings as emb  # noqa: E402
from eval_voyage import load_voyage_index  # noqa: E402
from run_hard_retrieval import KS, wilson  # noqa: E402

# run_hard_retrieval's module body monkeypatches embed_query to a Cohere-cached function.
# Left in place it silently scores Cohere vectors against a voyage index -> 0% recall with
# no error. Restore and assert. (This actually happened; see handoff notes.)
emb.embed_query = lambda text: emb.embed([text], is_query=True)[0]
assert emb.provider() == "voyage_local", f"wrong provider: {emb.provider()}"

HARD = "hard_retrieval.jsonl"
CAND = 50          # candidate pool re-ranked by MMR
TOPK = 10          # final list length, matching recall@10

# Methodology questions ask about concepts and procedures rather than a named place.
# NOTE: stems must NOT carry a trailing \b -- "\bestimat\b" can never match "estimate".
# The first version of this regex had that bug and fired on only 6 of 180 prompts.
METHOD_TERMS = re.compile(
    r"\b(?:gva|gdp|gsdp|gddp|nddp|gsva|"
    r"estimat\w*|methodolog\w*|compil\w*|deprecia\w*|deflat\w*|deriv\w*|"
    r"valuat\w*|calculat\w*|comput\w*|measur\w*|account\w*|apportion\w*|allocat\w*|"
    r"approach|procedure|method|formula|definition|define|defined|"
    r"base year|constant price|current price|value added|intermediate consumption|"
    r"product tax|subsid\w*|revision|reference point|price level|"
    r"sector contribution|divided among states)\b",
    re.I)


def classify(query):
    """methodology vs data question. Heuristic first -- only worth a model call if this
    proves insufficient."""
    if app.detect_district(query):
        return "data"          # names a district -> district/vision material
    return "methodology" if METHOD_TERMS.search(query) else "data"


def mmr_select(sims, matrix, k=TOPK, cand=CAND, lam=0.7):
    """Maximal marginal relevance over the top `cand` by cosine.

    Greedily picks the item maximising  lam*sim(q,d) - (1-lam)*max sim(d, already_picked).
    Vectors are L2-normalised, so dot product is cosine.
    """
    pool = np.argsort(sims)[::-1][:cand]
    if len(pool) == 0:
        return []
    selected = [int(pool[0])]
    pool = [int(i) for i in pool[1:]]
    while len(selected) < k and pool:
        sel_mat = matrix[selected]                      # (s, d)
        cand_mat = matrix[pool]                         # (c, d)
        redundancy = (cand_mat @ sel_mat.T).max(axis=1)  # (c,)
        score = lam * sims[pool] - (1 - lam) * redundancy
        best = int(np.argmax(score))
        selected.append(pool.pop(best))
    return selected


def plain_select(sims, k=TOPK):
    return [int(i) for i in np.argsort(sims)[::-1][:k]]


def build_folder_masks(chunks):
    idx = defaultdict(list)
    for i, c in enumerate(chunks):
        idx[c.get("folder")].append(i)
    return {f: np.asarray(v) for f, v in idx.items()}


def rank_of_gold(order, chunks, gold_source, gold_page):
    for rank, i in enumerate(order, 1):
        c = chunks[i]
        if c["source"] != gold_source:
            continue
        if gold_page is None or c.get("page") == gold_page:
            return rank
    return None


def mcnemar(base_ranks, new_ranks, k):
    gain = sum(1 for a, b in zip(base_ranks, new_ranks)
               if not (a and a <= k) and (b and b <= k))
    loss = sum(1 for a, b in zip(base_ranks, new_ranks)
               if (a and a <= k) and not (b and b <= k))
    n = gain + loss
    if n == 0:
        return gain, loss, 1.0
    p = sum(comb(n, x) for x in range(0, min(gain, loss) + 1)) / 2 ** n * 2
    return gain, loss, min(p, 1.0)


def report(name, prompts, ranks):
    by = defaultdict(list)
    for g, r in zip(prompts, ranks):
        by[g["stratum"]].append(r)
    print(f"\n===== {name} =====")
    print(f"  {'stratum':22s} " + "  ".join(f"R@{k:<2d}" for k in KS) + "    n")
    for s in sorted(by):
        v = by[s]
        cells = [f"{sum(1 for r in v if r and r <= k)/len(v)*100:4.0f}" for k in KS]
        print(f"  {s:22s} " + "  ".join(cells) + f"  {len(v):3d}")
    cells = [f"{sum(1 for r in ranks if r and r <= k)/len(ranks)*100:4.0f}" for k in KS]
    print(f"  {'OVERALL':22s} " + "  ".join(cells) + f"  {len(ranks):3d}")
    hit = sum(1 for r in ranks if r and r <= 10)
    p, lo, hi = wilson(hit, len(ranks))
    print(f"  recall@10 = {hit}/{len(ranks)} = {p*100:.1f}%  CI[{lo*100:.1f}, {hi*100:.1f}]")


if __name__ == "__main__":
    prompts = [json.loads(l) for l in open(HARD)]
    index = load_voyage_index()
    chunks, matrix = index["chunks"], index["matrix"]
    folders = build_folder_masks(chunks)
    print(f"Index: {len(chunks)} chunks. Folders: "
          f"{ {f: len(v) for f, v in folders.items()} }")

    # router accuracy first -- if it misclassifies, routing cannot help
    routed = [classify(g["prompt"]) for g in prompts]
    truth = ["methodology" if g["gold_folder"] == "methodology" else "data" for g in prompts]
    tp = sum(1 for r, t in zip(routed, truth) if r == t == "methodology")
    fp = sum(1 for r, t in zip(routed, truth) if r == "methodology" and t == "data")
    fn = sum(1 for r, t in zip(routed, truth) if r == "data" and t == "methodology")
    print(f"\nRouter: correct-methodology={tp}  false-positive={fp}  missed={fn}"
          f"  accuracy={sum(1 for r,t in zip(routed,truth) if r==t)/len(prompts)*100:.0f}%")

    print(f"\nEmbedding {len(prompts)} queries...")
    qvecs = [emb.embed_query(g["prompt"]) for g in prompts]

    # methodology candidate set: methodology + training (training decks teach methodology)
    meth_idx = np.concatenate([folders.get("methodology", np.array([], int)),
                               folders.get("training", np.array([], int))])

    configs = {}
    # Hard routing loses a misrouted prompt entirely -- the gold chunk is not even a
    # candidate. Soft routing keeps every chunk in play and only nudges the score, so a
    # false positive costs a little rank instead of the whole answer.
    for name in ["baseline", "mmr_0.7", "mmr_0.5", "routing",
                 "soft_route_0.05", "soft_route_0.10", "routing+mmr_0.7"]:
        ranks = []
        for g, qv, route in zip(prompts, qvecs, routed):
            sims = matrix @ qv
            if name.startswith("soft_route") and route == "methodology":
                boost = float(name.split("_")[-1])
                sims = sims.copy()
                sims[meth_idx] += boost
            use_route = name.startswith("routing") and route == "methodology"
            if use_route:
                sub = meth_idx
                sub_sims = sims[sub]
                if "mmr" in name:
                    lam = float(name.split("_")[-1])
                    local = mmr_select(sub_sims, matrix[sub], lam=lam)
                else:
                    local = plain_select(sub_sims)
                order = [int(sub[i]) for i in local]
            elif "mmr" in name:
                lam = float(name.split("_")[-1])
                order = mmr_select(sims, matrix, lam=lam)
            else:
                order = plain_select(sims)
            ranks.append(rank_of_gold(order, chunks, g["gold_source"], g["gold_page"]))
        configs[name] = ranks
        report(name, prompts, ranks)

    print("\n===== paired vs baseline (exact McNemar) =====")
    base = configs["baseline"]
    for name, ranks in configs.items():
        if name == "baseline":
            continue
        print(f"  {name}")
        for k in KS:
            gain, loss, p = mcnemar(base, ranks, k)
            b = sum(1 for r in base if r and r <= k)
            n_ = sum(1 for r in ranks if r and r <= k)
            print(f"    R@{k:<2d}: {b/len(base)*100:5.1f}% -> {n_/len(ranks)*100:5.1f}%"
                  f"   gained={gain:3d} lost={loss:3d}  p={p:.4f}")

    # methodology stratum specifically -- what routing targets
    print("\n===== method_paraphrase stratum only =====")
    mi = [i for i, g in enumerate(prompts) if g["stratum"] == "method_paraphrase"]
    for name, ranks in configs.items():
        hit = sum(1 for i in mi if ranks[i] and ranks[i] <= 10)
        print(f"  {name:18s} R@10 = {hit}/{len(mi)} = {hit/len(mi)*100:.0f}%")
