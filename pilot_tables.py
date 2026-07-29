"""Pilot: does fixing table serialization improve retrieval?

Rebuilds ONLY the 127 documents that the hard benchmark's gold chunks come from, using
ingest_v2 (header-bound tables + enforced size caps), re-embeds them with the SAME model
the live index uses, and splices them into a copy of the index. Everything else -- model,
retrieval code, questions, metric -- is held constant, so any movement is attributable to
the extraction change.

Cheap by design: ~127 documents instead of a 2.8 GB rebuild, so the full-corpus
re-ingest only gets spent if this shows a gain.

Usage:  venv/bin/python pilot_tables.py [--build-only]
Writes: pilot_chunks.pkl, pilot_index.npz
"""
import itertools
import json
import os
import pickle
import sys
import time

import numpy as np

import embeddings as _emb
import ingest_v2 as v2

HARD = "hard_retrieval.jsonl"
SRC_CHUNKS = "embed_chunks.pkl"
OUT_CHUNKS = "pilot_chunks.pkl"
OUT_NPZ = "pilot_index.npz"
BATCH = 90          # Cohere v2 embed accepts up to 96 texts per call

_CK = [k.strip() for k in os.environ.get("COHERE_API_KEYS", "").split(",") if k.strip()] \
      or [os.environ.get("COHERE_API_KEY", "")]
_cyc = itertools.cycle(_CK)


def embed_batch(texts):
    """Embed a batch, rotating keys on quota/rate limits."""
    last = None
    for _ in range(len(_CK) * 3):
        try:
            return _emb.embed(texts, is_query=False, api_key=next(_cyc))
        except RuntimeError as e:
            last = e
            if "429" in str(e):
                time.sleep(3)
                continue
            raise
    raise RuntimeError(f"all Cohere keys exhausted: {last}")


def _load_matrix():
    if os.path.exists("embed_index.npz"):
        return np.load("embed_index.npz")["matrix"]
    parts = ["embed_index_part0.npz", "embed_index_part1.npz"]
    return np.concatenate([np.load(p)["matrix"] for p in parts], axis=0)


def main():
    gold_docs = sorted({json.loads(l)["gold_source"] for l in open(HARD)})
    print(f"Pilot covers {len(gold_docs)} gold documents")

    with open(SRC_CHUNKS, "rb") as f:
        meta = pickle.load(f)
    old_chunks = meta["chunks"]
    matrix = _load_matrix()
    assert len(old_chunks) == matrix.shape[0], "chunk/matrix length mismatch"
    print(f"Baseline index: {len(old_chunks)} chunks, dim {matrix.shape[1]}")

    # keep every chunk that is NOT from a pilot document, with its existing vector
    gold_set = set(gold_docs)
    keep = [i for i, c in enumerate(old_chunks) if c["source"] not in gold_set]
    print(f"  keeping {len(keep)} untouched chunks, "
          f"replacing {len(old_chunks) - len(keep)}")

    # re-extract the pilot documents with the fixed extractor
    new_chunks = []
    for n, rel in enumerate(gold_docs, 1):
        try:
            cs = v2.chunks_for(rel)
        except Exception as e:
            print(f"  ! {rel}: {e}")
            cs = []
        new_chunks.extend(cs)
        if n % 20 == 0 or n == len(gold_docs):
            print(f"  extracted {n}/{len(gold_docs)} docs -> {len(new_chunks)} chunks")
    if not new_chunks:
        sys.exit("no chunks produced; aborting")

    over = sum(1 for c in new_chunks if len(c["text"]) > 2048)
    print(f"\nNew chunks: {len(new_chunks)}  "
          f"(over Cohere's ~512-token limit: {over} = {over/len(new_chunks)*100:.1f}%)")

    print(f"Embedding {len(new_chunks)} new chunks in batches of {BATCH}...")
    vecs = []
    for i in range(0, len(new_chunks), BATCH):
        batch = [c["text"] for c in new_chunks[i:i + BATCH]]
        vecs.append(embed_batch(batch))
        done = min(i + BATCH, len(new_chunks))
        print(f"  {done}/{len(new_chunks)}")
        time.sleep(0.5)
    new_mat = np.concatenate(vecs, axis=0).astype(np.float32)

    chunks = [old_chunks[i] for i in keep] + new_chunks
    mat = np.concatenate([matrix[keep], new_mat], axis=0).astype(np.float32)
    assert len(chunks) == mat.shape[0]

    with open(OUT_CHUNKS, "wb") as f:
        pickle.dump({"chunks": chunks, "model_id": meta.get("model_id")}, f)
    np.savez_compressed(OUT_NPZ, matrix=mat)
    print(f"\nPatched index: {len(chunks)} chunks -> {OUT_CHUNKS}, {OUT_NPZ}")


if __name__ == "__main__":
    main()
