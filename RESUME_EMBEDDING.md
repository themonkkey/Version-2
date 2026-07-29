# Resume the voyage-4-nano embedding

Paused 2026-07-28 at **44,000 / 59,388 chunks (74%)**. 15,388 remaining.
Checkpoint verified: `voyage_out/voyage_matrix.npy` holds 44,000 rows, norms correct.
Safe to sleep, reboot, or leave for days -- nothing is held in memory.

## Resume

```bash
cd ~/swarna-andhra-chatbot && EMBED_DEVICE=cpu OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 VOYAGE_OUT=/Users/thesinghaa/swarna-andhra-chatbot/voyage_out VOYAGE_BATCH=16 nice -n 10 ./venv/bin/python -u embed_voyage.py > voyage_embed_resume.log 2>&1 &
```

It reads the checkpoint and continues from 44,000 automatically. Expect ~3-4 hours:
the run is length-sorted, so everything left is the long tail (median 2,168 chars,
max 7,147) and transformer cost scales quadratically with sequence length.

**Use CPU, not MPS.** Measured on this machine, GPU was slower (2 vs 3 chunks/s) and
roughly doubled memory pressure -- Apple silicon's unified memory means the GPU competes
for the same 16 GB rather than adding capacity. Switching to MPS mid-run pushed swap to
91% and was reverted.

## Then score it

```bash
cd ~/swarna-andhra-chatbot && EMBED_DEVICE=cpu ./venv/bin/python eval_voyage.py
```

**Baseline to beat: recall@10 = 40.0%** (72/180), doc-level 74% -- see `PHASE1_BASELINE.md`.

Decision rule, fixed in advance: adopt voyage only if recall@10 holds or improves. Flat is
a good result, because flat plus no API key, no quota and no monthly ceiling is a clear net
win for a government deployment. A significant drop means the Cohere index stays.

## State of the wider work

- `PHASE1_BASELINE.md` -- hard benchmark, 180 questions, baseline 40.0% recall@10.
  Two findings: the two hand-tuned retrieval rules are net negative (p<0.01 at R@1-5),
  and 34 points sit between doc-level (74%) and chunk-level (40%) recall.
- `PILOT_TABLES_RESULT.md` -- table serialization did NOT help (40.0% -> 37.8%, p=0.56).
  Corpus rebuild is not justified; Docling/LlamaParse/vision-LLM parsing all premature.
- **Next highest-value move remains the reranker**, which converts doc-level hits into
  chunk-level hits and needs no corpus change. It requires a paid Cohere key.

## Housekeeping still open

- `sudo mdutil -i off /Volumes/EILA` -- stop Spotlight indexing 1.8 TB it never needs to.
- Deployed app is still down. Fastest free fix: put all four Cohere trial keys in
  Streamlit secrets as `COHERE_API_KEYS` (three still have quota; only the dead one is
  currently configured).
