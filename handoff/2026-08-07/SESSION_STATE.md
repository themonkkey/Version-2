# Swarna Andhra dashboard — District/Constituency/Mandal build

**Last updated: 2026-08-07.** Written so another Claude (or person) can pick this up
cold. Assumes no memory of any prior session. Read top to bottom before touching
anything.

Repo: `~/swarna-andhra-chatbot` · Remote: `github.com/themonkkey/swarna-andhra-chatbot`
(**public**) · Owner: Aryan Singh, Pahlé India Foundation (PIF).

Prior handoffs: `handoff/2026-07-30/` (chatbot/RAG backend, unrelated to this work),
`handoff/2026-08-05/` (SESSION_STATE.md + DASHBOARD_PROGRESS.md — the start of this
dashboard build; still accurate for how the tree/geojson/archetype system got started,
superseded by this file for current status).

---

## 0. What this is

The Districts page on the landing site (`landing/index.html`) is becoming a real
multi-level dashboard: **District (28) → Constituency (175) → Mandal (~750)**. Click a
district on the map, click a constituency, click a mandal — each level renders its own
archetype-appropriate dashboard, not one generic layout.

**Design doc, read this first:** `docs/DASHBOARD_ARCHITECTURE.md` — why archetypes
exist, the four constituency templates (C1–C4), four district templates (D1–D4), three
mandal templates (M1–M3), and the honesty rules that govern all of them (never invent a
number, always label year/estimate-class, never confuse two similarly-named
percentages).

**Audit doc:** `docs/DASHBOARD_AUDIT.md` — two rounds of adversarial review on the
constituency templates, what failed and what was fixed. Still accurate for C1–C4.
Does NOT cover M1–M3 (reviewed, see §3). D1–D4 now have their own
`docs/DASHBOARD_AUDIT_DISTRICTS.md` (2026-08-10, GO, hand-reviewed after three
workflow attempts died on session limits — see that file's §7).

---

## 1. Current state of the code — READ BEFORE ASSUMING ANYTHING WORKS

**Committed** (`a2f7abc`, latest commit): tree/geojson build, all 4 constituency
templates + component library + data-join layer, all 4 district templates (unreviewed),
mandal roster + first-draft M1–M3 templates, three-level drill-down wired into
`index.html`.

**NOT yet committed** — sitting in the working tree right now:
```
 M landing/assets/dash/enrich.js       (mandal contract's header comment corrected)
 M landing/assets/dash/tpl-m1.js       (false "no data" claims removed)
 M landing/assets/dash/tpl-m2.js       (same, + a real honesty bug fixed)
 M landing/assets/dash/tpl-m3.js       (same, + a false provenance claim fixed)
?? landing/assets/mandal_data/         (543 NEW extracted mandal-level JSON files)
?? scripts/extract_mandal_data.py      (the extractor that produced them)
```
**Commit this working tree before doing anything else** if you want a clean base to
build from — the fixes are correctness-critical (see §2) and the extraction is a real
deliverable (§4). Suggested message: something like "Fix false mandal-data-does-not-
exist claims; add mandal GVA/demographic extractor (543/548 parsed)".

---

## 2. THE BIG THING THAT HAPPENED THIS SESSION — read this whole section

Early in the mandal-template work, I (the previous instance) ran `ls` on the mandal PDF
folders, saw only `.pdf` files, and concluded "these are prose vision documents, no
structured data exists at mandal level." That assumption was **never verified** and
turned out to be **false**. It got baked into:

- `docs/DASHBOARD_ARCHITECTURE.md` §5 (mandal templates are "narrative-first by
  necessity") — this framing is now wrong and the doc has not been updated yet
- `enrich.js`'s `enrichMandal()` contract (header comment corrected this session, but
  the actual function still returns no numeric mandal fields — see §4)
- All three M1/M2/M3 template files, which rendered live text like *"No economic
  figures are published at mandal level... none can be derived from what exists"* on
  every one of 718 mandal pages

**The user caught this by asking "why does mandal dont have any data?"** — a good
prompt to re-verify a load-bearing assumption rather than defend it. Opening one PDF
with `pdfplumber` showed a full **Mandal GVA Statement** — 27-row sector/sub-sector
breakdown (same structure as the district workbook), plus demographics, land use, land
holdings, crops, irrigation, education. Sampled 8 PDFs across districts: **8/8 had it.**

**Fixed this session** (uncommitted, see §1): every false "no data exists" claim in
`tpl-m1.js` / `tpl-m2.js` / `tpl-m3.js` / `enrich.js`'s header was rewritten to say the
true thing — *"figures are not yet loaded into this dashboard"* / *"not yet extracted
from the PDFs"* — verified by rendering all 718 mandal pages and grepping for the false
phrasing (0 hits, was 718).

**What's still wrong and needs fixing next:** `enrich.js`'s `enrichMandal()` function
itself still has no code path to attach real mandal figures — only the comment above it
was corrected. The M1–M3 *templates* still only render inherited constituency figures.
Real mandal data exists now (§4) but nothing pipes it into the mandal pages yet. That's
the next concrete task — see §6.

**If you touch mandal anything, re-read this section first.** Don't re-introduce a "no
data at this level" framing anywhere.

---

## 3. Constituency + District + Mandal templates — status per level

### Constituency (C1–C4) — DONE, reviewed twice, integrated, working

- `landing/assets/dash/components.js` + `.css` — shared component library
- `landing/assets/dash/enrich.js` → `DASH.enrich()` — joins `dashboard_index.json`
  (always-present, 12 fields) with `apc/<code>.json` (rich portal payload, fetched on
  demand) into one documented contract, `DASH.ENRICHED_KEYS`
- `tpl-c1.js` (urban/services ≥55%), `tpl-c2.js` (agrarian, agri ≥40%), `tpl-c3.js`
  (industrial, industry ≥35%), `tpl-c4.js` (mixed)
- Two full adversarial review rounds (see `docs/DASHBOARD_AUDIT.md`). Round 1: 3 of 4
  FAILED, 45 findings, root cause was templates reading fields that existed nowhere.
  Round 2 after I built the `enrich.js` contract properly: **0 contract violations
  across all four**, two upgraded to PASS_WITH_FIXES. Verdict: **GO for integration.**
- **Live and wired.** Clicking a district then a constituency on the map renders the
  right template. Verified: 175 constituencies × {bare, enriched} = 350 renders, 0
  throws, 0 empty-states on the enriched path.
- Two library bugs found and fixed directly (not via agent, to avoid orphaning them):

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

  `compositionBars` was encoding rank-not-share (fixed, now defaults to
  `scale:'share'`, track is 100%); wrong fallback sector colours (fixed to match the
  portal's real values, `agri #16A34A / industry #FF8A00 / services #C93A2C`).

### District (D1–D4) — BUILT, working live, **REVIEWED 2026-08-10, GO**

- `tpl-d1.js` (metro/urban core, 6 districts), `tpl-d2.js` (agrarian, 11), `tpl-d3.js`
  (industrial, 2), `tpl-d4.js` (emerging/agency, 9 — deliberately leads with
  trajectory/composition, not rank, because these 9 districts include the 3 scheduled/
  agency ones and ranking them on income alone reads as a scoreboard of failure)
- Data: `landing/assets/dist/<district_key>.json` (28 files, built by
  `scripts/build_district_dash.py`) + `DASH.enrichDistrict()` in `enrich.js`
- **Important nuance baked into the contract:** the district workbook's
  `contribution_pct` column means "this district's share of the STATE total for that
  sector" (Guntur agriculture = 2.01% of AP's agriculture), **NOT** "this sector's share
  of the district's own economy" (Guntur agriculture is actually 14.04% of Guntur).
  These differ 7×. The contract emits both under unambiguous names —
  `pct_of_district` vs `pct_of_state_sector` — specifically so a template can't
  conflate them. If you touch district templates, do not let this collapse into one
  field.
- **The review workflow for D1–D4 died on session limits three times** across two
  sessions before producing a single finding (~1.1M tokens, zero output). Done by
  hand instead on 2026-08-10 — see `docs/DASHBOARD_AUDIT_DISTRICTS.md`. Verdict: GO.
  Zero contract violations across all four, zero percentage-trap confusion (the
  pct_of_district/pct_of_state_sector distinction above), zero hex colour literals,
  68 renders with zero throws, the DASH_PICK_CONSTITUENCY handler checked and
  confirmed wired (not just assumed by analogy to the earlier DASH_PICK_MANDAL bug).
  One non-blocking gap noted: bare-path empty-state counts are high, same as every
  other level's bare path, and not the path integration actually serves.

### Mandal (M1–M3) — BUILT, reviewed once, integrated, **now correcting a wrong premise**

- `tpl-m1.js` (rural, 632 of 718 roster entries), `tpl-m2.js` (urban, 121, portal's own
  `-U` marker), `tpl-m3.js` (scheduled/agency, 41 — mandals in the 3 agency districts,
  overriding the rural/urban split regardless of the portal's marker)
- Roster: `landing/assets/mandal_index.json`, built by `scripts/build_mandal_index.py`
  from the AP portal's `profile.mandals` string per constituency (authoritative — 47 of
  794 entries carry no rural/urban marker and are recorded `kind:"unknown"`, never
  guessed)
- One review round already caught and got fixed: M2 asserted "an urban mandal sits
  inside a services-weighted economy" — false for 65 of 121 (Pedana is 77.75%
  agriculture, 12.93% services); M3 claimed scheduled status was "recorded in the
  mandal roster" — it isn't, it's derived from the district being one of 3 hardcoded
  agency districts. Both fixed and verified (see git commit `a2f7abc`'s message for
  detail).
- **Now mid-correction on a bigger issue:** see §2. The three templates currently
  render only *inherited constituency figures* with heavy "not yet loaded" framing.
  Real mandal-level figures exist and are now extracted (§4) but not yet wired in.

---

## 4. NEW this session: real mandal-level data extraction

`scripts/extract_mandal_data.py` parses the mandal vision PDFs directly.
**543 of 548 attempted PDFs parsed successfully (99.1%)**, output to
`landing/assets/mandal_data/<slug>.json` (slug matches `mandal_index.json`'s own
slugs, e.g. `mangalagiri__duggirala`).

Two distinct table layouts in the wild, both handled:
- **Layout A** ("Gross Mandal Domestic Product Details") — 482 files. One combined
  table: Sl.No / Broad Sector / Sub Sector / GVA / Contribution%, with GMVA, Product
  Taxes/Subsidies, GMDP, NMDP, Projected Population, Per Capita Income as trailing rows
  in the same table.
- **Layout B** ("Overall GVA Sectoral Breakup") — 56 files. A 3-row sector summary
  table + one sub-sector table per broad sector.

Each file also carries demographics where extractable: population by gender (with a
male+female≈total sanity check — an early version had a bug that let a population
table wrongly record female > total; fixed), literacy, area.

**5 failures, all genuine and visible in `landing/assets/mandal_data/_report.json`**,
not silently dropped: 2 are scanned/image PDFs with zero extractable text (would need
OCR, out of scope), 1 fails validation (fewer than 2 broad sectors recovered), 2 threw
a pdfplumber "Invalid octal" exception on malformed PDF streams.

**Validated, not just parsed:**
- Every accepted parse passes: sub-sector rows sum to within ~1–2% of the declared
  broad-sector total (Layout A) or recovers ≥2 of the 3 broad sectors (Layout B)
- Random 25-file spot check: sector shares sum to 98–100.5%, no anomalies
- Cross-checked Duggirala mandal's GMDP (₹1,625 Cr, converting from the PDF's native
  Lakhs) against its parent Mangalagiri constituency's GCDP (₹11,843 Cr, across 3
  mandals) — right order of magnitude, so the extraction is measuring the right thing

**CRITICAL UNIT NOTE, easy to get wrong:** the PDFs state GVA in **Lakhs**. Every other
figure on this site (`fmtCr`, district/constituency GCDP) is in **Crores**. 1 Crore =
100 Lakhs. `extract_mandal_data.py`'s output is raw Lakhs, unconverted — **whatever
wires this into `enrichMandal()` must divide by 100** before calling `DASH.fmtCr()`, or
every mandal figure will render 100× too large. This is not yet done anywhere.

---

## 5. Next concrete tasks, in priority order

1. **Commit the working tree** (§1) so there's a clean base.
2. **Wire real mandal data into `enrichMandal()`** in `enrich.js`, then update
   `tpl-m1.js`/`m2`/`m3` to use it instead of only inherited constituency figures.
   Remember the Lakhs→Crore conversion (§4). This turns mandal from a thin
   inherited-context page into a real dashboard — genuinely the most valuable
   remaining piece, since mandal-level GVA didn't exist in the site's data model
   until today.
   - Consider whether M1/M2/M3's archetype split should be re-derived now that real
     sector shares exist per mandal (currently it's purely the portal's rural/urban
     marker) — that's a design call, not obviously required, flag it to the user.
   - Once real data is wired in, the "not yet loaded" framing in all three templates
     needs to change again — to actually show the data, not just stop denying it exists.
3. **Update `docs/DASHBOARD_ARCHITECTURE.md` §5** — it currently says mandal templates
   are "narrative-first by necessity" because no data exists. That premise is gone.
4. **Run the adversarial review on D1–D4** — this never completed (§3). The prior
   attempts died on session limits (`workflow "Build the four district archetype..."`,
   both invocations). Options: retry the same Workflow script (it's resumable —
   `resumeFromRunId` skips completed agents), or do the review by hand the way the
   audit was done for C1–C4 round 2 and D1-D4's manual spot-check. Given agent session
   limits have killed this twice, hand-review might be more reliable.
5. Once mandal templates use real data and D1–D4 are reviewed, do a final full-site
   pass: all 28 districts × 175 constituencies × ~718 mandals rendered, checked for
   throws and honesty-rule violations, before calling the three-level dashboard done.

---

## 6. Known gaps / non-blocking issues, not yet actioned

- 173 of 718 mandal roster entries have no matched vision-document PDF at all (visible
  in `mandal_index.json`'s `_counts.without_pdf`) — no GVA extraction possible for
  those regardless of parser quality.
- `mui-charts.js` (673 KB) loads with `defer` on every page including Home/About, where
  nothing uses it. Only the Districts page needs it. Not fixed — flagged, not urgent.
- Dash assets are cache-busted with `?v=2026-08-06a` in `index.html`. **Bump this
  string whenever any file under `landing/assets/dash/` changes**, or returning
  visitors can get a stale `enrich.js`/template mismatch that fails silently. This bit
  me repeatedly during dev — don't skip it.
- A real (not import-related) bug was found and fixed this session: `index.html`'s
  initial page router called `initMap()` before `let mapReady` was declared further
  down the same script, throwing a TDZ `ReferenceError` on any direct load or refresh
  of `#districts`. Fixed by deferring the initial route one tick
  (`setTimeout(()=>go(...), 0)`). If you ever see "Cannot access 'X' before
  initialization" on page load, check for this pattern elsewhere in the same script.
- GitHub push auth is still unresolved (carried over from `handoff/2026-08-05/`) — `gh`
  CLI has no push access to `themonkkey/swarna-andhra-chatbot` under the currently
  authenticated account. Get a fresh token or proper `gh auth login` before pushing.

---

## 7. Orientation for a cold-start Claude

1. Read this file top to bottom (you're here).
2. Read `docs/DASHBOARD_ARCHITECTURE.md` and `docs/DASHBOARD_AUDIT.md`.
3. Check `git status` — the working tree almost certainly still has the uncommitted
   mandal fixes from §1 unless someone has committed since. Read the diff before
   assuming what state the mandal templates are in.
4. Re-read §2 before touching anything mandal-related. Do not let "no data exists at
   mandal level" creep back into any code or doc.
5. If picking up §5 task 2 (wire real mandal data in): start by reading
   `landing/assets/mandal_data/mangalagiri__duggirala.json` as a concrete example, then
   `enrichMandal()` in `enrich.js` to see the current (numbers-free) contract it needs
   to grow into.
