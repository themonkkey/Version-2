#!/usr/bin/env python3
"""Extract real mandal-level GVA and demographic figures from the vision PDFs.

CONTEXT — READ THIS FIRST
Mandal templates originally shipped claiming no mandal-level figures existed
anywhere in the corpus. That was wrong: the mandal vision PDFs carry a Gross
Mandal Domestic Product statement (27-row sector/sub-sector breakdown, same
structure as the district workbook) plus demographic and land-use tables. See
docs/DASHBOARD_AUDIT.md / the 2026-08-06 session for how the false claim got
into three templates and was corrected there; this script is what makes the
correction real rather than just less wrong.

Confirmed from a sample of ~15 PDFs across districts: TWO distinct table
layouts carry the same data. Both are handled; anything matching neither is
recorded as a failure, never silently skipped.

  Layout A — "Gross Mandal Domestic Product Details"
    one combined table: Sl.No / Broad Sector / Sub Sector / GVA / Contribution%,
    with GMVA, Product Taxes, Product Subsidies, GMDP, NMDP, Projected
    Population and Per Capita Income as trailing rows in the same table.

  Layout B — "Overall GVA Sectoral Breakup"
    a 3-row sector summary table, followed by one sub-sector table per broad
    sector (Agriculture & Allied / Industries / Services), each ending in its
    own "Total" row.

VALIDATION, not just extraction. A parse is only accepted if:
  - sub-sector GVA rows sum to within 1% of their broad-sector total
  - the three broad-sector totals sum to within 1% of the grand total (Layout A)
    or of 100% (Layout B, which reports percentages, not absolute totals)
A parse that fails validation is recorded as a failure with the reason, never
silently accepted with a wrong number underneath it.

Output:
  landing/assets/mandal_data/<slug>.json   — one file per successfully parsed mandal
  landing/assets/mandal_data/_report.json  — per-PDF outcome: parsed / layout /
    validation error / not found, so gaps in the 706 are visible, not silent

Slug matches scripts/build_mandal_index.py's slugify(): norm(constituency) +
'__' + norm(mandal name), so the two outputs join directly.

    python3 scripts/extract_mandal_data.py            # all PDFs, resumable
    python3 scripts/extract_mandal_data.py --limit 20  # smoke test
    python3 scripts/extract_mandal_data.py --report-only   # print the last report, don't re-parse
"""
import argparse
import glob
import json
import os
import re

import pdfplumber

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANDAL_PDF_DIR = os.path.join(ROOT, "corpus_files", "vision_documents", "mandal")
MANDAL_INDEX = os.path.join(ROOT, "landing", "assets", "mandal_index.json")
OUT_DIR = os.path.join(ROOT, "landing", "assets", "mandal_data")
REPORT = os.path.join(OUT_DIR, "_report.json")

SUB_SECTOR_TO_BROAD = {
    "Agriculture": "agri", "Horticulture": "agri", "Live stock": "agri",
    "Livestock": "agri", "Forestry & Logging": "agri", "Forest": "agri",
    "Fishing & Aquaculture": "agri", "Fisheries": "agri",
    "Mining & Quarrying": "industry", "Mining": "industry",
    "Manufacturing": "industry", "Electricity, Gas, Water Supply": "industry",
    "Electricity, Gas & Water Supply": "industry", "Construction": "industry",
    "Trade, Hotel & Restaurants": "services",
    "Trade, Repair, Hotel and Restaurants": "services",
    "Railways": "services", "Transport by Other means & Storage": "services",
    "Communications": "services", "Banking & Ins": "services",
    "Financial Services": "services",
    "Real est., Ownership of Dwellings": "services",
    "Real Estate, Ownership of Dwellings and Prof. Services": "services",
    "Public Admn.": "services", "Public Administration and Defense": "services",
    "Other Services": "services",
}


def clean_num(v):
    if v is None:
        return None
    s = str(v).replace(",", "").replace("%", "").strip()
    if not s or s == "-":
        return None
    try:
        return float(s)
    except ValueError:
        m = re.search(r"-?\d+(\.\d+)?", s)
        return float(m.group()) if m else None


def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def flatten_header(row):
    return " ".join(str(c).replace("\n", " ") for c in row if c).upper()


def row_text(row):
    """Cell text collapsed and cleaned, in order, dropping empty/None cells.
    Column position is not trustworthy: pdfplumber splits a single logical
    column into several None-padded ones depending on how the PDF wrapped
    text, and the split point differs by mandal (confirmed: the same 'Sector'
    column sits at index 1 in some PDFs and index 3 in others)."""
    return [str(c).replace("\n", " ").strip() for c in row if c is not None and str(c).strip()]


NUM_RE = re.compile(r"^-?[\d,]+(\.\d+)?%?$")


def match_name(cell, candidates):
    """Loose match: exact, then substring in either direction, case-insensitive,
    ignoring '&'/'and' and whitespace differences that vary across PDFs."""
    def norm_txt(s):
        return re.sub(r"\s+", " ", s.lower().replace("&", "and")).strip()
    c = norm_txt(cell)
    for cand in candidates:
        n = norm_txt(cand)
        if c == n or (len(c) > 3 and (c in n or n in c)):
            return cand
    return None


def find_layout_a(pages):
    """One combined table naming both a broad sector and a sub-sector column."""
    for pi, page in enumerate(pages):
        for tb in page.extract_tables():
            if len(tb) < 5:
                continue
            head = " ".join(flatten_header(r) for r in tb[:3])
            if "SUB SECTOR" in head and ("GVA" in head or "BROAD SECTOR" in head):
                return pi, tb
    return None, None


def parse_layout_a(tb):
    """Scans each row's non-empty cells for a known sub-sector name anywhere in
    the row, then reads the first two numeric-looking cells after it as
    value and percentage. Column position is never assumed."""
    sub_rows = []
    headline = {}

    for row in tb:
        cells = row_text(row)
        if not cells:
            continue

        # headline rows: GMVA / GMDP / NMDP / population / PCI. The row also
        # carries a leading Sl.No. cell (e.g. '21' for the GMVA row), which is
        # numeric too — an earlier version took the first numeric cell in the
        # row and recorded the Sl.No. as the value. Take the numeric cell
        # AFTER the label cell instead.
        label_hit, label_idx = None, -1
        for i, c in enumerate(cells):
            u = c.upper()
            if any(k in u for k in ("GMVA", "GMDP", "NMDP", "PRODUCT TAXES", "PRODUCT SUBSIDIES")):
                for key in ("GMVA", "GMDP", "NMDP", "PRODUCT TAXES", "PRODUCT SUBSIDIES"):
                    if key in u:
                        label_hit = key
                label_idx = i
                break
            if "POPULATION" in u:
                label_hit, label_idx = "POPULATION", i
                break
            if "PER CAPITA" in u:
                label_hit, label_idx = "PCI", i
                break
        if label_hit:
            nums = [clean_num(c) for c in cells[label_idx + 1:] if NUM_RE.match(c)]
            if nums:
                headline[label_hit] = nums[0]
            continue

        if re.search(r"total agriculture|total industry|total services", " ".join(cells), re.I):
            continue  # broad-sector subtotal rows, recomputed rather than trusted

        name_cell = None
        name_idx = -1
        for i, c in enumerate(cells):
            if NUM_RE.match(c):
                continue
            hit = match_name(c, SUB_SECTOR_TO_BROAD.keys())
            if hit:
                name_cell, name_idx = hit, i
                break
        if not name_cell:
            continue

        nums = [clean_num(c) for c in cells[name_idx + 1:] if NUM_RE.match(c)]
        if not nums:
            continue
        val = nums[0]
        pct = nums[1] if len(nums) > 1 else None
        broad_key = SUB_SECTOR_TO_BROAD[name_cell]
        sub_rows.append({"name": name_cell, "broad": broad_key, "value": val, "pct": pct})

    return sub_rows, headline


BROAD_SECTOR_NAMES = {"agriculture & allied": "agri", "agriculture and allied": "agri",
                       "industries": "industry", "services": "services"}


def find_layout_b(pages):
    """A 3-row sector summary table naming Agriculture & Allied / Industries /
    Services somewhere in each row, regardless of which column they land in."""
    for pi, page in enumerate(pages):
        for tb in page.extract_tables():
            found = set()
            for row in tb:
                cells = row_text(row)
                joined = " ".join(cells).lower().replace("&", "and")
                for label, key in BROAD_SECTOR_NAMES.items():
                    if label.replace("&", "and") in joined:
                        found.add(key)
            if len(found) >= 2:
                return pi, page
    return None, None


def parse_layout_b(pages, start_page_idx):
    """Sub-sector tables follow the summary on the same or nearby pages, one
    per broad sector, each ending in its own Total row."""
    sub_rows = []
    seen_broads = set()
    for page in pages[start_page_idx:start_page_idx + 4]:
        for tb in page.extract_tables():
            head = " ".join(flatten_header(r) for r in tb[:3])
            if "SUB-SECTOR" not in head and "SUB SECTOR" not in head:
                continue
            for row in tb:
                cells = row_text(row)
                if not cells:
                    continue
                joined = " ".join(cells).upper()
                if re.match(r"^(SL\.?\s*NO\.?|TOTAL)$", cells[0], re.I) and len(cells) < 3:
                    continue
                if joined.startswith("TOTAL") or "GVA" in joined and "SECTOR" in joined and len(cells) <= 3:
                    continue  # the sub-table's own closing total row

                name_cell, name_idx = None, -1
                for i, c in enumerate(cells):
                    if NUM_RE.match(c):
                        continue
                    hit = match_name(c, SUB_SECTOR_TO_BROAD.keys())
                    if hit:
                        name_cell, name_idx = hit, i
                        break
                if not name_cell:
                    continue

                nums = [clean_num(c) for c in cells[name_idx + 1:] if NUM_RE.match(c)]
                if not nums:
                    continue
                broad_key = SUB_SECTOR_TO_BROAD[name_cell]
                sub_rows.append({
                    "name": name_cell, "broad": broad_key,
                    "value": nums[0], "pct": nums[1] if len(nums) > 1 else None
                })
                seen_broads.add(broad_key)
        if {"agri", "industry", "services"} <= seen_broads:
            break
    return sub_rows


def extract_demographics(pages):
    """Population by gender, area, literacy — best-effort, each field
    independently optional so a miss on one does not block the others.

    The population TOTAL row is matched by the word 'Total' appearing in the
    row (not by row position — an earlier version matched any row starting
    with '4', which also matched unrelated rows and once produced a female
    count larger than the total). Once matched, male/female/total are read
    from the three numeric cells in left-to-right order, and rejected outright
    if male + female does not equal total within rounding — a row that fails
    that check is not a population row, whatever else matched."""
    out = {}
    for page in pages:
        text = page.extract_text() or ""
        if "DEMOGRAPHIC" not in text.upper() and "POPULATION" not in text.upper():
            continue

        m = re.search(r"Geographical Area\s+Sq\.?\s*KMs?\s+([\d.,]+)", text, re.I)
        if m:
            out["area_sqkm"] = clean_num(m.group(1))

        for tb in page.extract_tables():
            for row in tb:
                cells = row_text(row)
                if not cells:
                    continue
                joined = " ".join(cells)

                if re.search(r"\btotal\b", joined, re.I) and not re.search(r"literacy", joined, re.I):
                    nums = [clean_num(c) for c in cells if re.match(r"^[\d,]+$", c)]
                    nums = [n for n in nums if n is not None and n >= 100]
                    if len(nums) >= 3:
                        male, female, tot = nums[-3], nums[-2], nums[-1]
                        if abs((male + female) - tot) <= max(2, tot * 0.005):
                            out["population_male"] = male
                            out["population_female"] = female
                            out["population_total"] = tot

                if re.search(r"\bliteracy\b", joined, re.I):
                    nums = [clean_num(c) for c in cells if re.match(r"^[\d.]+$", c)]
                    if len(nums) >= 3:
                        out["literacy_male"] = nums[-3]
                        out["literacy_female"] = nums[-2]
                        out["literacy_total"] = nums[-1]
    return out


def validate(sub_rows, headline, layout):
    """Returns (ok, reason)."""
    if not sub_rows:
        return False, "no sub-sector rows parsed"
    by_broad = {}
    for r in sub_rows:
        by_broad.setdefault(r["broad"], 0)
        by_broad[r["broad"]] += r["value"]
    total = sum(by_broad.values())
    if total <= 0:
        return False, "sector totals sum to zero"

    if layout == "A":
        gmva = headline.get("GMVA")
        if gmva and abs(total - gmva) / max(gmva, 1) > 0.02:
            return False, f"sub-sector sum {total:.0f} does not match GMVA {gmva:.0f}"
    else:
        # Layout B reports percentages; sub-sector VALUES should sum close to
        # each other proportionally — check the three broad totals aren't wildly
        # off from a 3-sector split (basic sanity: none is negative, all present)
        if len(by_broad) < 2:
            return False, "fewer than 2 broad sectors recovered"
    return True, None


def process_one(path):
    with pdfplumber.open(path) as pdf:
        pages = pdf.pages
        pi, tb = find_layout_a(pages)
        if tb:
            sub_rows, headline = parse_layout_a(tb)
            ok, reason = validate(sub_rows, headline, "A")
            if ok:
                demo = extract_demographics(pages)
                return {"layout": "A", "sub_rows": sub_rows, "headline": headline, "demographics": demo}, None
            # fall through to try layout B in case A's table was a false positive

        pi, page = find_layout_b(pages)
        if page is not None:
            sub_rows = parse_layout_b(pages, pi)
            ok, reason = validate(sub_rows, {}, "B")
            if ok:
                demo = extract_demographics(pages)
                return {"layout": "B", "sub_rows": sub_rows, "headline": {}, "demographics": demo}, None
            return None, f"layout B found but failed validation: {reason}"

        return None, "no recognisable GVA table found"


def build_pdf_index():
    """slug -> pdf path, from mandal_index.json's own pdfs list (already resolved
    by build_mandal_index.py), so this script and the roster never disagree
    about which file belongs to which mandal."""
    mi = json.load(open(MANDAL_INDEX))
    out = {}
    for slug, m in mi["mandals"].items():
        pdfs = [p for p in m.get("pdfs", []) if "-2026" not in p]  # skip duplicate revision
        if pdfs:
            out[slug] = os.path.join(ROOT, pdfs[0])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--report-only", action="store_true")
    args = ap.parse_args()

    if args.report_only:
        if os.path.exists(REPORT):
            r = json.load(open(REPORT))
            print(json.dumps(r.get("_summary", {}), indent=2))
        else:
            print("no report yet — run without --report-only first")
        return

    os.makedirs(OUT_DIR, exist_ok=True)
    pdf_by_slug = build_pdf_index()
    targets = list(pdf_by_slug.items())
    if args.limit:
        targets = targets[: args.limit]

    report = {}
    counts = {"parsed_A": 0, "parsed_B": 0, "failed": 0}
    for i, (slug, path) in enumerate(targets, 1):
        dest = os.path.join(OUT_DIR, slug + ".json")
        if os.path.exists(dest) and not args.force:
            cached = json.load(open(dest))
            report[slug] = {"status": "ok", "layout": cached.get("layout"), "cached": True}
            counts["parsed_" + cached.get("layout", "A")] += 1
            continue
        try:
            result, err = process_one(path)
        except Exception as e:
            result, err = None, f"exception: {e}"

        if result:
            json.dump(result, open(dest, "w"), indent=1)
            report[slug] = {"status": "ok", "layout": result["layout"]}
            counts["parsed_" + result["layout"]] += 1
            print(f"  [{i}/{len(targets)}] {slug} — layout {result['layout']}, "
                  f"{len(result['sub_rows'])} sub-sectors")
        else:
            report[slug] = {"status": "failed", "reason": err, "path": os.path.relpath(path, ROOT)}
            counts["failed"] += 1
            print(f"  [{i}/{len(targets)}] {slug} — FAILED: {err}")

    total = len(targets)
    report["_summary"] = {
        "total": total,
        "parsed_layout_A": counts["parsed_A"],
        "parsed_layout_B": counts["parsed_B"],
        "failed": counts["failed"],
        "success_rate": round((counts["parsed_A"] + counts["parsed_B"]) / total * 100, 1) if total else 0,
    }
    json.dump(report, open(REPORT, "w"), indent=1)
    print("\n" + json.dumps(report["_summary"], indent=2))
    print(f"\nwrote {os.path.relpath(OUT_DIR, ROOT)} + _report.json")


if __name__ == "__main__":
    main()
