#!/usr/bin/env python3
"""Build the district-level dashboard payload.

dashboard_index.json carries only an archetype and three sector shares per
district — enough to choose a template, not enough to draw one. The full picture
is in structured_district_data.csv: 27 sectors x 4 years x 28 districts, with
value / rank / growth / contribution on each cell.

This writes one file per district so the page fetches only what it shows, mirroring
the constituency layer's landing/assets/apc/<code>.json.

Output: landing/assets/dist/<district_key>.json
  {
    key, name,
    years: ["2022-23 (TRE)", ...],
    gddp:  [{year, value, growth, rank}],      # 4-year series — the trajectory
    nddp:  [...], pci: [...], population: [...],
    aggregates: {agri|industry|services: [{year, value, contribution}]},
    sectors: [{name, value, rank, growth, contribution}],   # latest year, all 27
    latest_year, source
  }

    python3 scripts/build_district_dash.py
"""
import csv
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(ROOT, "structured_district_data.csv")
INDEX = os.path.join(ROOT, "landing", "assets", "dashboard_index.json")
OUT_DIR = os.path.join(ROOT, "landing", "assets", "dist")

YEARS = ["2022-23 (TRE)", "2023-24 (SRE)", "2024-25 (FRE)", "2025-26 (FAE)"]
LATEST = "2025-26 (FAE)"

# rows that are totals/derived, not economic sectors — kept out of the sector list
# so a template can never plot the whole against its own parts
HEADLINE = {
    "Gross District Domestic Product (GDDP)": "gddp",
    "Net District Domestic Product (NDDP)": "nddp",
    "Per Capita Income (Rs.)": "pci",
    "Population ('000)": "population",
}
AGGREGATE = {
    "AGRICULTURE & ALLIED SECTOR": "agri",
    "Industry Sector (aggregate)": "industry",
    "Services Sector (aggregate)": "services",
}
NOT_A_SECTOR = set(HEADLINE) | set(AGGREGATE) | {
    "Gross District Value Added (GDVA)",
    "Product Taxes",
    "Product Subsidies",
}


def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def num(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except ValueError:
        return None


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    index = json.load(open(INDEX))
    key_by_norm = {norm(k): k for k in index["districts"]}

    # district -> sector -> year -> cell
    data = {}
    for row in csv.DictReader(open(CSV_PATH)):
        d = data.setdefault(row["district"], {}).setdefault(row["sector"], {})
        d[row["year"]] = {
            "value": num(row["value_rs_cr"]),
            "rank": num(row["rank"]),
            "growth": num(row["growth_pct"]),
            "contribution": num(row["contribution_pct"]),
        }

    written, unmatched = 0, []
    for csv_name, sectors in data.items():
        key = key_by_norm.get(norm(csv_name))
        if not key:
            unmatched.append(csv_name)
            continue

        def series(sector_name):
            cells = sectors.get(sector_name, {})
            return [
                {
                    "year": y,
                    "value": (cells.get(y) or {}).get("value"),
                    "growth": (cells.get(y) or {}).get("growth"),
                    "rank": (cells.get(y) or {}).get("rank"),
                }
                for y in YEARS
            ]

        rec = {
            "key": key,
            "name": index["districts"][key].get("name") or key.replace("_", " "),
            "years": YEARS,
            "latest_year": LATEST,
            "source": "AP district-wise GVA/GDDP workbook",
        }
        for label, out_key in HEADLINE.items():
            rec[out_key] = series(label)

        # The workbook's contribution_pct is this district's share of the STATE
        # total for that sector — Guntur is 2.01% of AP's agriculture. It is NOT
        # agriculture's share of Guntur's own economy, which is 14%. Those two
        # numbers differ by 7x and labelling one as the other would be a serious
        # misstatement, so both are emitted under names that cannot be confused
        # and neither is called "contribution".
        gdva_cells = sectors.get("Gross District Value Added (GDVA)", {})

        def share_of_district(cell, year):
            gdva = (gdva_cells.get(year) or {}).get("value")
            v = (cell or {}).get("value")
            if not gdva or v is None:
                return None
            return round(v / gdva * 100, 2)

        rec["aggregates"] = {}
        for label, out_key in AGGREGATE.items():
            cells = sectors.get(label, {})
            rec["aggregates"][out_key] = [
                {
                    "year": y,
                    "value": (cells.get(y) or {}).get("value"),
                    "pct_of_district": share_of_district(cells.get(y), y),
                    "pct_of_state_sector": (cells.get(y) or {}).get("contribution"),
                }
                for y in YEARS
            ]

        rec["sectors"] = []
        for sector_name, cells in sectors.items():
            if sector_name in NOT_A_SECTOR:
                continue
            cell = cells.get(LATEST) or {}
            if cell.get("value") is None and cell.get("contribution") is None:
                continue
            rec["sectors"].append({
                "name": sector_name,
                "value": cell.get("value"),
                "rank": cell.get("rank"),
                "growth": cell.get("growth"),
                "pct_of_district": share_of_district(cell, LATEST),
                "pct_of_state_sector": cell.get("contribution"),
            })
        rec["sectors"].sort(key=lambda s: -(s["pct_of_district"] or 0))

        json.dump(rec, open(os.path.join(OUT_DIR, key + ".json"), "w"), indent=1)
        written += 1

    print(f"wrote {written} district payloads to {os.path.relpath(OUT_DIR, ROOT)}")
    if unmatched:
        print("  unmatched CSV districts (expected: the state PCI row):", unmatched)


if __name__ == "__main__":
    main()
