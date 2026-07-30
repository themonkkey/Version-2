---
title: Swarna Andhra GVA Assistant
emoji: 📊
colorFrom: green
colorTo: gray
sdk: streamlit
sdk_version: 1.40.0
app_file: app.py
pinned: false
license: mit
short_description: RAG assistant on Andhra Pradesh GVA methodology and district data
---

# Swarna Andhra GVA Assistant

A retrieval-augmented assistant for Andhra Pradesh government officials, answering
questions on GDP/GSDP/GVA estimation methodology, district economic profiles, and
constituency/mandal vision plans, grounded in official material with citations.

Built by Pahlé India Foundation.

## Why this deployment exists

The previous Streamlit Community Cloud deployment depended on a hosted embedding API and
went down when its monthly key quota was exhausted. This Space embeds queries locally with
**voyage-4-nano** (Apache 2.0, open weights), so there is **no embedding API key and no
quota to exhaust**. That failure mode is gone.

The change also improved retrieval measurably: **47.2% vs 40.0% recall@10** on a 180-prompt
benchmark, at 1024 dimensions in both cases. See `VOYAGE_RESULT.md` in the source repo.

## Configuration

| Variable | Value | Notes |
| --- | --- | --- |
| `EMBED_PROVIDER` | `voyage_local` | Required. Loads `voyage_out/` and runs the model locally. |
| `EMBED_DEVICE` | `cpu` | Free Spaces are CPU-only. |
| `LLM_PROVIDER` | `groq` | Answer generation. |
| `GROQ_API_KEY` | secret | The only key this deployment needs. |

`app.py` refuses to start if the index's stamped `model_id` does not match the active
`EMBED_PROVIDER` -- a mismatch would otherwise return plausible-looking nonsense rather
than an error.

## Notes

- First boot is slow: the model (~670 MB) downloads from the Hub and loads before the first
  query. Subsequent queries measured 75-117 ms on CPU.
- Index is 59,388 chunks x 1024 dimensions, shipped via Git LFS.
