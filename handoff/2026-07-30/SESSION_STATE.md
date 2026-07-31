# Swarna Andhra GVA Assistant — full project state

**Last updated: 2026-07-30.** Written so another Claude (or person) can pick this up cold.
Assumes no memory of any prior session. Read top to bottom before touching anything.

Repo: `~/swarna-andhra-chatbot` · Remote: `github.com/themonkkey/swarna-andhra-chatbot`
(**public**) · Owner: Aryan Singh, Pahlé India Foundation (PIF).

---

## 0. What this system is

A RAG chatbot answering questions about Andhra Pradesh district economic data (GVA / GDDP /
GSDP) for **state government officers**. Streamlit UI, local embeddings, hosted LLM.

Pipeline: `extract → chunk → embed → index → retrieve → build context → LLM answer`.

Corpus: 59,388 chunks. 97% is `vision_documents`; `methodology` is only 253 chunks (0.4%).
Source PDFs/DOCX/PPTX live in `corpus_files/` (2.8 GB, **not** deployed — only the index is).

---

## 1. Current status at a glance

| Area | State |
| --- | --- |
| Retrieval | voyage-4-nano, 512-dim, recall@10 ≈ 47% — **adopted, working** |
| Answering model | **Decision made: Gemini 3.6 Flash** (see §4) — not yet wired as default |
| Production | **DOWN.** Streamlit Cloud deploy is stale (Cohere + Groq) |
| Hosting | **Unresolved.** Oracle Always Free preferred, capacity uncertain |
| Certification | Numeric solid; conceptual ~55% on the 120-prompt set |
| Blocking bugs | 2 open, both in `app.py` — see §6 |

---

## 2. The single most important finding (2026-07-30)

**Repeat every benchmark run. A single run cannot rank models, and stability is a separate
axis from accuracy.**

Each model answered the **same 30 prompts with byte-identical retrieved context**, graded by
the same judge. Only the answering LLM varied.

```
model                    runs                total   unstable   ₹/month
gemini 3.6 flash    30/30  30/30  17/17*     77/77       0       1,719
gemini 3.5 flash-lite      29/30  28/30      57/60       1         423
claude haiku 4.5    29/30  26/30  30/30      85/90       4       1,146
groq llama-3.3-70b         28/30  30/30      58/60       2     Dev Tier
                                      *stopped at 17, free keys spent
```

**Haiku swings 26–30 on identical input.** Its own range is wider than the gap between any
two models, so one run of each told us nothing. This is why run 1 alone was misleading:
Haiku's first run (29/30) looked stable; it took the second to expose the wobble.

**Gemini 3.6 Flash produced 77/77 across three runs — zero misses, zero instability.** Its
Wilson lower bound is ~95%, so the true rate could be 95% rather than 100%; a model at the
ceiling cannot show downward variance without first producing a miss.

### The root cause of nearly every failure is a DATA problem, not a model problem

**Across all four models and ten runs, every single failure landed on just five prompts —
and four of them are the same question shape:** *"Which sectors give <district> its strongest
comparative advantage?"*

The reason is in `district_data/<District>_Snapshot.txt`. Each snapshot contains **two
overlapping lists holding the same sectors in different orders**:

```
Top sectors by contribution to district GVA (comparative advantage):   <- ordered by share %
  Agriculture · Horticulture · Electricity,Gas,Water · Other Services · Construction

Best statewide ranks (sectors where Kurnool leads other districts):    <- ordered by rank
  Agriculture · Horticulture · Other Services · Electricity,Gas,Water · Transport
```

**Every wrong answer is the top three of the second list.** Both lists are plausibly
"comparative advantage", so the model has to guess. Confirmed identical on all three failing
districts:

| District | List 1 (by share) | List 2 (by rank) — what models wrongly returned |
| --- | --- | --- |
| Ananthapuramu | Railways, Horticulture, **E/G/W** | Horticulture, Railways, **Live stock** |
| Kurnool | Agriculture, Horticulture, **E/G/W** | Agriculture, Horticulture, **Other Services** |
| Polavaram | Forestry, **Public Admn.**, Horticulture | Forestry, **Fishing**, E/G/W |

### FIXED — and it closed the entire quality gap

`parse_district_data.py` now labels the two sections unambiguously: the share-ordered list is
marked *"THIS is the district's comparative advantage ranking"*, and the rank-ordered list is
marked *"NOT the comparative-advantage ordering; use the section above for that"*.

Result on the cheapest model, same 30 prompts, two runs each side:

```
Gemini 3.5 Flash-Lite (₹423/mo)
  BEFORE fix:  29/30 + 28/30 = 57/60
  AFTER  fix:  30/30 + 30/30 = 60/60

  Kurnool        [X X] -> [O O]   <- failed BOTH prior runs; now correct in both
  Ananthapuramu  [O X] -> [O O]
```

**Kurnool is the causal evidence.** It was a *reproducible* failure, not a coin flip, and a
targeted data change eliminated it in both post-fix runs.

**Consequence for the model decision: the premium is now unjustified.** Gemini 3.6 Flash
scored 77/77 only because it happened to resolve the ambiguity correctly. With the ambiguity
gone, Flash-Lite matches it at **one quarter of the price** — ₹423 vs ₹1,719/month, a saving
of **₹15,552/year** from a two-line header change.

**Outstanding:** the 29 snapshot chunks were patched in place in `voyage_out_512/
voyage_chunks.pkl` (backup at `voyage_chunks.pkl.bak`), so their *stored embeddings still
encode the old header text*. This is harmless for the ranking questions — those chunks are
force-injected by district match, not vector similarity — but the 29 chunks should be
re-embedded properly before production. Regenerating snapshots from source requires
`parse_district_data.py` and the district XLSX.

The remaining non-ranking failures were `A district has the highest per-capita GSDP…`
(Haiku, Groq — answer completeness) and `If Nominal GSDP growth…` (Haiku — one outright
refusal).

### Where the instability lives

```
prompt                              run1 run2 run3
Polavaram comparative advantage       X    X    O
Per-capita GSDP vs literacy           O    X    O
Kurnool comparative advantage         O    X    O
Real vs nominal growth                O    X    O
```

- **26 of 30 prompts were correct in all three runs.**
- **All 20 numeric prompts were correct in every run** — figures are deterministic.
- **4 of the 10 conceptual prompts are non-deterministic** — 40% of interpretive questions.

The worst single case: "Real vs nominal growth" returned a precise correct answer (3%, exact
2.75%) in runs 1 and 3, and in run 2 flatly refused — *"the context does not contain
information"* — on identical input.

### What follows from this

1. **Stop model-shopping.** All three candidates are equivalent within noise.
2. **Choose on cost and operations**, not on scores.
3. **Officers will see inconsistent answers** on interpretive questions. This belongs in the
   user-facing note, and makes the feedback control more important, not less.
4. **Existing certification numbers carry more uncertainty than stated.** Every headline
   figure came from a single run. Wilson intervals assume a fixed underlying rate; we have
   now shown the rate is not fixed.

---

## 3. The quota disaster, and why it matters methodologically

Earlier the same day, a certification run reported **Groq at 13.3%** and it was recorded as a
model-quality result. It measured nothing:

- **64 answers were HTTP 429 rate-limit strings**, scored as wrong answers.
- **40 judge calls returned `You've hit your session limit`** (the judge shells to
  `claude -p`, which hit the Claude Code subscription cap), scored as `parse_error` = wrong.

Re-running with a working harness gave **Groq 28/30 = 93.3%**. The model was never bad.

**Rule now enforced in code: quota exhaustion must abort loudly, never be graded.**
See `QUOTA_MARKERS` / `QuotaExhausted` in `bakeoff.py`.

### Free-tier ceilings — all three blocked measurement

| Tier | Limit | Notes |
| --- | --- | --- |
| Groq free | **100,000 tokens/day** (TPD) | ≈ 25 prompts/day at 4,034 tok/query |
| Gemini free | **5 req/min AND 20 req/day** per model per project | RPD is the real wall |
| Claude Code subscription | session limit | reset ~2.5h; killed both bot and judge |

Finishing one 30-prompt run took **4 Groq keys across 2 accounts** and **6 Gemini keys**.

**Gemini error trap:** the 429 says `Please retry in 6.6s` and `retryDelay: 6s`, while the
actual quota is `GenerateRequestsPerDayPerProjectPerModel-FreeTier`, `quotaValue: 20`.
Obeying `retryDelay` loops into the same 429 forever. **Classify on `quotaId`, not
`retryDelay`** — this is implemented in `bakeoff.py`.

Production needs **100 queries/day**. No free tier can serve that. Paying is not optional.

---

## 4. Model decision

### Verified pricing (Google official page + Anthropic, checked 2026-07-30)

Computed on the **measured** workload: 2,840 input + ~300 output tokens per query, 100
queries/day, ₹88/USD.

| Model | $/1M in | $/1M out | ₹/month | Score | Stability |
| --- | --- | --- | --- | --- | --- |
| Gemini 3.6 Flash | 1.50 | 7.50 | **₹1,719** | 77/77 (3 runs) | 0 unstable |
| Claude Haiku 4.5 | 1.00 | 5.00 | **₹1,146** | 85/90 (3 runs) | 4 unstable |
| **Gemini 3.5 Flash-Lite** | 0.30 | 2.50 | **₹423** | 57/60 (2 runs) | 1 unstable |
| Groq llama-3.3-70b | paid Dev Tier | — | — | 58/60 (2 runs) | 2 unstable |

**CORRECTION — an earlier version of this document said Gemini 3.6 Flash costs ~₹110/month.
That was wrong by 16x.** It carried forward Gemini *2.0* Flash's pricing. Gemini 3.6 Flash is
a much more capable and more expensive model, and is in fact **the most expensive option
tested — a ~50% premium over Haiku, not a 90% saving.** Any email, note, or slide repeating
the ~₹110 figure or "one-tenth the cost" must be corrected.

### Where the decision actually stands

**Quality/stability findings are unaffected by the pricing error.** Gemini 3.6 Flash really
did score 77/77 across three runs with zero instability, where Haiku ranged 26–30 with 4
unstable prompts. What changed is that this stability now costs a **premium** rather than
being free.

**CHOSEN: `gemini-3.5-flash-lite` at ₹423/month.**

After the snapshot fix (§2) it scores **60/60 across two runs** — matching Gemini 3.6 Flash's
77/77 at **one quarter of the price**.

| Model | post-fix score | ₹/year | vs Flash-Lite |
| --- | --- | --- | --- |
| Gemini 3.6 Flash | 77/77 (pre-fix data) | ₹20,628 | +₹15,552/yr for no measured gain |
| **Gemini 3.5 Flash-Lite** | **60/60** | **₹5,076** | — |
| Claude Haiku 4.5 | 85/90, 4 unstable | ₹13,752 | worse *and* dearer |
| Groq llama-3.3-70b | 58/60, 2 unstable | Dev Tier | free tier unusable (~25 q/day) |

Set it with:

```
LLM_PROVIDER=gemini
GEMINI_MODEL=gemini-3.5-flash-lite
```

**Worth re-testing 3.6 Flash and Groq on the fixed data** before treating this as final — all
their scores predate the fix. But Flash-Lite is now at ceiling, so the most the others can do
is tie, and they cost 4x more (3.6 Flash) or require a paid tier (Groq).

The general lesson, which outlives these particular models: **three of the four models'
failures were a data defect wearing a model-quality costume.** Before paying for a better
model, check whether the corpus is asking an ambiguous question.

### Non-price factors that still favour Gemini

- **No new code.** `app.py` already has a `gemini` provider; only the model string changes.
- **Runs on the VM.** `claude -p` (the current Haiku route) **cannot run headless** — it needs
  a logged-in Claude Code session. Haiku would require building an Anthropic API provider
  that does not exist yet.

**Do not quote "100%" as an accuracy figure** — see §9.

Measured workload: **2,840 input tokens** (348 system + 2,491 context) + ~300 output.
Prompt caching does **not** apply — only 348 tokens are stable, far under any minimum
cacheable prefix.

**Billing:** Google Cloud prepay minimum is **₹1,000**; credits expire after 1 year. At
Gemini 3.6 Flash's real rate (~₹1,719/mo) that is under three weeks of runtime, **not** the
nine months an earlier draft claimed. Keep **auto-reload OFF** as a hard spending cap. The
`$300` welcome credit **excludes Gemini API**.

**All API keys are listed in `keys.md`** (gitignored, never committed — git history verified
clean). Every key there was pasted into a chat session and must be rotated before launch;
`keys.md` carries the rotation checklist.

**Critical:** the API key must belong to the *project the billing account is attached to*. A
key from another project silently stays on the free tier and throws the identical 20/day 429.

---

## 5. The benchmark harness

### `bakeoff.py` — head-to-head model comparison (new, 2026-07-30)

Separate from `run_bench.py` because it **holds retrieval fixed and varies only the answering
LLM**. Every model sees byte-identical context for every prompt, which is what makes a
30-prompt sample informative and McNemar valid.

```bash
venv/bin/python bakeoff.py <provider> [n] [--judge MODEL] [--label NAME]
venv/bin/python bakeoff.py report
```

- `provider`: `groq | gemini | haiku | sonnet | opus`
- `--judge defer` records conceptual answers with `hit=null` for an in-session judge.
  **`hit=null` is explicitly not `false`** — ungraded never counts as wrong.
- `--label` separates result files when several models share a provider.
- Results cache to `bakeoff_<label>.jsonl`; retrieval caches to `bakeoff_retrieval.jsonl`.
  Runs resume, so providers can be run hours apart while a limit resets.
- Reports Wilson CIs and exact McNemar between every pair.

**Guards built in, each from a real failure:**
1. Quota strings in responses → `QuotaExhausted`, abort.
2. Quota raised as an SDK *exception* (429s never reach the string guard) → reclassified.
3. Per-minute quota → wait and retry. Per-day → abort. Keyed on `quotaId`.
4. 503 / UNAVAILABLE → transient, exponential backoff, not quota.

### Running Haiku without the CLI

`claude -p` uses whichever account the terminal is logged into. To test Haiku on the desktop
account instead, prompts are materialised to `haiku_tasks/NN.txt` (system prompt + context +
question) and answered by **subagents pinned to `model: haiku`**, six agents × five prompts.
Answers go to `NN.ans.txt`, `NN.ans2.txt`, `NN.ans3.txt` for runs 1–3.

Caveat: a subagent carries the Claude Code system prompt and tools, so it is not a clean API
call. Mild confound, direction unknown.

### Statistical note

With n=30 only large gaps reach significance. McNemar counts **only discordant pairs** — the
prompts where two models differ. Gemini vs Groq differed on 2, so the minimum achievable
p-value was 0.500 no matter who won. **You need ≥5 discordant pairs before p can drop below
0.05.** Every pairwise comparison in this bake-off was non-significant.

---

## 6. Open bugs — fix before deploying

1. **`app.py:375` defaults to `gemini-2.0-flash`** — quota-blocked on this account and two
   generations old. The working model list runs to `gemini-3.6-flash`. Must be pinned.
2. **No 503 retry in `call_llm`.** Gemini returned transient `UNAVAILABLE` twice during
   testing. In production that is a failed answer in front of an officer. `bakeoff.py` has
   the retry logic; `app.py` does not.

Neither is fixed as of this writing.

---

## 7. Retrieval — settled, do not revisit without new evidence

### Adopted: voyage-4-nano (local, open weights, no API key)

| | Cohere v3 | voyage-4-nano | p |
| --- | --- | --- | --- |
| R@1 | 16.1% | 22.8% | 0.043 |
| R@5 | 31.7% | 40.6% | 0.020 |
| **R@10** | **40.0%** | **47.2%** | 0.079 |
| doc-level@10 | 74% | 69% | — |

Ships as **512-dim float16** (`voyage_out_512/`, 129 MB) — measured at identical recall to
the 1024-dim 528 MB build. Matryoshka truncation plus fp16 costs nothing here.

Note the doc-level *drop*: the models fail differently. Cohere lands in the right document on
the wrong page; voyage nails the chunk or misses the document entirely. **This shrinks the
expected payoff of a reranker** — re-measure before investing there.

### Rejected on evidence

- **Table serialization** (`ingest_v2.py`): recall@10 40.0% → 37.8%, p=0.56. The stratum it
  targeted got *worse* (32% → 20%). Correlation was real, causal inference was wrong. Saved a
  2.8 GB rebuild and $50–350 of paid parsing.
- **MMR diversity re-ranking**: significantly harmful.
- **Hard query routing**: net zero.
- **Soft routing**: contaminated by overfitting; not adoptable without a held-out set.
- **Three system-prompt edits**: each regressed accuracy. **The base system prompt is an
  established local optimum. Do not touch it.**

### Fixed along the way

`detect_district()` was doing bare substring matching, so "Guntur" matched inside other
strings — 16 of 180 prompts got the wrong district. Now uses word-boundary regex over
aliases sorted longest-first.

---

## 8. Deployment plan

Phase folders live in `deployment/` with checklists and a progress bar:

```bash
bash deployment/progress.sh -v
```

**Phase 0 — security & decisions.** Rotate leaked credentials (see §10). Confirm host:
Oracle Always Free, Mumbai/Hyderabad, ₹0 (fallback E2E Networks C3 ~₹2,263/mo). Confirm
model: Gemini 3.6 Flash, billing enabled.

**Phase 1 — local prep.** `pip install google-genai`; set `LLM_PROVIDER=gemini`,
`GEMINI_MODEL=gemini-3.6-flash`, billed `GEMINI_API_KEY` in `.env`; smoke-test; commit the
`run_bench.py` fix (currently modified, unpushed).

**Phase 2 — provision.** Oracle Ampere A1, Ubuntu 22.04. **Region is permanent.** VCN
security list: ingress TCP 8501.

**Phase 3 — deploy.** Update `deploy/vm_setup.sh` (it still writes `LLM_PROVIDER=groq`), run
it on the VM, `scp -r voyage_out_512` across (129 MB, not in git), write `.env`, then:

```bash
sudo iptables -I INPUT -p tcp --dport 8501 -j ACCEPT && sudo netfilter-persistent save
```

**Oracle needs the port opened in BOTH places** — VCN *and* iptables. Miss either and the app
looks dead.

**Phase 4 — verify.** Startup log must read `voyage_local:voyageai/voyage-4-nano:512` — not
cohere, not 1024. Numeric check: *"GDDP of Anakapalle 2024-25"* → Rs. 53,010 Cr, ~9.23%
growth. Ask about a district not in the corpus — it must decline, not invent. `free -h` under
load. Re-run the hard benchmark against the deployed index (~47% recall@10). Soak 24h.

**Phase 5 — launch.** Query logging, feedback control, officer note, soft-launch to 3–5.

---

## 9. What to tell officers

**State the real numbers: ~100% on figures, ~55% on open-ended interpretation. Not 90%.**

Two categories scored **0/5** (`DataInterpretation`) and **0/2** (`Intervention`) on the
120-prompt set — questions asking the system to *reason* rather than *cite*. No index change
fixes this; it is an architectural gap.

**Add a line about consistency**: the same interpretive question can get a different answer
on a re-ask. An officer who re-asks and gets a refusal after a good answer will lose trust
fast.

**Do not quote the bake-off's 90–100% scores as system accuracy.** That 30-prompt draw
contains zero `Intervention` prompts, only three `DataInterpretation`, and half its
conceptual slots are sector-ranking lookups. It is a *model selection* tool, not an accuracy
measurement.

Also unresolved for a public government link: **no HTTPS** on port 8501, **no
authentication**, and fabrication measured at **1.7%** (above the previously documented <1%).

---

## 10. Security — needs action

- **GitHub token** `ghp_2AZi…` was pasted into chat. Repo is public. **Rotate.**
- **Nine Cohere keys** pasted into chat. **Rotate.**
- **Four Groq keys** and **six Gemini keys** pasted into chat. **Rotate.**
- Gitignored and must stay so: `streamlit_secrets.toml`, `.cohere_live_keys`, `voyage_out/`,
  `pilot_*.pkl`, `pilot_index.npz`, `*.log`, `*_out.txt`.
- Add: `haiku_tasks/`, `bakeoff_*.jsonl` (not yet gitignored).
- `trust_remote_code=True` is required by voyage-4-nano — flag for government sign-off.

Note: multiple free accounts were used to work around per-organisation daily caps. This
generally violates provider terms and risks the accounts. It is also not a deployment
strategy — at 100 queries/day it would need ~4 fresh Groq accounts *per day*.

---

## 11. Traps — read before debugging

**A side-effectful import silently invalidated a whole experiment.** `eval_voyage.py` imports
from `run_hard_retrieval`, whose *module body* monkeypatches `embeddings.embed_query` with a
Cohere key-rotating cache. Voyage queries silently got **cached Cohere vectors** scored
against a **voyage index**: 0.0% recall, no error, cosine 0.065. If retrieval ever looks
implausibly bad, **check which provider actually produced the query vector first.**

**Process alive ≠ process working.** Twice a job reported as "running" was a husk — RSS 20 MB
instead of 815 MB. Check RSS and log progress, never just `pgrep`.

**`transformers` 5.x cannot load voyage-4-nano** — remote code leaves `config_class = None`,
rejected with an opaque `AttributeError`. Pin `transformers<5` (4.57.6).

**MPS (GPU) is slower than CPU here** — 2 vs 3 chunks/s, doubles memory pressure, pushed swap
to 91%. Use `EMBED_DEVICE=cpu`.

**Length-sorted batching is load-bearing**, not an optimisation — batches pad to their
longest member.

**Buffered stdout is lost when a background job is killed.** Use `python -u`.

**`ru_maxrss` units differ**: bytes on macOS, kilobytes on Linux.

---

## 12. Immediate next steps

1. Fix the two `app.py` bugs (§6).
2. Enable Gemini billing; generate a key **in the billed project**; verify no 429.
3. Gitignore `haiku_tasks/` and `bakeoff_*.jsonl`; commit `bakeoff.py` and `run_bench.py`.
4. Provision Oracle, deploy, verify (§8).
5. Build the **held-out benchmark set** — still pending, and now clearly needed: the
   synthetic set has driven five decisions and is partly spent.
6. Re-validate soft routing on that held-out set.
7. Replace the synthetic benchmark with one built from **real officer query logs** once
   traffic exists. That is where the remaining gains are.
