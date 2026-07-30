# Production deployment

Six phases. Each folder holds a `CHECKLIST.md` with tickable items and the **challenges**
specific to that phase — the traps found the hard way, written down so they aren't
rediscovered.

## Progress

```bash
bash deployment/progress.sh        # progress bars per phase
bash deployment/progress.sh -v     # also list outstanding items
```

Tick an item by editing its `CHECKLIST.md` and changing `- [ ]` to `- [x]`.

## Phases

| | Phase | What it covers |
| --- | --- | --- |
| 00 | prerequisites | Certification, secrets rotation, honest-numbers correction |
| 01 | host | Oracle Always Free (₹0) or E2E C3 (Rs 2,263/mo) |
| 02 | deploy | Provision script, index upload, systemd service |
| 03 | verify | Prove it works on the server before anyone sees it |
| 04 | launch | Logging, feedback, expectation setting, soft launch |
| 05 | post-launch | Learn from real queries; where the remaining gains are |

## Certified numbers — use these, not the old ones

| Layer | Result |
| --- | --- |
| Numeric factual | **100%** (80/80) |
| Conceptual reasoning | **~55%** |
| Retrieval recall@10 (hard set) | 47.2% |

`STATUS_2026-07-28.md` reports "conceptual 90% (clean context)". That was a curated subset.
Random sampling gives 47-55% on both Cohere and voyage. **Do not quote 90% to officials.**

## Cost

₹0/month if Oracle Always Free capacity comes through and Groq certifies.
Rs 2,263/month fallback on E2E. ~₹3,000/month more if Haiku is needed over Groq.
