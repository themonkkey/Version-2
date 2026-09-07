# Working notes

## TurboVec / vector compression — parked (2026-09-06)

TurboVec (Rust index on Google's TurboQuant, ICLR 2026) compresses embeddings
8–16× (float32 → 4/2-bit) and out-searches FAISS. Evaluated for this project:
**not adopted — solves scale/RAM, not answer quality.**

- Our index is 59K chunks × 1024-dim ≈ 240 MB; brute-force dot product is
  milliseconds. Nothing to speed up.
- Quantization is lossy: best case preserves recall, never improves it.
- Bench evidence says retrieval already lands the right material in context
  ~95–100% of the time; conceptual losses are generation-side (dilution,
  padding, verbosity) — vector compression touches none of that.

**When to revisit**: if Streamlit Community Cloud RAM (~1 GB) becomes a problem
loading the embedding matrix. TurboVec (or plain int8 quantization, simpler)
would cut 240 MB → ~30–60 MB at ~1–2% recall cost. Hosting fix, not quality fix.

Priority for conceptual quality instead: system-prompt surgery (answer only
what's asked, top-3 only) → structured lookup over structured_district_data.csv
for numeric/comparative queries → re-run the 60-prompt conceptual bench
(bench_gemini_models.py, Sonnet judge).
