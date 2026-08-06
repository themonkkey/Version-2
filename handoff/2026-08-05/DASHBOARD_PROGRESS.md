# Dashboard build — progress at pause

**Paused 2026-08-05** (MacBook restart). Everything below is on disk and committed
to the working tree. Nothing is half-written; the only interrupted thing is a
resumable download.

Read `docs/DASHBOARD_ARCHITECTURE.md` first — that is the design. This file is just
"where we stopped".

---

## Resume in one command

```bash
cd ~/swarna-andhra-chatbot && python3 scripts/fetch_apc_data.py
```

It is resumable and skips the 26 constituencies already cached. ~1 request/sec by
design, so the remaining 149 take roughly 18 minutes. Then:

```bash
python3 scripts/classify_templates.py
```

---

## Done and verified

| Artifact | State |
| --- | --- |
| `landing/assets/district_tree.json` | 28 districts → 175 constituencies → 750 mandals |
| `landing/assets/ap_constituencies.geojson` | 175 polygons, 610 KB, 175/175 matched |
| Map drill-down in `landing/index.html` | district → constituency zoom, back button, dropdown synced both ways — tested in browser, no console errors |
| `scripts/build_district_tree.py` | builds the tree |
| `scripts/build_constituency_geojson.py` | builds the boundaries |
| `scripts/fetch_apc_data.py` | harvests the AP portal |
| `scripts/classify_templates.py` | assigns archetypes |
| `docs/DASHBOARD_ARCHITECTURE.md` | the template design |

Theme, fonts and colours were not touched, per the standing instruction.

---

## In flight

**AP portal harvest: 26 of 175 done.** Files land in `landing/assets/apc/<code>.json`.
`_roster.json` (all 175 with their encrypted ids) is already complete, so the slow
discovery work is finished — what remains is the plain per-constituency pull.

District archetypes are final (all 28, they don't depend on the harvest).
Constituency archetypes fill in as the harvest completes.

---

## The find that changed the plan

The AP portal (`apconstituencies.ap.gov.in`) is an Angular front end over a plain
JSON API at `/CONST/api/Home/*`. That means the constituency level is **not**
narrative-only as previously assumed — every constituency has real numbers:

- GCDP baseline 2023-24, target 2028-29, CAGR — total and per sector
- sector shares (agri / industry / services)
- thrust sectors with descriptions
- population, voter count, area, revenue villages, municipal wards
- **the authoritative mandal list per constituency** (`profile.mandals`) — better
  than the mandal names currently derived from PDF filenames, and worth switching
  `build_district_tree.py` over to once the harvest finishes

API quirks worth knowing before touching `fetch_apc_data.py`:
- ids are opaque AES blobs handed out by `constituencieslist`; plaintext ids are
  rejected. No need to decrypt, only to pass back.
- the id's JSON key is inconsistent per endpoint — `encryptedConstId` vs
  `constituencyId` vs `EncryptedConstituencyId`. That is the API's own quirk.
- the list endpoint is `constituencieslist`, one word, lowercase. Every
  camelCase/hyphenated guess 404s.

---

## Corrections made this session — do not undo

1. **28 districts, not 26.** The `district/` vision-doc folder has 26 and is stale.
   `districts_data.json`, the AP portal and iGOD all agree on 28. Markapuram and
   Polavaram are real districts, not sub-groupings of Prakasam/ASR — an earlier
   reading of the folder layout suggested otherwise and was wrong.
2. **Hierarchy is District → Constituency → Mandal**, mandal smallest.
3. **DataMeet boundaries predate the 2014 bifurcation** — all Telangana ACs are
   still filed under `ST_NAME='ANDHRA PRADESH'` (296 rows → 175 after filtering),
   and its district column is the old 13-district layout, so it is ignored
   entirely in favour of the tree's assignment.
4. **District archetypes must classify off `structured_district_data.csv`, not
   `districts_data.json`.** The JSON has only top-5 sectors, ~30% of each economy;
   the first classifier gave junk because of it. Fixed to use the CSV's sector
   aggregates against GDVA.

---

## Next steps, in order

1. Finish the harvest, re-run the classifier, sanity-check the C1–C4 spread.
2. Switch `build_district_tree.py` to the portal's `profile.mandals` for mandal
   names (authoritative) instead of PDF filename parsing.
3. Build the shared component library (§4 of the architecture doc) using existing
   CSS tokens only.
4. Build the four constituency templates, then four district, then three mandal.
5. Wire templates into the map drill-down that already works.

---

## Known open items

- **Mandal level still has no structured numbers.** Only the vision PDFs. Mandal
  templates are narrative-first by necessity — see §5 of the architecture doc.
- **Guntur's `Prathipadu_SC` folder has two misfiled mandal PDFs** (`Guntur_East`,
  `Guntur_West`) that belong to their own constituencies. Source-data issue, not
  blocking; the portal's mandal list will supersede it anyway.
- **GitHub push auth is still unresolved** — see `SESSION_STATE.md` §4. The token
  used last time was to be revoked.
- `corpus_files/gis/assembly_constituencies/` (11.5 MB shapefile) is gitignored as
  a rebuildable artifact; the download URL and CC-BY attribution are documented in
  `build_constituency_geojson.py`.
