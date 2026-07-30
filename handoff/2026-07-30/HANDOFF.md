# Session handoff — 2026-07-30

Written for whoever (or whichever Claude) picks this up next. Assumes no memory of the
session. Read this top to bottom before touching anything.

Repo: `~/swarna-andhra-chatbot` · Remote: `github.com/themonkkey/swarna-andhra-chatbot`
(public) · Local and remote both at commit `9f3d790`.

---

## 1. One-paragraph summary

The session set out to improve retrieval accuracy for the Swarna Andhra GVA assistant. The
first and most important thing built was a **benchmark the existing system could actually
fail** — the old gold set reported 100% retrieval and was therefore useless for measuring
change. With that in place, two plausible improvements were tested and **rejected on
evidence**, and one was **adopted**: replacing Cohere's hosted embeddings with a locally-run
open-weights model, `voyage-4-nano`, which improved recall@10 from 40.0% to 47.2% and
removes the API quota that has been taking the production app down. The voyage index is
built and verified but **not yet certified end-to-end and not deployed**.

---

## 2. The three results, with numbers

### 2.1 Baseline: the old benchmark was measuring the wrong thing

`PHASE1_BASELINE.md` has the detail. The existing gold benchmark reported **100% retrieval
(195/195)**, which is an artifact: every numeric gold prompt names a district, so
`detect_district` fires and `app.retrieve` force-injects that district's snapshot at score
1.0. The target figure is present in the context almost by construction. It measures the
forcing rule, not the retriever.

A new benchmark (`gen_hard_retrieval.py` → `hard_retrieval.jsonl`, 180 prompts) scores a hit
only when the retriever returns the **specific (source, page) chunk** the question was
written from. Questions are Haiku-generated from a known chunk and steered away from its
vocabulary; mean lexical overlap is 0.28, so keyword matching cannot pass.

**Baseline: recall@10 = 40.0%** (72/180), doc-level 74%.

Two findings fell out:

- **The two hand-tuned retrieval rules are net negative.** Disabling both raises R@1 from
  16.1% to 16%→... precisely: R@1 6%→16%, R@3 16%→26%, R@5 22%→32% (exact McNemar
  p=0.0029 / 0.0051 / 0.0051), and makes no difference at R@10 (p=0.83). They inject chunks
  at score 1.0/0.99, above anything the embeddings ranked, so when the injected chunk is not
  the answer it occupies the top slots. **Not yet removed** — see §6.
- **34 points sit between doc-level (74%) and chunk-level (40%) recall** — the right
  document, the wrong page.

### 2.2 Rejected: table serialization

`PILOT_TABLES_RESULT.md`. Hypothesis was that header-stripped tables caused the doc/chunk
gap (table-heavy chunks were 60% of those failures vs 43% of successes).

Built `ingest_v2.py` (header-bound table rows, enforced size caps), rebuilt the 127 gold
documents, re-embedded, re-scored. **recall@10 went 40.0% → 37.8%, p=0.56.** The stratum it
targeted, `numeric_table`, went **32% → 20%**.

**Correlation was real; the causal inference was wrong.** This saved a 2.8 GB corpus rebuild
and the $50-350 that Docling / LlamaParse / vision-LLM parsing would have cost. Do not
revisit extraction without new evidence.

Two flaws in that pilot, for the record: it changed two variables at once (size caps *and*
table serialization), and the rebuild produced 5.81 chunks per gold page vs 3.21 before, so
chunk-level recall was measured under harder conditions.

### 2.3 Adopted: voyage-4-nano

`VOYAGE_RESULT.md`. Local open-weights model replacing Cohere `embed-english-v3.0`.

| | Cohere | voyage | p |
| --- | --- | --- | --- |
| R@1 | 16.1% | 22.8% | 0.043 |
| R@5 | 31.7% | 40.6% | 0.020 |
| **R@10** | **40.0%** | **47.2%** | 0.079 |
| doc-level@10 | 74% | 69% | — |

Four cutoffs were tested, so Bonferroni would push the two nominally-significant results
above 0.05. Adoption rests on the combination: consistent direction, a pre-registered
decision rule ("adopt if recall@10 holds or improves") that is met, ~2x more prompts gained
than lost at every cutoff, and the non-accuracy wins below.

`training_case` went **27% → 67%** (worst stratum to best). `numeric_table` regressed
32% → 28%.

Note the doc-level *drop*: the two models fail differently. Cohere lands in the right
document on the wrong page; voyage nails the chunk or misses the document. **This shrinks
the expected payoff of a reranker** — re-measure before investing there.

Non-accuracy advantages, which are arguably the larger part of the case:
- **No API key, no quota.** This is the failure that keeps taking production down.
- **32,768-token context.** 18.4% of chunks exceeded Cohere v3's 512-token cap and were
  silently truncated (worst case embedded from ~29% of its text). Now impossible.
- Apache 2.0, 1024 dims (index footprint unchanged), 75-117 ms query latency on CPU.

---

## 3. Current state

### Deployed (Streamlit Community Cloud) — DOWN, fix ready
Runs **Cohere + Groq**, not voyage. It went down because Streamlit secrets contained
`COHERE_API_KEY` (singular) holding the **one exhausted key** of the nine tested.

Fix is ready and requires no code change:
1. `streamlit_secrets.toml` (gitignored, in repo root) holds **8 live keys** under
   `COHERE_API_KEYS` (plural) → ~8,000 calls/month, ~266 questions/day.
2. Paste its contents into Streamlit Secrets. Main file is **`app.py`** (not
   `streamlit_app.py` — that error was hit during the session).
3. The rotation logic that reads the plural form is now on GitHub (commit `76a1a20`),
   which it was not before this session.

### voyage build — works locally, NOT deployed, NOT certified
- Index at `voyage_out/` (531 MB, gitignored): 59,388 × 1024, verified — all norms 1.0, no
  NaN, and re-embedding four scattered chunks reproduced their stored rows at cosine 1.0000.
- End-to-end smoke test passes: correct answer with citations, 1.2 s via Groq.
- **Peak RAM measured: 2.29 GB** (model + index + one query).

### Hosting — unresolved, and this is the live blocker
**HF Spaces no longer has a free compute tier.** Static Spaces only; Gradio/Docker require
PRO. Streamlit isn't even offered as an SDK on the creation form any more. Earlier advice in
this session assumed the old free 16 GB tier and was wrong.

| Host | RAM | Fits 2.29 GB? | Cost |
| --- | --- | --- | --- |
| Streamlit Community Cloud | ~1 GB | No | free |
| Oracle E2.1.Micro (Always Free) | 1 GB | No | free |
| **Oracle Ampere A1 (Always Free)** | 24 GB | Yes | free |
| Hetzner CX22 | 4 GB | Yes | ~€4/mo |
| Railway | 8 GB | Yes | ~$5/mo (account exists, from BlackMantis) |
| HF Spaces PRO | — | Yes | ~$9/mo |

Free hosting and no-quota are now mutually exclusive. Oracle Ampere A1 is the only free
option that fits, and its capacity is frequently exhausted ("Out of host capacity"),
especially in Indian regions.

---

## 4. Files created or changed

### New — evaluation
| File | Purpose |
| --- | --- |
| `gen_hard_retrieval.py` | Generates the 180-prompt hard set (Haiku), filters >70% lexical overlap |
| `run_hard_retrieval.py` | Scores recall@k, 4 ablation configs, Wilson CIs |
| `hard_retrieval.jsonl` | The benchmark itself |
| `hard_retrieval_results.jsonl` | Baseline per-prompt results |
| `PHASE1_BASELINE.md` | Baseline writeup |

### New — table pilot (rejected)
`ingest_v2.py`, `pilot_tables.py`, `eval_pilot.py`, `pilot_results.jsonl`,
`PILOT_TABLES_RESULT.md`

### New — voyage (adopted)
`embed_voyage.py`, `eval_voyage.py`, `voyage_results.jsonl`, `VOYAGE_RESULT.md`,
`RESUME_EMBEDDING.md`

### New — deployment (untracked, not committed)
`hfspace/{README.md,requirements.txt,deploy.sh}` — written before discovering HF's free
tier is gone. `deploy.sh` is still reusable: point its remote at another host.
`deploy/vm_setup.sh` — provisions any Ubuntu VM (Oracle/Hetzner/Railway) end to end:
packages, venv, `transformers<5` pin, model warm-up, systemd service.

### Modified
- `embeddings.py` — added `EMBED_PROVIDER=voyage_local`. torch/sentence-transformers are
  imported **lazily** inside `_voyage_local_model()`, so the Cohere deploy path pulls no
  extra dependencies.
- `app.py` — three changes:
  1. `ABLATE_FORCE` / `ABLATE_RESCUE`, **default off**, so the benchmark can isolate the
     hand-tuned rules without changing production behaviour.
  2. Loads `voyage_out/` when `EMBED_PROVIDER=voyage_local`.
  3. **Raises on index/model mismatch.** See §5 — this guard exists for a reason.
- `.gitignore` — added `voyage_out/`, `pilot_*.pkl`, `pilot_index.npz`, `*.log`, `*_out.txt`,
  `streamlit_secrets.toml`, `.cohere_live_keys`. Without this the push would have failed:
  `voyage_out/` is 531 MB and GitHub rejects files over 100 MB.

---

## 5. Traps discovered — read this before debugging anything

**A side-effectful import invalidated an entire experiment, silently.** `eval_voyage.py`
imports helpers from `run_hard_retrieval`, whose *module body* monkeypatches
`embeddings.embed_query` with a Cohere key-rotating function backed by
`query_emb_cache.pkl`. Every voyage query silently returned a **cached Cohere vector**
scored against a **voyage index**. Result: **0.0% recall, no error.** The two query vectors
had cosine 0.065. Fixed by restoring `embed_query` after the import plus a provider
assertion, and by the `app.py` mismatch guard. **If you ever see implausibly bad retrieval,
check which provider actually produced the query vector first.**

**`transformers` 5.x cannot load voyage-4-nano.** Its remote code leaves `config_class` as
`None`, which 5.x rejects with an opaque `AttributeError: 'NoneType' object has no attribute
'__name__'`. Pin `transformers<5` (currently 4.57.6). This pin is in `deploy/vm_setup.sh`.

**MPS (GPU) is slower than CPU for this workload.** Measured: 2 chunks/s on MPS vs 3 on CPU,
and MPS roughly doubled memory pressure. Apple silicon's GPU shares the same 16 GB rather
than adding capacity; switching to MPS mid-run pushed swap to 91% and was reverted. **Use
`EMBED_DEVICE=cpu`.**

**Length-sorted batching is essential, not an optimisation.** Batches pad to their longest
member, so mixing a 300-char chunk with a 7,000-char one wastes most of the compute.
Sorting took throughput from 1 chunk/s to 30-100 chunks/s on short chunks. A linear
char-slot model predicted only 54% savings; the real gain was far larger because attention
is **quadratic** in sequence length. `embed_voyage.py` sorts, then inverts the permutation
before saving — that inversion is verified in the script and was independently checked by
re-embedding sample chunks.

**pdfplumber's table headers are fragmented across many rows.** One real table came back as
17 sparse columns with the header spread over rows 0-7 (`Total Land under` / `Cultivation` /
`No. of` / `Bore-` / `wells` each on its own row). Assuming row 0 is the header produces
garbage. `ingest_v2.py` reconstructs headers per column. Also: `outside_bbox` throws when a
table bbox exceeds the page by a rounding error, silently leaving tables uncropped —
`ingest_v2.py` clamps the box.

**Oracle Cloud opens ports in two places.** Its images ship a restrictive `iptables` ruleset
that ignores the VCN security list. Both must be configured or the app appears dead.

**Checking that a process exists is not checking that it works.** Twice during this session
a job was reported as running when only a shell wrapper survived (RSS 20 MB instead of
815 MB). Check RSS and log progress, not `pgrep`.

---

## 6. Open items, in priority order

1. **Restore production** (5 min, no code change): paste `streamlit_secrets.toml` into
   Streamlit Secrets, main file `app.py`. Free, unblocks officers today.
2. **Rotate the GitHub token.** `ghp_2AZi…` was pasted into the session chat and has write
   access to the repo. Revoke at github.com/settings/tokens. It was never written to
   `.git/config`. The nine Cohere keys were also pasted in chat — lower stakes, but rotate
   when convenient.
3. **Certify voyage end-to-end** — the gate before shipping it. `run_bench.py` over
   `gold_prompts.jsonl` (450 prompts) plus `build_stress.py`, Haiku answering / Sonnet
   judging, to compare against the existing 98.8% numeric / 90% conceptual / 96% stress.
   **`run_bench.py` needs adapting first** — it loads the Cohere index and monkeypatches
   `embed_query` (see §5). Retrieval improving does not guarantee answer quality holds, and
   `numeric_table` regressing is a specific reason to check.
4. **Decide hosting.** Oracle Ampere A1 if obtainable, else ~$5/mo Railway. `deploy/vm_setup.sh`
   handles either. The 300 MB `voyage_out/` must be `scp`'d — it is not in git.
5. **Remove the two hand-tuned rules?** Evidence says they cost ~10 points at R@1-5. But the
   hard set is structurally biased against them: it scores finding a *specific page*, while
   the rules serve *district-aggregate* queries — the shape officers actually ask most.
   **Gate on running the 450-prompt gold set with `ABLATE_FORCE=1`.** If retrieval holds
   there, remove; if it collapses, narrow them instead. Do not remove on the hard set alone.
6. **Re-measure the reranker's value.** It was the top recommendation before voyage, but
   voyage shrank doc-level headroom from 74% to 69%, which is exactly what a reranker
   converts. Needs a paid Cohere key.
7. **The repo is public** and contains corpus-derived index files. If any Andhra government
   material is meant to stay internal, that needs a decision.

---

## 7. Commands

```bash
# hard benchmark (all 4 ablation configs)
cd ~/swarna-andhra-chatbot && ./venv/bin/python run_hard_retrieval.py

# score the voyage index against the baseline
EMBED_DEVICE=cpu ./venv/bin/python eval_voyage.py

# rebuild the voyage index from scratch (~4 h CPU, resumable)
EMBED_DEVICE=cpu OMP_NUM_THREADS=4 VOYAGE_BATCH=16 nice -n 10 \
  ./venv/bin/python -u embed_voyage.py

# run the app locally on voyage
EMBED_PROVIDER=voyage_local EMBED_DEVICE=cpu LLM_PROVIDER=groq \
  ./venv/bin/streamlit run app.py

# provision a VM (run ON the VM)
bash deploy/vm_setup.sh
```

Env vars: `EMBED_PROVIDER` (`cohere` | `voyage_local`), `EMBED_DEVICE` (`cpu` — do not use
`mps`), `LLM_PROVIDER` (`groq` | `gemini` | `claude`), `VOYAGE_OUT` (index dir).

---

## 8. Judgement notes for whoever continues

**The benchmark is the asset, not the voyage index.** Everything useful this session came
from having a metric that could show a regression. Two well-reasoned ideas were killed by
it. Preserve that discipline: measure before adopting, fix the decision rule before seeing
results, and prefer a cheap pilot over a full rebuild.

**Three of my own conclusions were wrong mid-session and got corrected by data:** that
oversized chunks drove the doc/chunk gap (they didn't — median failing chunk was 1,514
chars, under the truncation limit); that tables were the lever (intervening produced
nothing); and that HF Spaces had a free 16 GB tier (it doesn't any more). Treat confident
claims here as provisional unless a number is attached.

**Do not touch the base system prompt.** Prior work established it as a local optimum —
three prompt edits each regressed accuracy on certification and were rejected. Nothing this
session changes that.
