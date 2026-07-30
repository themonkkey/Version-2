# Phase 05 — Post-launch

What to do once real officers are using it. This is where the remaining gains are — not in
further local tuning.

## Checklist

- [ ] Review logged queries weekly — what are officers actually asking?
- [ ] Build a benchmark set **from real queries**, replacing the synthetic 180
- [ ] Triage every thumbs-down; check whether it was retrieval or generation
- [ ] Track fabrication rate against the 1.7% certification figure
- [ ] Build the held-out benchmark set (guards against accumulated overfitting)
- [ ] Re-evaluate soft routing on that held-out set — currently overfit, not adoptable
- [ ] Re-measure the reranker's value (voyage shrank doc-level headroom 74% → 69%)
- [ ] Decide Haiku vs Groq on evidence once the Groq certification lands
- [ ] Drift monitoring — daily error rate, p-chart or EWMA (designed, never run)
- [ ] Refresh the corpus when new DDP/vision documents are published

## Challenges

**Local retrieval tuning has saturated.** Today: MMR rejected (significantly harmful),
table serialization rejected (flat), hard routing rejected (net zero), soft routing
contaminated by overfitting. Four attempts, no adoptable gain, one accidental bug fix.
Further tuning against synthetic prompts is low-value.

**The synthetic benchmark is partly spent.** It has now driven five decisions, and I tuned
a classifier against it, which erodes it further. Real query logs are a better foundation.

**Interpretive questions are an architectural gap, not a retrieval gap.**
`DataInterpretation` 0/5 and `Intervention` 0/2 on *both* models. No index fixes this.
Options: a separate prompt path for interpretive questions, or scope them out of the
tool's stated purpose.

**Corpus staleness.** DDP estimates get revised (SRE → FRE → FAE). When new books are
published, `ingest.py` and `embed_voyage.py` must be re-run. Budget ~4 hours; the embedding
resumes from checkpoints if interrupted.

**Do not touch the base system prompt.** Established as a local optimum — three prompt
edits each regressed accuracy on certification and were rejected.
