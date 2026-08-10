# Dashboard template audit — district level (D1–D4)

**2026-08-10.** First review of the four district archetype templates. Written by
hand: three workflow attempts to run this as an adversarial-agent review died on
session limits before producing a single finding (573k, 547k and an earlier run's
tokens spent, zero results each time). Every claim below is verified against files on
disk and by executing the real code — no agent self-report to weigh, because none
survived to report.

**Verdict: GO for integration**, with one non-blocking gap noted in §4.

The district templates were built, wired into `index.html`, and passed a casual
spot-check during integration, but — unlike C1–C4 and M1–M3 — had never been through
adversarial review. That is the gap this document closes.

---

## 1. Results

| Template | Districts | Contract violations | Percentage-trap confusion | Colour violation | Renders clean |
| --- | --- | --- | --- | --- | --- |
| D1 Metro/urban | 6 | **0** | **0** | **0** | yes |
| D2 Agrarian | 11 | **0** | **0** | **0** | yes |
| D3 Industrial | 2 | **0** | **0** | **0** | yes |
| D4 Emerging/agency | 9 | **0** | **0** | **0** | yes |

**68 renders** (28 districts × {bare, enriched} + 12 hostile inputs), **zero throws**.

---

## 2. The percentage trap — the highest-value check, independently verified

`node.aggregates.<sector>` carries two percentages that differ by roughly 7×:
`pct_of_district` (that sector's share of the district's own economy) and
`pct_of_state_sector` (the district's share of AP's total for that sector). Confusing
them is the single most likely way to misstate a real government figure.

Traced concretely, one district per archetype:

| District | Sector | `pct_of_district` | `pct_of_state_sector` | Rendered under the right caption? |
| --- | --- | --- | --- | --- |
| Guntur (D1) | Agriculture | 14.04% | 2.01% | yes — "Of Andhra Pradesh's TOTAL agriculture output" |
| Krishna (D2) | Agriculture | 53.22% | 8.98% | yes |
| Anakapalle (D3) | Industry | 20.98% | 2.15% | yes |
| Srikakulam (D4) | Agriculture | 30.16% | 2.48% | yes |

For all four, I searched the rendered HTML for the district-share number appearing near
state-wording and the state-share number appearing near district-wording. **Zero hits
in either direction, on any of the four.** Each template also keeps the two constants
in separate functions/sections in source, with a header comment restating the
distinction — the same pattern that made the constituency-level fix legible.

---

## 3. Independently verified as passing

- **Contract: 0 violations across all four.** Enumerated every `node.<key>` read by
  static regex in each file and diffed against `DASH.DISTRICT_KEYS` (22 keys). D1 reads
  21 distinct keys, D2 21, D3 18, D4 19 — all present in the allowed list. This is the
  defect class that sank the first constituency round (fields read from nowhere); it
  did not recur here.
- **Colour: 0 hex literals in any of the four files.** None of the four even calls a
  colour function directly — colour is entirely delegated to shared components, so
  there is no path by which a template could reintroduce the AP portal's palette
  (rejected earlier for measuring ΔE 3.9 under protanopia) or hardcode its own map.
- **No hardcoded provenance.** `grep` for "Census 2011" or similar asserted-source
  strings across all four: no hits. (This was a real C4 defect in the constituency
  round — fixed there, not reintroduced here.)
- **No inline colour styling on headings.** (A prior template shipped one that was
  illegible on the dark stage; grepped for the same pattern here, none found.)
- **Runnability: 68 renders, 0 throws** — every district on both bare and enriched
  paths, plus hostile inputs (`{}`, an archetype tag with nothing else, and a record
  with every array field explicitly nulled/emptied).
- **Enriched path fully clean**: 0 empty-states per render across all four archetypes.
  Matches the pattern already established at the constituency and mandal levels.
- **Constituency drill-down wired correctly.** All four templates call
  `onpick: 'DASH_PICK_CONSTITUENCY'` (D1 via a local const referencing the same
  string), and `window.DASH_PICK_CONSTITUENCY` is defined in `index.html:1619`. This is
  the same defect class as the earlier `DASH_PICK_MANDAL` bug (a handler named but
  never defined, so every click threw) — checked explicitly, not assumed fixed by
  analogy.
- **D4's framing avoids the league-table trap it was built to avoid.** Compared a
  scheduled/agency district (Alluri Seetharama Raju) against a merely low-PCI one
  (Kurnool): ASR's copy states "scheduled / agency district" and explicitly frames
  itself as leading "with trajectory rather than with rank"; Kurnool's copy names its
  rank plainly ("24/28 — emerging, out of 28 districts") without the agency framing.
  `node.why` correctly distinguishes the two situations and the template reads it
  rather than treating all nine D4 districts as one undifferentiated group.
- **D3's concentration is the headline, not buried.** Anakapalle's 52.6% industry
  share — extreme for AP — is visible in the rendered output and industry sections lead
  the page ("Inside industry", "Industry's four-year path") ahead of the whole-economy
  view.
- **Cross-template rhythm is consistent without being identical.** All four share the
  same skeleton (headline stats → trajectory → composition → state-footprint →
  constituencies) while each leads with what its thesis demands: D1 "A services-led
  economy", D2 "What this district produces" (agriculture first), D3 "Inside industry",
  D4 "Where the district economy is going" (trajectory, not a snapshot). A user
  clicking between districts sees one system, not four unrelated pages.
- **Reasonable accessibility coverage.** 3–5 inline SVGs per render, 7–12 `aria-label`
  attributes per render across the four sampled districts — figures are available as
  text, not only as chart geometry.

---

## 4. Known gap — not a defect, worth tracking

- **Bare-path empty-state counts are high** (D1 15, D2 6, D3 18, D4 22 per render) —
  expected, since the bare record carries only the 12 always-present
  `dashboard_index.json` fields against a 22-key contract. This is a non-issue in
  practice: `landing/assets/dist/<key>.json` exists for all 28 districts, so the
  enriched path is what integration actually serves; the bare path exists purely as a
  defensive fallback if a fetch fails. Same shape as the constituency level's bare/
  enriched split, and treated the same way there.

No blockers, no majors, found in this pass. That is a materially better first result
than either the constituency round (3 of 4 FAIL, 45 findings) or the mandal round (2 of
3 FAIL, including two shipped falsehoods). The most credible reason: `enrich.js`'s
district contract and the honesty-rule discipline were already established by the time
these four were written, so the defect classes that required a first round to discover
elsewhere were designed against from the start here.

---

## 5. What a from-scratch adversarial pass might still find

This was one reviewer (me) checking the highest-known-risk defect classes plus
runnability, not four independent adversarial agents each trying to break one template
for an extended session. It is thorough on the checks that have mattered so far. It is
not a substitute for genuinely independent adversarial review if the appetite exists to
retry it later — ideally as a smaller, single-template-at-a-time run given three
consecutive full-fleet attempts have died on session limits.

If retried, the template most worth a second look first is **D2** (11 districts, the
largest group, and the constituency-level equivalent — C2 — was the one round-1 loop
that came back PASS_WITH_FIXES rather than FAIL, suggesting agrarian templates may
converge faster but are also checked less hard by a reviewer who assumes they're
simpler).

---

## 6. Next steps

1. No blocking work required — district level is ready alongside constituency and
   mandal.
2. If deeper adversarial review becomes affordable (single-template runs rather than a
   four-template fleet), start with D2 per §5.
3. Update `docs/DASHBOARD_ARCHITECTURE.md` and `handoff/2026-08-07/SESSION_STATE.md` to
   mark the district level reviewed, matching what was done for constituency and
   mandal.

---

## 7. Process note

Three consecutive attempts to run this review as a multi-agent workflow died on
session limits (this session and, per the handoff notes, at least one prior session)
without producing a single finding — roughly 1.1M tokens spent across those three
attempts for zero output. The hand-review that replaced them cost a small fraction of
that and found the same shape of "clean, no blockers" result the earlier casual
spot-check had suggested — but this time backed by the specific checks (contract-key
diff, percentage-trap trace, colour grep, click-handler wiring) that have caught real
defects at every other level. The lesson already written into the constituency audit
holds again: when a review workflow keeps dying at the same stage, doing the check by
hand is not a fallback to settle for — for a scope this size, it is frequently the more
reliable option outright.
