# What production actually costs

_2026-07-30. Costs are estimates — verify current provider pricing before committing._

**The headline: you can launch for $0-6/month. The one thing that might force real spend is
the answering model, and that is a quality decision, not an infrastructure one.**

---

## The gap nobody has priced yet

Every certified number on this project — **98.8% numeric, 90% conceptual, 96% stress** — was
measured with **Claude Haiku** answering.

The deployed app runs **Groq `llama-3.3-70b-versatile`** (`app.py:363`).

**Groq has never been certified on this corpus.** That was flagged as an open item in the
original status doc and is still open. So "production quality" currently means one of:

- **Certify Groq** and accept whatever it scores (free, might be fine, might be worse)
- **Switch to Haiku** and inherit the certified numbers (costs real money per query)

This is the only decision on this page with meaningful recurring cost attached. Everything
else is a rounding error.

---

## Three tiers

### Tier 0 — Launch free, today · **$0/month**

| Component | Choice | Cost |
| --- | --- | --- |
| Hosting | Streamlit Community Cloud | free |
| Embeddings | Cohere, 8 trial keys rotating | free |
| LLM | Groq free tier | free |
| Domain | `*.streamlit.app` | free |

Works right now. `streamlit_secrets.toml` is ready; it needs one paste.

**Limits you are accepting:** ~8,000 embedding calls/month (~266 questions/day) and a hard
ceiling when they exhaust; Groq's tokens-per-minute cap, which is *why* context is truncated
to 11 chunks / 900 chars (`app.py:339`); public apps only; an uncertified answering model.

Right choice for a pilot with a handful of officers. Not right for a launch you publicise.

### Tier 1 — Recommended · **~$5-6/month**

| Component | Choice | Cost |
| --- | --- | --- |
| Hosting | **Railway** (account already exists from BlackMantis) | ~$5/mo |
| Embeddings | **voyage-4-nano, local** | **$0 — no key, no quota, ever** |
| LLM | Groq free tier | free |
| Domain | optional `.in` or `.org` | ~$10-15/yr |

**This removes the failure that has taken the app down twice.** No embedding key means no
quota to exhaust. It also ships the measured **+7.2 points recall@10** improvement.

Needs 2.29 GB RAM (measured). Railway's 8 GB is ample; Hetzner CX22 at ~€4/month also fits;
Oracle Ampere A1 is free at 24 GB if you can obtain one, which is genuinely uncertain.

Streamlit Community Cloud **cannot** host this — ~1 GB ceiling against a 2.29 GB requirement.

### Tier 2 — Certified quality · **~$35-60/month at moderate use**

Tier 1 plus **Claude Haiku** as the answerer instead of Groq.

Rough per-query arithmetic: ~10K input tokens of context + ~300 output. At Haiku's rates
that lands around **$0.01 per query**, so:

| Daily questions | Approx. monthly LLM cost |
| --- | --- |
| 50 | ~$15 |
| 100 | ~$33 |
| 300 | ~$100 |
| 500 | ~$165 |

**Prompt caching would cut this substantially** — the system prompt and any preloaded
methodology are identical across queries, and cached input is heavily discounted. Worth
implementing before scaling up, not before launching.

Take this tier only if certification shows Groq materially underperforms Haiku. Do not
pre-pay for quality you have not shown you need.

---

## Recommendation

**Launch on Tier 1 (~$5/month).** It is barely more than free, it permanently removes the
quota failure, and it ships a measured accuracy gain.

**Decide Tier 2 on evidence.** The certification currently running scores voyage with Haiku.
Run the same harness once more with `LLM_PROVIDER=groq` and compare. If Groq holds near
98.8% / 90%, stay free and save ~$40/month. If it drops sharply, Haiku's cost is justified —
and you will have the number to justify it with.

That is a one-hour experiment that decides a recurring bill. Do it before paying anything.

---

## Not money, but required before launch

1. **Certify the answering model** — in progress for Haiku; still needed for Groq.
2. **Rotate the exposed GitHub token** (`ghp_2AZi…`) — write access, sitting in a chat log.
3. **Data residency.** The repo is **public**, and Railway/Streamlit/HF all host outside
   India. For Andhra government economic data this may become a procurement question. The
   compliant answer would be NIC/MeghRaj or an AWS/Azure Mumbai region — heavier, and worth
   raising before officials ask rather than after.
4. **Error handling under load.** The crash fix (`76a1a20`) handles a 429, but nothing has
   been load-tested with concurrent officers.
5. **Monitoring.** A drift pilot was designed and never run. At minimum, log queries and
   failures so you learn what officers actually ask.
6. **A feedback path.** The fastest route to real improvement is knowing which answers were
   wrong — cheaper and better-targeted than any further retrieval tuning.

---

## Launch sequence

1. Paste `streamlit_secrets.toml` → production back up, free, today *(Tier 0)*
2. Finish voyage certification *(running)*
3. Certify Groq vs Haiku → decides Tier 1 vs Tier 2
4. Deploy voyage to Railway via `deploy/vm_setup.sh` *(Tier 1)*
5. Point `landing/index.html` at the new URL
6. Soft-launch to a small group of officers, with logging on
7. Widen once the logs show it behaving

Steps 1-2 cost nothing. Step 3 decides the bill. Nothing before step 3 needs a payment method.
