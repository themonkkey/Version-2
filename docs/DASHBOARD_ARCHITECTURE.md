# Multi-level dashboard architecture

**Status: design, 2026-08-05.** Covers the District → Constituency → Mandal dashboard
on the landing site. Read alongside `handoff/2026-08-05/SESSION_STATE.md`.

---

## 1. Why templates, not one layout

A single layout misrepresents most places. Three real constituencies from the first
harvest batch:

| Constituency | Agri | Industry | Services | Reality |
| --- | --- | --- | --- | --- |
| Achanta | **49%** | 18% | 33% | delta farmland, aquaculture |
| Addanki | 25% | **50%** | 25% | agro-processing belt |
| Anantapur Urban | 0.3% | 20% | **80%** | municipal corporation, colleges |

Anantapur Urban's agriculture is ₹19 crore — 0.28% of its economy. A layout that
gives agriculture a third of the screen is lying about that place. Achanta's
aquaculture is the story and a services-first layout buries it.

So: **the layout is chosen by what the place actually is.** Same components, same
theme, different arrangement and emphasis. Facts and numbers swap by name; the
*template* swaps by economic structure.

---

## 2. Levels and their data

| Level | Count | Numeric source | Richness |
| --- | --- | --- | --- |
| District | 28 | `districts_data.json` (GDDP, PCI, 11 sectors, ranks, 4 years) | high |
| Constituency | 175 | AP portal API → `landing/assets/apc/<code>.json` | high (GCDP, 3 sectors, baseline+target, thrust sectors, demographics) |
| Mandal | ~750 | vision-doc PDFs only | low — names + narrative, no structured numbers yet |

The constituency layer changed the picture completely. Before the AP portal API we
had names only; now every constituency has GCDP baseline (2023-24), target
(2028-29), CAGR per sector, sector shares, thrust sectors, population, voters,
area, revenue villages, and MLA history.

**Mandal remains the weak level.** Its numbers do not exist in structured form
anywhere we have found. Mandal templates are therefore narrative-first by
necessity, not by choice — see §5.

---

## 3. Archetype classification

Deterministic, from the numbers. No hand-curation of 175 places, and re-running
the classifier after a data refresh re-derives everything.

```
shares  = share_current    (agri %, industry %, services %)
urban   = municipal_wards > 0 or municipalities > 0
density = population / area
```

### Constituency archetypes (4)

| # | Archetype | Rule | Leads with |
| --- | --- | --- | --- |
| C1 | **Urban / Services-led** | services ≥ 55% | service composition, density, civic infrastructure, real estate & logistics |
| C2 | **Agrarian** | agri ≥ 40% | crop & aqua mix, land use, irrigation, agri value chain, post-harvest |
| C3 | **Industrial** | industry ≥ 35% | MSME base, industrial estates, manufacturing sub-sectors, power & logistics |
| C4 | **Mixed / Transitional** | none of the above dominant | balanced tri-sector view, growth-gap vs district, which sector is pulling ahead |

Ties resolve in order C1 → C2 → C3 → C4 (urban signal wins, because a services-heavy
municipal seat behaves like a city regardless of what else is present).

### District archetypes (4)

Same idea one level up, but off **`structured_district_data.csv`**, not
`districts_data.json`. The JSON carries only each district's top-5 sectors, which
sum to roughly 30% of its economy — far too partial to classify on, and an early
version of the classifier produced junk because of it. The CSV has the three
official sector aggregates against GDVA for all 28 districts at 2025-26 (FAE).

| # | Archetype | Rule |
| --- | --- | --- |
| D1 | **Metro / Urban core** | services-led **and** PCI in top 8 |
| D2 | **Agrarian heartland** | agriculture & allied ≥ 35% of GDVA |
| D3 | **Industrial corridor** | industry ≥ 30% of GDVA |
| D4 | **Emerging / Agency** | bottom-8 PCI, or a scheduled/agency district (ASR, Parvathipuram Manyam) |

D4 exists because agency districts genuinely need a different frame — forest
economy, tribal welfare schemes and connectivity matter more than sector share, and
ranking them on GDDP alone reads as a scoreboard of failure rather than a plan.

### Mandal archetypes (3)

Constrained by having no numbers. Derived from the parent constituency's archetype
plus what the vision PDF actually contains:

| # | Archetype | When |
| --- | --- | --- |
| M1 | **Rural / agri mandal** | parent is C2, or the PDF's plan is crop/irrigation-led |
| M2 | **Urban / municipal mandal** | mandal contains a municipality or corporation ward |
| M3 | **Agency / tribal mandal** | scheduled area |

---

## 4. Shared component library

Every template composes from one set. Nothing is bespoke per place, so a fix or a
restyle lands everywhere at once, and the existing theme, fonts and colours are
never touched.

| Component | Purpose |
| --- | --- |
| `stat-card` | one headline number + delta (GCDP, PCI, population, voters) |
| `sector-donut` | 3- or 11-way share, using the portal's own sector colours |
| `growth-bullet` | baseline → target with CAGR, per sector — the core Vision-2029 visual |
| `trajectory-line` | 4-year district series (district level only; constituencies have 2 points) |
| `rank-strip` | this place vs its peers, with the peer set named |
| `thrust-chips` | thrust sectors, from the portal |
| `composition-bars` | sector contribution ranking (already built for districts) |
| `narrative-block` | portal/PDF prose, sanitised HTML |
| `drill-list` | children (district→constituencies, constituency→mandals) |
| `source-note` | provenance + year for every figure |

---

## 5. Template compositions

Order matters — the first two rows are what a district officer sees without
scrolling, and they differ by archetype.

**C1 Urban / Services-led** — `stat-card`×4 (GCDP, PCI proxy, population, density) →
`sector-donut` (services exploded) → `growth-bullet` services-first →
`thrust-chips` → civic infrastructure `narrative-block` → `drill-list`.
Agriculture is present but demoted to a single row; it is not the story.

**C2 Agrarian** — `stat-card`×4 (GCDP, agri share, area, revenue villages) →
crop/aqua `composition-bars` → `growth-bullet` agri-first →
land-use `narrative-block` → `thrust-chips` → `drill-list`.

**C3 Industrial** — `stat-card`×4 (GCDP, industry share, CAGR, workforce proxy) →
`growth-bullet` industry-first (the steepest curve is the point) →
manufacturing `composition-bars` → `thrust-chips` → connectivity `narrative-block`.

**C4 Mixed** — `stat-card`×4 → three equal `sector-donut`s side by side →
`growth-bullet` all three → `rank-strip` vs district → `thrust-chips`.
The comparison *is* the content, so nothing gets promoted.

District templates mirror these with the 11-sector split and `trajectory-line`
instead of a 2-point bullet. Mandal templates are `narrative-block`-led with a
`stat-card` row only where the PDF yields numbers, and always carry a
`source-note` saying the figures are constituency-level.

---

## 6. Honesty rules

Non-negotiable, because this is government-facing and the numbers get quoted.

1. **Never invent a number to fill a slot.** A template that cannot fill a
   component drops the component. Empty states say what is missing and why.
2. **Label the year and the estimate class.** District figures are 2025-26 (FAE);
   constituency GCDP is 2023-24 baseline against a 2028-29 target. These are not
   the same vintage and must never share an unlabelled axis.
3. **Targets are targets.** Baseline is measured, 2028-29 is a plan. They render
   differently (solid vs. outlined) and are never summed into one figure.
4. **Mandal numbers are inherited, not measured** — say so on every mandal card
   that shows a figure from its parent.
5. **Attribute the source.** AP Assembly Constituencies portal for constituency
   data, the district workbook for district data, DataMeet CC-BY for boundaries.

---

## 7. Build order

1. ~~District → Constituency → Mandal tree~~ — done, `district_tree.json`
2. ~~Constituency boundaries~~ — done, `ap_constituencies.geojson`, 175/175
3. ~~Harvest AP portal data~~ — `scripts/fetch_apc_data.py`, running
4. Classifier → `scripts/classify_templates.py`, writes archetype onto each node
5. Component library — one CSS/JS module, existing tokens only
6. Four constituency templates, then four district, then three mandal
7. Wire to the map drill-down already built
