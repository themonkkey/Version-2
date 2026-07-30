# End-to-end certification: voyage-4-nano vs Cohere

_2026-07-30. Same harness, same seed, same 120 prompts, Haiku answering, Sonnet judging.
Logs: `bench_log_20260730_110928.jsonl` (voyage), `bench_log_20260730_114148.jsonl` (Cohere)._

## Verdict: voyage passes. Ship it.

Paired comparison on identical prompts:

| | Cohere | voyage | gained | lost | p |
| --- | --- | --- | --- | --- | --- |
| **Numeric** | 79/80 = 98.8% | **80/80 = 100.0%** | 1 | 0 | 1.00 |
| **Conceptual** | 19/40 = 47.5% | **22/40 = 55.0%** | 5 | 2 | 0.45 |
| **Overall** | 98/120 = 81.7% | **102/120 = 85.0%** | 6 | 2 | 0.29 |

Voyage is better or equal on every layer, gains outnumber losses 3:1, and **no layer
regressed**. Nothing reaches significance at n=120, so this is "no evidence of harm plus a
consistent positive direction" rather than a proven improvement — which, combined with the
retrieval result (+7.2 points recall@10) and the operational wins, is enough to adopt.

The `numeric_table` regression seen in retrieval (32% → 28%) **did not propagate to answer
quality**: numeric went 98.8% → 100%. That was the specific risk flagged before this run and
it did not materialise.

## The important secondary finding: the documented 90% is not reproducible

`STATUS_2026-07-28.md` reports **"Conceptual reasoning (clean context) 90% (27/30)"**.

Under random sampling from the gold set, conceptual scores **47.5% on Cohere** and **55.0%
on voyage**. Both models, same harness, n=40.

**The 90% figure is not wrong, but it is not a general claim.** The "(clean context)"
qualifier matters: it was measured on a curated subset of 30 prompts under favourable
retrieval conditions. Quoted without that qualifier — in a deck, a report, or to officials —
it materially overstates conceptual performance on the questions officers will actually ask.

The defensible headline numbers are:

- **Numeric factual: 100%** (80/80) — genuinely excellent, and the bulk of real usage
- **Conceptual reasoning: ~55%** on random sampling
- **Retrieval: 100%** on the saturated legacy metric, **47.2% recall@10** on the hard set

This is the single most consequential thing in this document. Anyone presenting this system
should use 55%, not 90%, for open-ended reasoning questions.

## Where conceptual actually fails (voyage run)

| stratum | score |
| --- | --- |
| ComparativeAdvantage | 13/18 = 72% |
| Methodology | 9/15 = 60% |
| DataInterpretation | 0/5 = 0% |
| Intervention | 0/2 = 0% |

Error distribution across all 120: 7 incomplete, 5 wrong_specificity, 3 missing_content,
**2 fabrication**, 1 not_retrieved.

`DataInterpretation` and `Intervention` fail completely on both models. These are
open-ended reasoning prompts ("a district has the highest per-capita GSDP but below-average
literacy — interpret") rather than lookups. They are not retrieval failures; the system is
being asked to reason rather than cite, which this architecture is not built for.

**Two fabrications (1.7%)** is above the previously documented "<1%" and worth watching in
production, though at n=120 the difference is not meaningful.

## What this decides

1. **Voyage ships.** Better retrieval, better or equal answers, no API key, no quota, 32k
   context. The failure that took production down twice stops existing.
2. **A host with ~2.3 GB RAM is now genuinely needed** — Streamlit Community Cloud cannot
   run it. Oracle Always Free (India, 24 GB, ₹0) first; E2E C3 (Rs 2,263/mo) as fallback.
3. **Correct the 90% claim** wherever it appears before this is shown to officials.
4. **Consider scoping expectations** for open-ended interpretation questions, or routing
   them to a different prompt — 0/5 and 0/2 are not fixable by better retrieval.

## Reproduce

```bash
EMBED_PROVIDER=voyage_local EMBED_DEVICE=cpu CENSUS_N=200 venv/bin/python run_bench.py 120 sonnet haiku
EMBED_PROVIDER=cohere            CENSUS_N=200 venv/bin/python run_bench.py 120 sonnet haiku
```

`run_bench.py` now guards its Cohere key-rotating cache behind a provider check — without
that guard it silently scores cached Cohere vectors against whatever index is loaded,
producing plausible nonsense rather than an error.
