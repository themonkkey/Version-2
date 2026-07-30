# Pilot result — table serialization did not improve retrieval

_Run 2026-07-28. Baseline: `PHASE1_BASELINE.md`. Scripts: `ingest_v2.py`, `pilot_tables.py`,
`eval_pilot.py`. Per-prompt log: `pilot_results.jsonl`._

## Verdict

**Hypothesis not supported. Do not run the full-corpus rebuild on this evidence.**

127 gold documents were re-extracted with header-bound tables and enforced size caps,
re-embedded with the same Cohere model, and spliced into the index. Same 180 questions,
same metric, same retrieval code.

| | baseline | pilot | McNemar p |
| --- | --- | --- | --- |
| recall@1 | 16.1% | 15.0% | 0.79 |
| recall@3 | 25.6% | 23.9% | 0.63 |
| recall@5 | 31.7% | 29.4% | 0.52 |
| **recall@10** | **40.0%** | **37.8%** | **0.56** |
| doc-level recall@10 | 74% | 78% | 0.09 |

Nothing reaches significance. The headline moved slightly **down**.

## The prediction that failed

Phase 1 found table-heavy chunks over-represented in failures (60% of right-doc/wrong-page
failures, 67% of wrong-document failures, vs 43% of successes) and concluded tables were the
lever. Intervening on exactly that did not produce the gain.

Worse, the stratum the fix targeted moved the wrong way:

| stratum | baseline R@10 | pilot R@10 | gained | lost | p |
| --- | --- | --- | --- | --- | --- |
| numeric_table | 32% | 20% | 1 | 6 | 0.125 |
| table-heavy strata combined | 44.7% | 37.6% | — | — | — |

Not significant at n=40, so this is "no evidence of benefit" rather than proven harm. But
there is certainly no gain, and the direction is consistently negative.

**The correlation was real and the causal inference from it was wrong.** Table-heavy chunks
fail more often, but making their headers explicit did not fix them.

## What did move

- **Doc-level recall@10: 74% → 78%** (gained 10, lost 3, p=0.09). The clearest signal in the
  run, and in the expected direction: better chunking makes the right *document* easier to
  find.
- **method_paraphrase R@10: 32% → 38%**, docR@10 70% → 80% (p=0.79, not significant).
  Consistent with the truncation fix — methodology was the most oversized folder (87% of its
  chunks over cap), so it had the most to gain from enforced size limits.
- **Truncation in the rebuilt documents fell from 18.4% to 5.5%.**

## Two flaws in this pilot, both mine

**1. Granularity confound.** The rebuilt documents produce **5.81 chunks per gold page vs
3.21 in the baseline** — 1.8x more. Total index grew 59,388 → 65,087. Each page's content is
now spread across more vectors, and sibling chunks from the same page compete for the same
top-k slots. So chunk-level recall was measured under harder conditions in the pilot, and the
-2.2 point headline is not a like-for-like comparison. Doc-level recall, which is immune to
this, went up.

**2. Two variables changed at once.** Size-cap enforcement and table serialization shipped
together, so their effects cannot be separated. The evidence weakly suggests they pulled in
opposite directions — size caps helped methodology, table serialization hurt numeric tables —
but this run cannot prove that. It should have been two runs.

## Why table serialization may have backfired

Plausible, untested:

- **Noisy labels are worse than no labels.** pdfplumber drifts on wide sparse tables:
  `Status (Proposed/Ongoing): 15531` assigns a value to the wrong column. A confidently wrong
  header may mislead the embedding more than a bare number did.
- **Cropping removed signal.** Table regions are cut from the prose before extraction, so raw
  figures no longer appear in the surrounding narrative — which may be what matched
  figure-seeking queries before.
- **Repetition dilutes.** Serialized rows repeat the header for every cell, so a chunk's
  vector is pulled toward header vocabulary and away from its distinguishing content.

## What to do instead

**Do not rebuild the corpus.** The 2.8 GB re-ingest is not justified by this result, and that
is exactly what the pilot was for. Docling, LlamaParse and vision-LLM parsing are all
premature for the same reason — they are better ways to do a thing that did not help.

**Add the reranker.** Doc-level recall is 74-78%, chunk-level is 38-40%. Reranking converts
document-level hits into chunk-level hits by rescoring candidates already retrieved. That
gap is the largest measured, it is stable across both runs, and closing it requires no
corpus change. This was already the Phase 2 recommendation and this result strengthens it.

**Optional, cheap:** a single-variable rerun with size caps only and no table serialization,
to separate the two effects. Roughly an hour and a few cents. Worth doing only if you intend
to revisit extraction later; not on the critical path.

## Reproduce

```bash
./venv/bin/python pilot_tables.py && ./venv/bin/python eval_pilot.py
```
