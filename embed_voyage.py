"""Re-embed the EXISTING corpus chunks with local voyage-4-nano.

Chunks are deliberately unchanged. The table-serialization pilot showed rebuilding them
did not improve retrieval (PILOT_TABLES_RESULT.md), so this changes exactly one variable
-- the embedding model -- and stays comparable to the Phase 1 baseline.

Output goes to EILA by default to keep the internal disk free; point VOYAGE_OUT elsewhere
to change that. Resumable: partial batches are checkpointed, so an interrupted run picks
up where it stopped.

Usage:  HF_HOME=/Volumes/EILA/hf-cache venv/bin/python embed_voyage.py [limit]
"""
import os
import pickle
import sys
import time

import numpy as np

os.environ.setdefault("EMBED_PROVIDER", "voyage_local")
import embeddings as emb  # noqa: E402  (env must be set before import)

SRC = "embed_chunks.pkl"
OUT_DIR = os.environ.get("VOYAGE_OUT", "/Volumes/EILA/swarna-voyage")
BATCH = int(os.environ.get("VOYAGE_BATCH", "32"))
CKPT_EVERY = 100  # batches


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    os.makedirs(OUT_DIR, exist_ok=True)
    npy = os.path.join(OUT_DIR, "voyage_matrix.npy")
    ckpt = os.path.join(OUT_DIR, "voyage_progress.pkl")

    with open(SRC, "rb") as f:
        meta = pickle.load(f)
    chunks = meta["chunks"]
    if limit:
        chunks = chunks[:limit]
    n = len(chunks)
    # Every batch is padded to its longest member, so mixing a 300-char chunk with a
    # 7,000-char one wastes most of the compute on padding. Sorting by length first makes
    # each batch uniform and removes ~54% of the padded work on this corpus. The order is
    # restored before saving, and the sort is deterministic so a resume reproduces it.
    order = sorted(range(n), key=lambda i: (len(chunks[i]["text"]), i))
    texts = [chunks[i]["text"] for i in order]
    print(f"Embedding {n} chunks with {emb.model_id()} (length-sorted batching)")

    start, mat = 0, None
    if os.path.exists(ckpt) and os.path.exists(npy):
        with open(ckpt, "rb") as f:
            state = pickle.load(f)
        if state.get("n") == n and state.get("model_id") == emb.model_id():
            start = state["done"]
            mat = np.load(npy, mmap_mode=None)[:start]
            print(f"  resuming from chunk {start}")

    m = emb._voyage_local_model()
    print(f"  device={m.device} max_seq={m.max_seq_length} batch={BATCH}")

    out = [mat] if mat is not None and start else []
    t0 = time.time()
    for bi, i in enumerate(range(start, n, BATCH), 1):
        batch = texts[i:i + BATCH]
        out.append(emb.embed(batch, is_query=False))
        done = min(i + BATCH, n)
        if bi % 20 == 0 or done == n:
            rate = (done - start) / max(time.time() - t0, 1e-6)
            eta = (n - done) / max(rate, 1e-6)
            print(f"  {done}/{n}  {rate:.0f} chunks/s  eta {eta/60:.1f} min")
        if bi % CKPT_EVERY == 0 or done == n:
            np.save(npy, np.concatenate(out, axis=0).astype(np.float32))
            with open(ckpt, "wb") as f:
                pickle.dump({"done": done, "n": n, "model_id": emb.model_id()}, f)

    sorted_matrix = np.concatenate(out, axis=0).astype(np.float32)
    assert sorted_matrix.shape[0] == n, f"{sorted_matrix.shape[0]} != {n}"
    # undo the length sort so row i of the matrix is chunk i again
    matrix = np.empty_like(sorted_matrix)
    matrix[np.asarray(order)] = sorted_matrix
    np.savez_compressed(os.path.join(OUT_DIR, "voyage_index.npz"), matrix=matrix)
    with open(os.path.join(OUT_DIR, "voyage_chunks.pkl"), "wb") as f:
        pickle.dump({"chunks": chunks, "model_id": emb.model_id()}, f)
    print(f"\nDone: {matrix.shape} -> {OUT_DIR}  in {(time.time()-t0)/60:.1f} min")


if __name__ == "__main__":
    main()
