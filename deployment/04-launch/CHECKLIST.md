# Phase 04 — Launch

Going from "it works" to "officials are using it".

## Checklist

- [ ] Query logging in place — question, retrieved sources, answer, latency, timestamp
- [ ] Feedback control in the UI (thumbs up/down, or a "was this right?" link)
- [ ] Point `landing/index.html` at the production URL
- [ ] Optional: domain + HTTPS (Caddy or nginx + Let's Encrypt — port 8501 over plain HTTP
      is fine for a pilot, not for a public launch)
- [ ] Write a one-page note for officers: what it can answer, what it cannot, how to report
      a bad answer
- [ ] **State the real numbers** in that note: ~100% on figures, ~55% on open-ended
      interpretation. Not 90%.
- [ ] Soft-launch to 3-5 officers first
- [ ] Watch the logs for a week before widening
- [ ] Restore the Streamlit Cloud deployment as a fallback URL (Cohere + 8 keys, free)

## Challenges

**Expectation setting is the main risk now, not accuracy.** Numeric answers are excellent
(100%). Open-ended interpretation is ~55%, and two categories score **0/5 and 0/2** —
questions asking the system to *reason* rather than *cite*. An officer who opens with an
interpretive question will conclude the tool is poor. The note should steer people toward
what it's good at.

**No HTTPS on port 8501.** Fine for a pilot with a handful of known users. Not acceptable
for a publicised government-facing link.

**No authentication.** Anyone with the URL can use it. If usage should be restricted to
officials, that needs building — Streamlit has no auth on the free path.

**Fabrication at 1.7%** in certification, above the previously documented <1%. At two
occurrences in 120 that's noisy, but for a government tool, a single confident wrong figure
in front of an official is disproportionately damaging. The feedback control is how you
catch these.

**Free tier is not an SLA.** Oracle can reclaim the instance. Keep the Streamlit Cloud
fallback alive so there's a URL that still works.
