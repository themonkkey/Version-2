# Phase 00 — Prerequisites

Things that must be true before a host is worth provisioning. Several are blocked on you,
not on code.

## Checklist

- [x] Voyage index built and verified (59,388 x 1024, norms 1.0, permutation checked)
- [x] 512-dim float16 index built — 130 MB, verified at 47.2% recall@10, identical to full size
- [x] Voyage certified end-to-end vs Cohere (numeric 100%, conceptual 55%, no regression)
- [x] `deploy/vm_setup.sh` written and syntax-checked for ARM64 + x86
- [x] Code pushed to GitHub (`themonkkey/swarna-andhra-chatbot`, main)
- [ ] **Groq certified as the production answering model** ← running now
- [ ] **Rotate the exposed GitHub token** (`ghp_2AZi…`) at github.com/settings/tokens
- [ ] Rotate the 9 Cohere keys pasted into chat (low stakes, but do it)
- [ ] Confirm no non-public material in `corpus_files/` (decides whether residency matters)
- [ ] Correct the "90% conceptual" claim in any deck/report before showing officials

## Challenges

**The Groq gap is the real blocker.** Every certified number was measured on Claude Haiku;
production runs Groq `llama-3.3-70b`. Deploying before this completes means shipping a
system whose answering model has never been measured. If Groq lands materially below
Haiku, the choice is: accept lower quality, or pay ~₹3,000/month for Haiku.

**The 90% figure is a reputational risk, not a technical one.** `STATUS_2026-07-28.md`
reports "conceptual 90% (clean context)". Random sampling gives 47-55% on *both* models.
Presenting 90% to AP officials and then having them experience ~55% is worse than
presenting 55% up front.

**Secrets in chat history.** The GitHub token has write access to the repo. Lower urgency
than it sounds only because the repo is already public — but it allows *writes*.
