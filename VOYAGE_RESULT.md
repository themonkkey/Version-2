# voyage-4-nano vs Cohere embed-english-v3.0

_Run 2026-07-29. Baseline: `PHASE1_BASELINE.md`. Scripts: `embed_voyage.py`, `eval_voyage.py`.
Per-prompt log: `voyage_results.jsonl`._

## Verdict: adopt

Pre-registered decision rule was "adopt only if recall@10 holds or improves". It improved by
**7.2 points**, and the direction is positive at every cutoff.

| | Cohere v3 | voyage-4-nano | gained | lost | McNemar p |
| --- | --- | --- | --- | --- | --- |
| recall@1 | 16.1% | **22.8%** | 21 | 9 | 0.043 |
| recall@3 | 25.6% | **31.7%** | 24 | 13 | 0.099 |
| recall@5 | 31.7% | **40.6%** | 29 | 13 | 0.020 |
| **recall@10** | **40.0%** | **47.2%** | 30 | 17 | 0.079 |
| doc-level@10 | 74% | 69% | — | — | — |

recall@10 = 85/180 = 47.2%, CI [40.1, 54.5].

Only the embedding model changed. Same 59,388 chunks, same retrieval code, same 180
questions, same `dense_only` configuration (both hand-tuned rules off).

**Statistical honesty:** four cutoffs were tested. Bonferroni correction would push the two
nominally-significant results (p=0.020, p=0.043) above 0.05. So this is not a single
airtight significance claim. What supports adoption is the combination: consistent positive
direction at all four cutoffs, a pre-registered decision rule that is met, roughly twice as
many prompts gained as lost at every cutoff, and decisive non-accuracy advantages below.

## By stratum (recall@10)

| stratum | Cohere | voyage | change | doc-level change |
| --- | --- | --- | --- | --- |
| training_case | 27% | **67%** | **+40** | 27% -> 67% |
| method_paraphrase | 32% | **45%** | +13 | 70% -> 62% |
| ambiguous_mandal | 25% | **35%** | +10 | 95% -> 85% |
| district_profile | 60% | **65%** | +5 | 60% -> 65% |
| vision_specific | 56% | 58% | +2 | 96% -> 84% |
| numeric_table | 32% | 28% | **-4** | 70% -> 55% |

**training_case went from worst stratum to best.** It was failing at the *document* level
(27%) under Cohere, which Phase 1 flagged as suspicious because case studies are the only
folder receiving the 4x repeated keyword block at `ingest.py:166`. voyage appears far less
distracted by that keyword stuffing.

**numeric_table is the one regression**, and it is the table-heavy stratum -- consistent
with the pilot finding that tabular content is genuinely hard and not fixed by any change
tried so far.

## The doc-level drop is real and worth understanding

Chunk-level recall rose (40% -> 47%) while document-level recall fell (74% -> 69%). The two
models fail differently:

- **Cohere** lands in the right document often but on the wrong page -- Phase 1's central
  finding, 34 points trapped between doc-level and chunk-level.
- **voyage** picks the exact right chunk more often, but when it misses it misses the
  document entirely.

For answering questions, chunk-level is what matters -- that is the text the LLM receives.
But it means the reranker's expected payoff is now smaller: there is less doc-level headroom
sitting unconverted. Worth re-measuring before spending on it.

## Non-accuracy advantages (the larger part of the case)

- **No API key, no quota, no monthly ceiling.** This is what took the deployed app down.
  The failure mode stops existing.
- **32,768-token context.** 18.4% of chunks exceeded Cohere v3's 512-token cap and were
  silently truncated -- the worst embedded from ~29% of their text. That is now impossible.
- **Apache 2.0**, open weights. No procurement conversation for a government deployment.
- **Query latency 75-117 ms on CPU**, measured. Acceptable for a chatbot.
- 1024 dimensions, so the index footprint is unchanged.

## A harness bug worth recording

The first scoring run returned **0.0% recall (0/180)**. That was not the model -- it was
`eval_voyage.py` importing helpers from `run_hard_retrieval`, whose module body
monkeypatches `embeddings.embed_query` with a Cohere key-rotating function backed by
`query_emb_cache.pkl`. Every query silently returned a *cached Cohere vector* scored against
a *voyage index*. Two unrelated vector spaces; the two query vectors had cosine 0.065.

It produced no error -- just plausible-looking zeros. Fixed by restoring `embed_query` after
the import, with an assertion on the active provider. The lesson: a side-effectful import
can invalidate an entire experiment silently.

## Build notes

- 59,388 chunks embedded locally, ~227 min total on CPU (4 threads, batch 16).
- **Length-sorted batching was essential**: batches pad to their longest member, so mixing a
  300-char chunk with a 7,000-char one wastes most of the compute. Sorting took throughput
  from 1 chunk/s to 30-100 chunks/s on short chunks. Attention is quadratic in sequence
  length, so the gain far exceeded the 54% predicted by a linear char-slot model.
- **MPS was slower than CPU** (2 vs 3 chunks/s) and roughly doubled memory pressure. Apple
  silicon's GPU shares the same 16 GB rather than adding capacity. Use CPU.
- Index verified before scoring: all norms 1.0, no NaN, and re-embedding four scattered
  chunks reproduced their stored rows at cosine 1.0000 (confirming the length-sort was
  correctly undone).

## Next

1. **Swap the app to voyage.** Set `EMBED_PROVIDER=voyage_local`, ship `voyage_out/`.
2. **Re-certify end-to-end** on `gold_prompts.jsonl` (450 prompts) and `build_stress.py`
   before deploying -- retrieval improving does not guarantee answer quality holds.
3. **Re-measure the reranker's expected value** given doc-level headroom shrank.
4. Deploy to Hugging Face Spaces (Streamlit Cloud cannot hold the model).
