"""Precompute retrieved context for every conceptual gold prompt, split
train/validation, so the optimization workflow can run pure text (no Cohere
in the loop). Output: concept_dataset.json {train:[...], val:[...]}."""
import st_stub, app
import json, os, pickle, itertools, random

# Cohere query embeddings: rotate keys + cache (same as run_bench)
import embeddings as _emb
_CK = [k.strip() for k in os.environ.get("COHERE_API_KEYS", "").split(",") if k.strip()] \
      or [os.environ.get("COHERE_API_KEY", "")]
_cyc = itertools.cycle(_CK)
_QC = pickle.load(open("query_emb_cache.pkl", "rb")) if os.path.exists("query_emb_cache.pkl") else {}
def _eq(text):
    if text in _QC: return _QC[text]
    last = None
    for _ in range(len(_CK)):
        try:
            v = _emb.embed([text], is_query=True, api_key=next(_cyc))[0]
            _QC[text] = v; pickle.dump(_QC, open("query_emb_cache.pkl", "wb")); return v
        except RuntimeError as e:
            last = e
            if "429" in str(e): continue
            raise
    raise RuntimeError(f"cohere keys exhausted: {last}")
_emb.embed_query = _eq

INDEX = app.load_index()
gold = [json.loads(l) for l in open("gold_prompts.jsonl")]
concept = [g for g in gold if g["grade"] == "judge"]

data = []
for g in concept:
    df = app.detect_district(g["prompt"])
    hits = app.retrieve(g["prompt"], INDEX, district_folder=df)
    ctx = app.build_context_block(hits)[:5000]  # cap: conceptual answers need top chunks, not all
    data.append({"id": g["id"], "metric": g["metric"], "prompt": g["prompt"],
                 "reference": g["reference"], "context": ctx})
    print(f"  ctx for {g['id']} ({g['metric']}) — {len(ctx)} chars")

random.seed(13); random.shuffle(data)
half = len(data) // 2
out = {"train": data[:half], "val": data[half:]}
json.dump(out, open("concept_dataset.json", "w"))
print(f"\nWrote concept_dataset.json: {len(out['train'])} train, {len(out['val'])} val")
