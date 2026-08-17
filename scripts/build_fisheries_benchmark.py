#!/usr/bin/env python3
"""Bake the official Fishing & Aquaculture GVA per district, for the calculator.

The fisheries calculator works out a district's GVA from figures the officer
types in. On its own it has no way to say whether the answer it produced is
plausible. This file gives it something to check against: the published estimate
for the same sector, same district, so the tool can show the gap.

Source: landing/assets/dist/<District>.json, the same per-district files the
district dashboards read, which come from the AP district-wise GVA/GDDP
workbook. Only the "Fishing & Aquaculture" line is copied, verbatim.

UNITS. dist/*.json carries value in RUPEES CRORE. The calculator works in
RUPEES LAKH. This file stays in crore and records that in `unit`; the single
conversion (1 crore = 100 lakh) happens in one clearly marked place in the UI.
The lakh/crore mix-up is a known trap on this project, so nothing here is
silently rescaled.

Nothing is computed. Every number is copied from the source file as printed.

Usage:
    python3 scripts/build_fisheries_benchmark.py            # write
    python3 scripts/build_fisheries_benchmark.py --check    # verify only
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST_DIR = os.path.join(ROOT, "landing", "assets", "dist")
OUT = os.path.join(ROOT, "landing", "assets", "fisheries_benchmark.json")

SECTOR = "Fishing & Aquaculture"


def main():
    check = "--check" in sys.argv

    districts = {}
    years, sources, missing = set(), set(), []

    for fn in sorted(os.listdir(DIST_DIR)):
        if not fn.endswith(".json"):
            continue
        with open(os.path.join(DIST_DIR, fn), encoding="utf-8") as fh:
            d = json.load(fh)
        row = None
        for s in d.get("sectors", []):
            if s.get("name") == SECTOR:
                row = s
                break
        if row is None:
            missing.append(d.get("name", fn))
            continue
        districts[d["name"]] = {
            "value_cr": row["value"],                     # as printed, rupees crore
            "rank": row.get("rank"),
            "growth_pct": row.get("growth"),
            "pct_of_district": row.get("pct_of_district"),
        }
        if d.get("latest_year"):
            years.add(d["latest_year"])
        if d.get("source"):
            sources.add(d["source"])

    if missing:
        sys.exit("no %r line in: %s" % (SECTOR, ", ".join(missing)))
    if not districts:
        sys.exit("no districts read from " + DIST_DIR)
    # One year and one source across all 28, or the comparison is not like-for-like.
    if len(years) != 1:
        sys.exit("districts disagree on latest_year: %s" % sorted(years))
    if len(sources) != 1:
        sys.exit("districts disagree on source: %s" % sorted(sources))

    out = {
        "_note": "Official Fishing & Aquaculture GVA per district, copied verbatim "
                 "from landing/assets/dist/*.json. Nothing computed here.",
        "sector": SECTOR,
        "unit": "rupees crore",
        "year": sorted(years)[0],
        "source": sorted(sources)[0],
        "districts": districts,
    }

    print("%-28s %12s %6s %9s" % ("district", "value (cr)", "rank", "growth%"))
    for name in sorted(districts, key=lambda k: -districts[k]["value_cr"]):
        r = districts[name]
        print("%-28s %12.2f %6.0f %9.2f"
              % (name[:28], r["value_cr"], r["rank"] or 0, r["growth_pct"] or 0))
    print("\n%d districts | %s | %s" % (len(districts), out["year"], out["unit"]))

    if check:
        print("--check: verified, nothing written")
        return

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print("wrote", os.path.relpath(OUT, ROOT))


if __name__ == "__main__":
    main()
