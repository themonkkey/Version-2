# Review: "RAG with LangChain" carousel vs what we measured

_2026-07-30. Assessing an Instagram RAG guide against this project's benchmark evidence._

**Summary: two ideas worth testing, one worth considering later, one that would actively
damage this corpus, and the rest already covered — usually by something stronger.**

The guide is a competent beginner introduction. This project is past the stage it addresses:
we have a 180-prompt benchmark with Wilson intervals, paired McNemar tests, ablation
switches, and pre-registered decision rules. Most of its advice is either already
implemented or was tested here and rejected on evidence.

---

## Worth testing

### 1. MMR (Maximal Marginal Relevance) — the one genuinely new idea

The guide mentions `search_type="mmr"` for diversity. **We have no diversity control at all**
— retrieval is pure cosine ranking (`grep mmr app.py` → nothing).

This matters because we have *measured* the failure it fixes. In the table pilot, the
rebuilt corpus produced **5.81 chunks per gold page vs 3.21 before**, and recall went
*down*: sibling chunks from the same page crowded each other out of top-k. MMR penalises
near-duplicate results, which is exactly that problem.

It also fits the voyage finding — doc-level recall fell to 69% while chunk-level rose, i.e.
voyage concentrates its hits. Diversity pressure could widen coverage without losing
precision.

**Cheap to test:** it's a reranking step over the existing similarity scores, no re-embed,
no corpus change. Score on the 180-prompt hard set against the 47.2% voyage baseline.
Rejected if it doesn't beat it.

### 2. `temperature=0` for factual answers

The guide says keep temperature at 0. **We run `temperature=0.2`** (`app.py:348`).

For a citation-grounded government tool, 0.2 buys nothing and adds variance. Worth a
controlled test — but note it must be certified, not just assumed: prior work on this
project found three plausible prompt improvements each *regressed* accuracy. Generation
settings deserve the same scepticism.

Test on the conceptual subset where the 90% figure was measured.

---

## Worth considering later, not now

### FAISS instead of a raw numpy matrix

We do a full dot product over a 59,388 × 1024 matrix per query. FAISS would index it
properly.

**Not a bottleneck today** — that matmul is tens of milliseconds against a 1.2 s LLM call.
But FAISS brings **metadata filtering**, which is interesting for a specific reason: it
could replace the district force-injection rule (`app.py:196`) that we measured as **net
negative** (p=0.0029 at R@1). Instead of injecting a district's chunks at score 1.0 and
crowding out the real answer, you would *filter* the candidate set by district and rank
honestly within it.

That's a principled fix for a hack we have evidence against. Worth doing when the retrieval
layer is next touched, not as a standalone task.

---

## Already covered, by something stronger

| Guide says | What we have |
| --- | --- |
| `RecursiveCharacterTextSplitter` | `ingest_v2.py` does paragraph → sentence → hard split with enforced caps. Also: **we measured that re-chunking did not help** (40.0% → 37.8%, p=0.56). |
| all-mpnet / MiniLM / ada-002 embeddings | voyage-4-nano, measured at 47.2% vs Cohere's 40.0%. MiniLM is 384-dim/512-context — a downgrade. ada-002 is superseded. |
| `QAEvalChain`, faithfulness, relevance | `run_bench.py` + `run_hard_retrieval.py`: objective + LLM-judge grading, Wilson CIs, exact McNemar, four ablation configs. Substantially more rigorous. |
| Caching embeddings | `query_emb_cache.pkl` already does this. |
| PyPDFLoader | We use pdfplumber, which is **better at tables** — pypdf has no table extraction. Switching would lose ground. |

---

## Would actively damage this corpus

### The preprocessing regex

```python
text = re.sub(r'[^\w\s\.\,\!\?]', '', text)   # "Remove special characters"
```

**Do not apply this.** It strips every character that is not a word, space, or basic
punctuation. On an economic corpus that deletes:

- `%` → growth rates become meaningless (`9.23%` → `9.23`)
- `₹` and `Rs.` symbols → currency context lost
- `-` → `2028-29` becomes `202829`, breaking every fiscal year
- `/` → `Rs./person`, `kg/ha` units destroyed
- `()` → `(SRE)`, `(FRE)`, `(FAE)` revision-stage markers lost

Those are precisely the tokens our numeric benchmark depends on. This is good advice for
scraped prose and wrong for structured government data.

The same slide's `re.sub(r'Page \d+', '', text)` is reasonable and we effectively do it via
boilerplate stripping.

---

## Doesn't apply

**LangChain itself.** It's a wrapper, not a capability — `CohereEmbeddings`,
`HuggingFaceEmbeddings` etc. call the same APIs we already call directly. Adopting it now
means rewriting a working, benchmarked pipeline for no measured gain, and adding a
dependency whose abstractions would make the ablation switches harder to implement, not
easier.

**`chunk_size=300` "is optimal".** Presented without evidence. Our chunks are 800-2,000
chars by folder, tuned to content type. 300 characters would fragment a district data table
across many chunks. More importantly, **we tested chunking changes on this corpus and they
did not help** — a generic optimum from a slide does not override a measurement on your own
data.

**`RetrievalQA` chain types (stuff / map_reduce / refine).** `RetrievalQA` is deprecated in
current LangChain. `map_reduce`/`refine` multiply LLM calls per query, which conflicts with
the Groq token-per-minute cap that motivated our context truncation in the first place.

**BLEU / ROUGE / BERTScore.** N-gram overlap measures surface similarity, not factual
correctness. For "what is the GDDP of Anakapalle", an answer can score well on ROUGE and
still state the wrong number. Our LLM-judge plus objective numeric matching is strictly
better suited. Adopting these would be a downgrade.

---

## Actions

1. **Test MMR** on the hard set vs the 47.2% voyage baseline. Cheap, no re-embed.
2. **Test `temperature=0`** vs 0.2 on the conceptual subset. One-line change, must be
   certified.
3. **Note FAISS metadata filtering** as the principled replacement for the district-forcing
   rule, for whenever retrieval is next reworked.
4. Ignore everything else. Explicitly do **not** apply the preprocessing regex.

The one broader point worth keeping: the guide's own summary says "Evaluation is crucial for
production systems" and "Start simple, then optimize based on results." That is the one
piece of advice this project already follows harder than the guide does — and it is why most
of the rest of the guide is not actionable here.
