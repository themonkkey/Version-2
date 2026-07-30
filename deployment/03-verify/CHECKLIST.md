# Phase 03 — Verify

Prove it works on the server before anyone sees it. Do not skip to launch because it
"looks fine" — two failures today were processes that existed but were doing nothing.

## Checklist

- [ ] App loads in a browser at `http://<ip>:8501`
- [ ] Startup log shows the right model:
      `voyage_local:voyageai/voyage-4-nano:512` — **not** cohere, **not** 1024
- [ ] Ask a numeric question and check the figure against the corpus:
      *"What is the GDDP of Anakapalle for 2024-25?"* → Rs. 53,010 Cr, ~9.23% growth
- [ ] Ask a methodology question, confirm it cites a source file
- [ ] Ask about a district **not** in the corpus — it should decline, not invent
- [ ] Measure query latency on the server (expect ~100 ms embed + LLM time)
- [ ] `free -h` under load — confirm well under the 12 GB ceiling
- [ ] Run the hard benchmark **against the deployed index** and confirm ~47% recall@10
- [ ] Leave it running 24h, then re-check the service is still up and memory is flat

## Challenges

**Process alive ≠ process working.** Twice today a job reported as "running" was a husk —
RSS 20 MB instead of 815 MB. Check RSS and log progress, never just `pgrep`.

**Cold start after idle.** First request after a long gap may be slow if the OS has paged
out the model. Worth measuring; if bad, a tiny keep-warm cron helps.

**Memory creep.** The embedding run showed RSS growing from 815 MB to 5 GB on long inputs
before settling. Watch `free -h` over 24h rather than at one moment.

**Silent wrong-index.** If it ever loads a Cohere index with a voyage provider (or 1024 vs
512), retrieval degrades to near-random *without erroring*. The model-id guard should
prevent it — verify the startup line rather than assuming.

**Groq rate limits.** Free tier caps tokens per minute. Several officers querying at once
may hit it. This is exactly why context is truncated to 11 chunks / 900 chars. Test with
two or three concurrent sessions before inviting a group.
