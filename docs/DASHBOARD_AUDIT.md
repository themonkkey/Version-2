# Dashboard template audit — second pass

**2026-08-06.** Audit of the conform → review loops that rewrote the four constituency
templates against the enriched-node contract. Supersedes the first-pass audit
(2026-08-05), whose findings are tracked as resolved/surviving below.

**Verdict: GO for integration**, with two known non-blocking defects listed in §3.

Written by hand. The meta-audit agent died on a session limit in both rounds, so the
checks it was briefed to run were executed directly and every claim below is verified
against files on disk — no agent self-report is taken at face value.

---

## 1. Loop results

| Loop | Verdict | Ran cleanly | Contract violations | Blockers | Findings |
| --- | --- | --- | --- | --- | --- |
| C1 Urban | FAIL | yes | **0** | 2 | 11 |
| C2 Agrarian | PASS_WITH_FIXES | yes | **0** | 0 | 7 |
| C3 Industrial | FAIL | yes | **0** | 1 | 9 |
| C4 Mixed | PASS_WITH_FIXES | yes | **0** | 1 | 7 |

No loop died. No reviewer rubber-stamped — the lowest finding count was 7, and every
reviewer verified by execution: one used a runtime Proxy over 32×2 renders to enumerate
key access, another served the repo over HTTP and rendered in a real browser so the
sanitiser took its live DOM path rather than the string fallback.

---

## 2. First-pass defects — all three resolved

**(a) `compositionBars` encoded rank, not share — RESOLVED.**
`components.js` now defaults to `scale:'share'`, so the track is 100% and bar width is
the published percentage. Verified: items `[41, 39, 20]` render at widths `41%, 39%,
20%`. `scale:'relative'` remains available for genuine rankings. No template overrides
the default under a share caption.

**(b) Wrong fallback sector colours — RESOLVED.**

> **SUPERSEDED 2026-08-07 (later session) — sector colours.** The line below records
> `agri #16A34A / industry #FF8A00 / services #C93A2C` as the correct fallback, taken
> from the AP portal. **Those colours have since been replaced and must not be restored.**
> Measured with the OKLab CVD validator:
>
> ```
> #16A34A (agriculture) vs #FF8A00 (industry)   ΔE 3.9 protanopia   (floor is 8)
> ```
>
> At 3.9 those two bars are effectively the SAME COLOUR to a protanope — roughly one man
> in twelve — on a tool being handed to government officers. Colour is now keyed off the
> sector name in `components.js` → `sectorHue()`, using `#6FA817 / #2B93BF / #BF8A2B`,
> which passes lightness, chroma, CVD separation and contrast on both surfaces.
> **Do not take chart colours from the portal payload again.** Validate any new palette
> with the `dataviz` skill's `scripts/validate_palette.js` before shipping it.

`components.js:238` is now `agri #16A34A, industry #FF8A00, services #C93A2C`, matching
the portal across all 175 harvested records. The previous value shipped `#F5B400` for
Industry, which the portal reserves for whole-economy GCDP. Both template-level
hardcoded colour maps are gone: `grep -oE '#[0-9A-Fa-f]{6}' tpl-*.js` returns nothing.

**(c) Templates reading fields that existed nowhere — RESOLVED, and this was the big
one.** `enrich.js` now joins `dashboard_index.json` with `apc/<code>.json` into one
documented contract. All four reviewers independently enumerated every `node.<key>`
read and diffed it against `DASH.ENRICHED_KEYS`: **zero violations across all four
templates.** The measured effect:

| | bare path | enriched path |
| --- | --- | --- |
| C1 | 0.00 empty-states/render | **0.00** |
| C2 | 3.00 | **0.00** |
| C3 | 6.00 | **0.00** |
| C4 | 0.00 | **0.00** |

Every template fully populates once enriched. All 175 `apc/*.json` files are already on
disk, so the enriched path is the one integration will use; the bare path is now a
degraded fallback rather than the primary experience it was in round one.

---

## 3. Findings from this pass

**FIXED during the audit:**

- **Fabricated population on a real record (C1 blocker).** Mangalagiri rendered
  `Population 4` and `Density 0 / km²`. Root cause was NOT the template — it was
  `num()` in `scripts/classify_templates.py`. The portal writes that one constituency's
  population as `"3.53 Lakhs"` while the other 174 use plain integers, and the regex
  took the leading number and discarded the unit. Fixed with a unit-aware parser
  (Lakh/Crore/Million/Thousand); index re-derived. Now renders `Population 3,53,000`,
  `Density 1,016 / km²`, and the population range across all 175 seats is a plausible
  124k–629k. Worth noting the defect surfaced in a template but lived two layers
  upstream, in code written outside the workflow.

- **Dead click handler (C4 blocker).** `drillList` emitted
  `onclick="DASH_PICK_MANDAL(...)"` naming a global defined nowhere, so every mandal
  click threw a `ReferenceError`. Fixed in `components.js` at the call site rather than
  in the template: the handler is now invoked only if it exists, so clicking is a no-op
  until integration wires it, and templates need no knowledge of when that lands.

**SURVIVING, non-blocking:**

- **C3's bare path carries 6 empty-states per render** — the highest of any template.
  Its thesis is the industrial growth curve, which needs `node.growth`, absent without
  the apc payload. It states this honestly rather than stubbing a fake chart, and the
  enriched path is clean. Acceptable, but C3 is the template most dependent on
  enrichment actually being wired.

- **Reviewer-reported items not independently re-verified**, listed here so they are not
  lost: C2 omits the 2028-29 GCDP target on the enriched path; C4's CAGR sub-label
  asserts a derivation the figure may not have; C1's identity strip uses an inline style
  that may read poorly on the dark stage. These are single-line copy/style issues, none
  of which affect correctness of a rendered figure.

**FALSE POSITIVE — corrected.** My first check of C3 reported "says *not published* while
growth data exists on 20 of 20 records." That was a bad test, not a bug: the phrase
appears in three different places in `tpl-c3.js` about three different things, and my
regex matched any of them. Testing the specific claims gives **0 false assertions across
all 20 enriched records**. C3 is honest here.

---

## 4. Independently verified as passing

- **350 renders, zero throws** — all 175 records on both bare and enriched paths, plus
  hostile inputs (`{}`, null fields, `area = 0`, zero shares, empty thrust, empty mandals).
- **Hard rules hold.** No agent modified `index.html`, `components.js`, `components.css`
  or `enrich.js` (the library fixes above were made deliberately, outside the workflow,
  before it ran). No frameworks, no CDN, no external fetch, no build step. No colour
  literals in any template.
- **No hardcoded provenance.** `Census 2011` appears only inside two code comments;
  every rendered provenance string comes from `node.population_note`, which is `''` for
  the 10 of 175 records where the portal states none.
- **Year and estimate class labelled** — "2023-24 — measured", "target 2028-29 planned",
  "As published". Baseline and target are visually distinct and never summed.
- **Enrichment doubles content** (avg HTML ~4.2–7.6 KB bare → ~8.7–12.8 KB enriched),
  confirming the join is doing real work rather than being nominally wired.

---

## 5. Next steps

1. Integrate into `landing/index.html`: load `components.css`, `components.js`,
   `enrich.js`, the four `tpl-*.js`; on district→constituency pick, fetch
   `apc/<code>.json`, call `DASH.enrich(rec, name, apc, index)`, render
   `DASH_TPL[node.archetype](node)`. **Use the enriched path** — the bare path exists
   for resilience, not as the default.
2. Define the real `DASH_PICK_MANDAL` during integration to activate mandal drill-down.
3. Clean up the three surviving copy/style items in §3.
4. Then district (D1–D4) and mandal (M1–M3) templates, per
   `docs/DASHBOARD_ARCHITECTURE.md`.

---

## 6. Process notes

Both structural changes made after the first audit worked, and the evidence is direct:

- **Specifying the data contract instead of the data sources.** Round one described two
  datasets and never said who joined them; four agents invented four incompatible joins
  and 100% of them were dead. Round two shipped `enrich.js` with the contract in its
  header: **zero contract violations across all four templates.** The component API,
  which was precisely specified in both rounds, produced no incompatibilities in either.
- **Giving the shared library an owner.** Round one forbade editing `components.js` to
  stop four parallel agents colliding — correct for collisions, but it orphaned every
  library-level defect; three reviewers found the scaling bug and none could fix it.
  Round two fixed the library upfront and told agents to report library bugs, not fix
  them. Both surviving blockers this round were correctly reported rather than patched
  around, and both turned out to be best fixed in the library or upstream — not in the
  templates at all.

One caution for future runs: **the meta-audit agent died on a session limit in both
rounds**, always after the expensive review work had completed. It is the cheapest agent
in the workflow and the last to run, which is the worst possible position. Either run
the audit as a separate invocation, or do it by hand as here — it is roughly 2% of a
workflow's token cost.
