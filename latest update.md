# Swarna Andhra @2047 Dashboard — Status (2026-08-31)

Live: **https://version-2-coral.vercel.app** · Repo: themonkkey/Version-2 (main)
Deploy: `vercel --prod --yes` from `landing/` (git push does NOT deploy).

## What shipped, by area

### Suggested interventions — all 28 districts (the engine)
- `scripts/build_suggested_interventions.py`: per-district, per-sector specialised
  suggestions grounded in Vision plans + sector Toolkit + Drive WOOP district docs.
- 446/446 sector recs authored; 16 districts carry WOOP-doc grounding
  (Drive folder mirrored to `corpus_files/district_docs/`, 3 folders were empty).
- Authored content: `scripts/suggested_authored.json`; shipped artifact:
  `landing/assets/suggested_interventions.json`.
- Renderer merges with Kurnool's verified plan-quote layer (`recommendations.json`
  stays Kurnool-only, quotes preserved); everywhere else the card shows
  "Suggested interventions" with a grounding note.

### Capacity building tab — fully district-dynamic
- Section header, stat strip (sessions/reports/attendances/photos/levels),
  day-wise brief heading, feedback + assessment cards: all scope to the picked
  district; honest empty states ("No assessment filed for X yet",
  "Select a district…" when none picked).
- A day whose session did not run shows only its note, no dashed fact boxes.
- Dropdown pick rides the map's own route (`showDistrict`): map drills, profile
  paints, chip + every tab re-scope, URL becomes `#districts/capacity/<name>`.
- Cases tab: "Relevant case studies for <district> · Discussed during the
  capacity building sessions."

### Navigation — adversarial audit, 13 flaws fixed
Multi-agent loop (find → live-verify → fix → re-verify, 2 rounds) plus a full
back-navigation sweep of every page. Headlines:
- `go()` pushes history on reader clicks: Back = previous page (was: exit site).
- Deep links survive: in-session district hashes wait for the map; drill path
  kept on every tab; `#capacity/<District>` and `#calculator/<sector>` shareable.
- Malformed % in the hash can no longer wedge the router (decodeSeg).
- No swallowed Back presses, no capacity back-oscillation, no stale chip text.

### Case-study decks (17)
- Rebuilt by `scripts/proto_deck.py` to the methodology deck's structure
  (agenda, kickers, watermarks, closing plate); wheel-scroll advance removed,
  arrows are focusable buttons with glow nudges; reduced-motion respected.
- Content source: `corpus_files/case_studies/*.txt` (edit there, regenerate).

### Language engine
- `scripts/check_language.py --check`: sweeps index.html (text + JS prose
  strings), all case decks, capacity pages and copy-bearing JSON for em dashes,
  US spellings, PIF-flagged words, typos. Allowlist:
  `scripts/language_allow.txt`. Currently clean (22 html + 4 json).
- 31 findings fixed at their sources (playbook em dashes, US→British across
  decks and suggestions; "taught" → discussed/delivered).

### GVA playbook
- Location Quotient explained in method step 2 (formula + above/below 1).
- `landing/assets/gva_playbook.json` is authoritative; builder kept in sync.

## Guards (all green)
```
python3 scripts/build_i18n.py --check            # 384 strings, 13 untranslated
python3 scripts/check_language.py --check
python3 scripts/build_suggested_interventions.py --check
python3 scripts/build_recommendations.py --check
python3 scripts/check_classifications.py
```

## Ops notes
- Local preview: python http.server on :8090 serving `landing/`.
- Push: one-shot token header (never in .git/config; verify 0 after).
- i18n: runtime `apply()` keys on English text; JS-generated copy is not
  extracted; bump `te.json?v=` stamp on translation changes.
- No em dashes in user-facing text (colon/comma/semicolon/middot).

Last commits: 84e96e5 (calculator history + chip), dfe1b27 (nav hardening),
a62cf6c (language engine), d9b9ed2…57984b3 (capacity dynamics, WOOP fold-in).
