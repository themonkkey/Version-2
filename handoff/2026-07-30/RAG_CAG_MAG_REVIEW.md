# Notes: RAG vs CAG vs MAG (Naresh Edagotti / PracticAI carousel)

_2026-07-30. Summarised, then applied to this project's measured numbers._

**Verdict: RAG remains correct for us. CAG is impossible for the full corpus and blocked by
cost for the useful subset. MAG does not apply and carries privacy risk. But the carousel's
final "hybrid tiered" idea points at a genuinely good, cheap change we have not tried:
query routing.**

---

## The three paradigms, summarised

**Why augmentation exists:** LLMs are frozen at training cutoff and know nothing about your
data. Two failure modes — *static memory* (knowledge baked into weights) and *amnesia*
(forgetting between sessions).

### RAG — Retrieval-Augmented Generation
Embed query → vector DB cosine search → top-k chunks → prompt assembly → grounded answer.
Dynamic retrieval at query time from an external store.

- **Strengths:** scales to millions of docs, always the freshest version, source attribution,
  works across heterogeneous formats.
- **Weaknesses:** retrieval latency and complexity; retrieval failures cascade (wrong chunk =
  wrong answer); chunking breaks context across boundaries; multi-hop reasoning is hard.
- **When:** large corpus, varied queries, frequently updated docs.
- Frameworks: LangChain, LlamaIndex, Haystack.

### CAG — Cache-Augmented Generation
Load *all* documents into the context window at startup → precompute and save the KV cache
→ at query time append the query to the cached state and generate. No retrieval step.

- **Strengths:** low latency, no chunking errors (full docs in context), better multi-hop
  reasoning, much simpler architecture (no embedding pipeline, no vector DB).
- **Weaknesses:** bounded by context window; stale cache needs a full rebuild when knowledge
  changes; upfront KV precompute cost; not multi-tenant.
- **When:** stable, bounded knowledge base that fits in context.
- Frameworks: vLLM, HF Transformers, Anthropic prompt caching.

### MAG — Memory-Augmented Generation
Working memory + episodic/semantic retrieval → write important facts back to a memory store
→ retrieve for the same user next session.

- **Strengths:** true continuity, self-improving with use, per-user personalisation.
- **Weaknesses:** memory staleness (old memories contradict new facts), **privacy risk**
  (stores hold personal data), write-strategy complexity, highest infra complexity.
- **When:** long-running agents, personal assistants, multi-session systems.
- Frameworks: Mem0, Zep, MemGPT, LangGraph.

### The carousel's decision framework
1. **Corpus size** — fits in context → CAG; too large → RAG/MAG
2. **Change frequency** — stable for months → CAG; daily → RAG; evolves per user → MAG
3. **Multi-session** — users return → MAG; independent → RAG/CAG
4. **Priority** — speed → CAG; freshness → RAG; personalisation → MAG

Closing recommendation: *hybrid tiered — CAG for core identity + RAG for long-tail search.*

---

## Applied to Swarna Andhra

### Corpus size settles it

| folder | chunks | ~tokens |
| --- | --- | --- |
| vision_documents | 57,687 | **19.3M** |
| training | 416 | 116K |
| methodology | 253 | 112K |
| district_data | 786 | 108K |
| case_studies | 246 | 50K |
| **total** | **59,388** | **~19.7M** |

**19.7M tokens against a 128K-200K context window.** CAG for the whole corpus is off by two
orders of magnitude. Not a close call.

Running the framework: corpus far too large → RAG. Change frequency is low but irrelevant
given size. No user accounts, so multi-session does not apply. Priority is freshness and
citation → RAG. **The architecture we have is the right one.**

### CAG for methodology only — attractive, but blocked

The one place CAG is arithmetically possible is interesting because it targets a *measured*
weakness. Methodology is **253 chunks / ~112K tokens** — it fits in Haiku's 200K window, and
it is the most stable material in the corpus (GSVA estimation methodology does not change
monthly).

It is also underperforming: `method_paraphrase` scores **45% recall@10** even with voyage,
because 253 methodology chunks compete against 57,687 vision chunks for top-k. Preloading
methodology permanently into context would eliminate that competition entirely — no
retrieval step to fail.

**Why we cannot do it now:** 112K tokens per query. The current context is capped at 11
chunks / 900 chars precisely because Groq's free tier caps tokens per minute — see the
comment at `app.py:288`. 112K tokens per query is far beyond that. It would only become
viable on Claude with prompt caching, where cached input is heavily discounted, and even
then it is a real recurring cost rather than free.

**Status: designed, not viable under current constraints.** Revisit if the LLM moves to
Claude with prompt caching.

### The cheap version of the same idea — worth testing

The carousel's insight is that *different knowledge deserves different handling*. We can act
on that without CAG's cost:

**Route the query to a sub-index.** Methodology questions search only the 253 methodology
chunks; district/vision questions search the rest. A methodology query then competes against
253 candidates instead of 59,388 — capturing most of CAG's benefit for that stratum at
essentially zero cost.

This is a better fit for our constraints than either CAG or the district force-injection rule
we measured as net negative (p=0.0029 at R@1). Routing *filters* the candidate set and ranks
honestly within it, rather than injecting chunks at score 1.0 and crowding out the answer.

Testable on the existing hard set: `method_paraphrase` is 40 of the 180 prompts, so an
improvement there should be visible in the overall 47.2% baseline. Classification could start
as a keyword/heuristic router and only become a model call if that proves insufficient.

### MAG — no, and not just because of effort

No user accounts, stateless sessions, and officers asking independent factual questions. The
framework says RAG/CAG for that shape.

More importantly, the carousel itself flags **privacy risk** as a MAG weakness. For a
government tool, persisting per-official memory of what they asked about which district
creates a data-protection obligation with no offsetting benefit for factual lookup. Actively
avoid.

### The RAG weaknesses slide describes exactly what we measured

- *"Retrieval failures cascade (wrong chunk = wrong answer)"* — our recall@10 is 47.2%, so
  this is the dominant failure mode, and it is why the benchmark exists.
- *"Chunking breaks context across paragraph boundaries"* — tested directly. `ingest_v2.py`
  fixed the chunking and recall went **down** (40.0% → 37.8%, p=0.56). Real in general,
  not the binding constraint here.
- *"Multi-hop reasoning is hard across multiple retrievals"* — matches our cross-district
  comparison prompts, which require two documents in one context.
- *"Real failure: fails to synthesize 5 chunks for a full picture"* — this is our doc-level
  vs chunk-level gap in different words.

---

## Actions

1. **Test query routing** — methodology queries against a methodology-only index. Cheap, no
   re-embed, directly targets a measured 45% stratum. Score on the hard set vs 47.2%.
2. **Record CAG-for-methodology** as a designed option, blocked on moving to a
   prompt-caching LLM. Do not attempt on Groq.
3. **Rule out MAG** on privacy grounds, not just cost.
4. No change to the core architecture — RAG is confirmed correct by the framework's own
   criteria.

The carousel is a good conceptual map and its decision framework is sound. Applied honestly
to our numbers it mostly *confirms* the current design, which is a useful result: it means
the remaining gains are in retrieval quality, not in switching paradigms.
