# Experiments: MMR diversity and query routing

_2026-07-30. Script: `exp_mmr_routing.py`. Baseline: voyage index, 46.7% recall@10 on the
180-prompt hard set._

**Outcomes: MMR rejected. Hard routing rejected. Soft routing promising but contaminated by
overfitting. And a real production bug found by accident — now fixed.**

Note the baseline here is 46.7%, not the 47.2% in `VOYAGE_RESULT.md`. This script scores raw
top-k over the full index without `app.retrieve`'s neighbour expansion, so it is a slightly
simplified pipeline. All configs share that same baseline, so comparisons within this
document are valid; do not compare these numbers directly to `eval_voyage.py` output.

---

## The accidental finding: `detect_district` matched substrings — FIXED

While debugging why routing never fired, the router reported district `Ntr` for:

> "What determines how insurance sector **contributions** are divided among states?"

`detect_district` did a bare `if alias in query.lower()`. The alias `ntr` matches inside
**co-ntr-ibutions**, **co-ntr-ibuting**, **cou-ntr-y**. Other short aliases at risk: `asr`,
`eluru`, `vizag`.

**Impact on the hard set: 16 of 180 prompts (9%) detected the wrong district.**

This was live in production and worse than a mis-label: a detected district triggers the
force-injection at `app.py:196`, which inserts that district's chunks **at score 1.0**,
above everything the embeddings ranked. A false match doesn't just add noise, it actively
displaces the correct answer from the top of the list.

**Fixed** — `detect_district` now matches on word boundaries, longest alias first (so
"east godavari" still beats "godavari"):

| | before | after |
| --- | --- | --- |
| wrong district detected | 16 | **5** |
| correct district detected | 45 | 45 |

Legitimate detections are unaffected — Anakapalle, NTR-as-a-word, and East Godavari all
still resolve correctly. This fix stands on its own merit and is independent of both
experiments below.

---

## 1. MMR (maximal marginal relevance) — REJECTED

Re-rank the top 50 by `lam*sim(q,d) - (1-lam)*max sim(d, selected)`, penalising chunks
similar to those already picked.

| config | recall@10 | gained | lost | p |
| --- | --- | --- | --- | --- |
| baseline | 46.7% | — | — | — |
| mmr, lam=0.7 | 42.8% | 9 | 16 | 0.23 |
| **mmr, lam=0.5** | **35.6%** | 10 | **30** | **0.0022** |

**Harmful, with a clear dose-response**: more diversity pressure (lower lambda) makes it
monotonically worse, and lam=0.5 is significantly worse. A dose-response relationship is
strong evidence this is real rather than noise.

**Why the reasoning was wrong.** The table pilot showed sibling chunks from the same page
crowding top-k, and MMR suppresses near-duplicates — so it looked well-targeted. But our
ground truth *is* a specific page, and the chunks most similar to a correct chunk are its
own neighbours, which are frequently also correct or adjacent to the answer. MMR
systematically pushes away exactly the material we want. Diversity is the wrong objective
for single-fact lookup; it suits exploratory or summarisation queries.

**Do not revisit** unless the task changes to multi-document synthesis.

---

## 2. Hard routing (methodology sub-index) — REJECTED

Classify the query; if methodology, search only the 253 methodology + 416 training chunks
instead of all 59,388.

Router accuracy after fixing its own regex bug: **88%** — 26 correct, 8 false positives,
14 missed.

| | recall@10 | gained | lost | p |
| --- | --- | --- | --- | --- |
| baseline | 46.7% | — | — | — |
| hard routing | 46.1% | 3 | 4 | 1.00 |
| *method_paraphrase stratum* | *42% → 50%* | | | |

**The mechanism works; the classifier is not good enough.** Routing lifts its target
stratum by 8 points, but each of the 8 false positives loses that prompt *entirely* — the
gold chunk isn't even a candidate. Gains and losses cancel exactly.

---

## 3. Soft routing (score boost) — PROMISING, NOT ADOPTABLE YET

Same classifier, but instead of restricting the candidate set, add a constant to methodology
chunks' similarity. A false positive then costs a little rank rather than the whole answer.

| config | recall@10 | gained | lost | p | method_paraphrase |
| --- | --- | --- | --- | --- | --- |
| baseline | 46.7% | — | — | — | 42% |
| soft boost +0.05 | 47.8% | 2 | **0** | 0.50 | 48% |
| **soft boost +0.10** | **48.3%** | 3 | **0** | 0.25 | **50%** |

**`lost = 0` is the meaningful result**, more than the +1.6 points. No prompt was made worse
at either boost level, which is exactly the asymmetry the design predicted. It is a safe
change whose upside is small but whose downside appears to be nil.

### The reason it is not adoptable: I overfit the classifier

**Own this before acting on the number.** After the first run showed the router firing on
only 6 of 180 prompts, I inspected *which prompts it missed from the evaluation set* and
added terms to catch them — including `sector contribution` and `divided among states`,
which were lifted almost verbatim from missed test prompts.

That tunes the classifier on the same data used to score it. The +8 points on
`method_paraphrase` is therefore partly memorisation, and the true out-of-sample gain is
unknown and smaller.

**To make this adoptable:**
1. Rewrite `METHOD_TERMS` from domain knowledge alone, without looking at any failure from
   the 180-prompt set; or
2. Generate a fresh held-out set with `gen_hard_retrieval.py` (different random seed) and
   score the existing classifier on it cold.

Option 2 is cleaner and costs about an hour. Until one of them is done, treat soft routing
as an untested hypothesis with a promising shape.

---

## Actions

1. **Keep the `detect_district` fix.** Independent of both experiments, addresses a live
   production bug, and verified not to regress legitimate detections.
2. **Drop MMR.** Rejected on a significant dose-response result.
3. **Drop hard routing.** Mechanism sound, classifier too lossy.
4. **Park soft routing** pending a clean held-out evaluation. Do not ship on the current
   number.

## Method note

Two of the three experiments failed, and the most valuable output was a bug found while
debugging one of them. That is the expected yield rate — it is why the benchmark exists, and
why the discipline of scoring before adopting keeps paying. The one thing that would have
invalidated all of this quietly is the overfitting in §3, which is why it is written down
rather than smoothed over.
