#!/usr/bin/env python3
"""Assign a dashboard archetype to every district and constituency.

The archetype picks which template renders the place. Rules and rationale live in
docs/DASHBOARD_ARCHITECTURE.md §3 — keep the two in sync.

Deterministic and derived purely from the numbers, so a data refresh re-derives
every assignment and nobody hand-curates 175 places.

Reads:  landing/assets/district_tree.json
        landing/assets/apc/<code>.json      (from fetch_apc_data.py)
Writes: landing/assets/dashboard_index.json

    python3 scripts/classify_templates.py
"""
import glob
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APC_DIR = os.path.join(ROOT, "landing", "assets", "apc")
TREE = os.path.join(ROOT, "landing", "assets", "district_tree.json")
OUT = os.path.join(ROOT, "landing", "assets", "dashboard_index.json")

# scheduled / agency districts — these get D4 regardless of sector split, because
# ranking them on GDDP alone reads as a scoreboard rather than a plan
AGENCY_DISTRICTS = {"Alluri_Seetha_Rama_Raju", "Parvathipuram_Manyam", "Polavaram"}

SECTOR_CODES = {"AGRIC": "agri", "INDUSTRY": "industry", "SERVICE": "services"}


def num(v):
    """'274.6' / '223693 (As per Census 2011)' / '3.53 Lakhs' / 274.6 -> float or None

    The unit suffix matters. The portal writes population as a plain integer for 174
    of 175 constituencies and as '3.53 Lakhs' for Mangalagiri. Taking the leading
    number blindly recorded that constituency's population as 3.53 people, which then
    rendered on the dashboard as 'Population 4'. Scale the value when a unit is named
    rather than silently truncating it.
    """
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)

    s = str(v)
    m = re.search(r"[\d,]+(?:\.\d+)?", s)
    if not m:
        return None
    val = float(m.group().replace(",", ""))

    # only look for a unit between the number and any parenthesised provenance
    tail = s[m.end():].split("(")[0].lower()
    for pattern, mult in (
        (r"\bcrores?\b", 10_000_000),
        (r"\blakhs?\b|\blacs?\b", 100_000),
        (r"\bmillions?\b", 1_000_000),
        (r"\bthousands?\b", 1_000),
    ):
        if re.search(pattern, tail):
            return val * mult
    return val


def classify_constituency(rec):
    """C1 urban/services · C2 agrarian · C3 industrial · C4 mixed"""
    shares = {}
    sc = rec.get("share_current") or {}
    for item in (sc.get("items") or []):
        key = SECTOR_CODES.get(item.get("sectorCode"))
        if key:
            shares[key] = item.get("sharePct")

    agri = shares.get("agri") or 0
    industry = shares.get("industry") or 0
    services = shares.get("services") or 0

    if not (agri or industry or services):
        return "C4", shares, "no sector data — defaulting to the balanced view"

    # order matters: urban signal wins, a services-heavy municipal seat behaves
    # like a city whatever else is present
    if services >= 55:
        return "C1", shares, f"services {services}% — urban/services-led"
    if agri >= 40:
        return "C2", shares, f"agriculture {agri}% — agrarian"
    if industry >= 35:
        return "C3", shares, f"industry {industry}% — industrial"
    return "C4", shares, "no dominant sector — mixed/transitional"


def load_district_sector_mix():
    """{district_key: {agri,industry,services} as % of GDVA}

    districts_data.json only carries the top-5 sectors (~30% of the economy), far
    too partial to classify on. The CSV has the three official sector aggregates
    against GDVA for every district, so use that instead.
    """
    import csv

    csv_path = os.path.join(ROOT, "structured_district_data.csv")
    latest = "2025-26 (FAE)"
    want = {
        "AGRICULTURE & ALLIED SECTOR": "agri",
        "Industry Sector (aggregate)": "industry",
        "Services Sector (aggregate)": "services",
        "Gross District Value Added (GDVA)": "gdva",
    }

    raw = {}
    with open(csv_path) as f:
        for row in csv.DictReader(f):
            key = want.get(row["sector"])
            if not key or row["year"] != latest:
                continue
            try:
                val = float(row["value_rs_cr"])
            except (TypeError, ValueError):
                continue
            raw.setdefault(row["district"], {})[key] = val

    def norm(s):
        return re.sub(r"[^a-z0-9]", "", s.lower())

    mix = {}
    for district, vals in raw.items():
        gdva = vals.get("gdva")
        if not gdva:
            continue
        mix[norm(district)] = {
            k: round(vals.get(k, 0) / gdva * 100, 1)
            for k in ("agri", "industry", "services")
        }
    return mix


def classify_district(dkey, dval, pci_rank, total, mix):
    """D1 metro · D2 agrarian · D3 industrial · D4 emerging/agency"""
    if dkey in AGENCY_DISTRICTS:
        return "D4", "scheduled/agency district", {}
    if pci_rank is not None and pci_rank > total - 8:
        return "D4", f"PCI rank {pci_rank}/{total} — emerging", mix.get(dkey, {})

    m = mix.get(dkey)
    if not m:
        return "C4" if False else "D4", "no sector aggregates in the workbook", {}

    agri, industry, services = m["agri"], m["industry"], m["services"]

    if services > max(agri, industry) and pci_rank is not None and pci_rank <= 8:
        return "D1", f"services {services}%, PCI rank {pci_rank} — metro/urban core", m
    if agri >= 35:
        return "D2", f"agriculture {agri}% — agrarian heartland", m
    if industry >= 30:
        return "D3", f"industry {industry}% — industrial corridor", m
    if services > max(agri, industry):
        return "D1", f"services {services}% — services-led", m
    return ("D2", f"agriculture {agri}% — agrarian", m) if agri >= industry \
        else ("D3", f"industry {industry}% — industrial", m)


def main():
    tree = json.load(open(TREE))

    # PCI rank across districts, 1 = highest
    ranked = sorted(((k, v.get("pci") or 0) for k, v in tree.items()),
                    key=lambda kv: -kv[1])
    pci_rank = {k: i + 1 for i, (k, _) in enumerate(ranked)}

    # constituency records keyed by normalized name
    def norm(s):
        return re.sub(r"[^a-z0-9]", "", s.lower())

    apc = {}
    for path in glob.glob(os.path.join(APC_DIR, "[0-9]*.json")):
        rec = json.load(open(path))
        apc[norm(rec["name"])] = rec

    out = {"districts": {}, "constituencies": {}, "_counts": {}}
    tally = {}

    # district keys and CSV district names differ in spelling; match on alnum
    raw_mix = load_district_sector_mix()
    mix = {}
    for dkey in tree:
        mix[dkey] = raw_mix.get(norm(dkey), {})
    unmatched_mix = [k for k, v in mix.items() if not v]
    if unmatched_mix:
        print("WARNING: no sector aggregates for:", unmatched_mix)

    for dkey, dval in tree.items():
        arch, why, dmix = classify_district(dkey, dval, pci_rank.get(dkey), len(tree), mix)
        out["districts"][dkey] = {
            "archetype": arch, "why": why,
            "shares": dmix,
            "pci_rank": pci_rank.get(dkey),
            "constituencies": list(dval.get("constituencies", {})),
        }
        tally[arch] = tally.get(arch, 0) + 1

        for cname in dval.get("constituencies", {}):
            rec = apc.get(norm(cname))
            if not rec:
                out["constituencies"][cname] = {
                    "district": dkey, "archetype": None,
                    "why": "no portal data harvested yet",
                }
                continue
            arch_c, shares, why_c = classify_constituency(rec)
            growth = {g.get("sectorCode"): g for g in (rec.get("growth") or [])}
            total = growth.get("TOTAL") or {}
            prof = rec.get("profile") or {}
            out["constituencies"][cname] = {
                "district": dkey,
                "code": rec.get("code"),
                "archetype": arch_c,
                "why": why_c,
                "shares": shares,
                "gcdp_baseline": total.get("baselineAmountCrore"),
                "gcdp_target": total.get("targetAmountCrore"),
                "cagr": total.get("cagR_Pct"),
                "population": num(prof.get("population")),
                "area_sqkm": num(prof.get("area")),
                "thrust": [s.get("sectorName") for s in (rec.get("thrust") or [])],
                "mandals": [m.strip() for m in (prof.get("mandals") or "").split(",") if m.strip()],
            }
            tally[arch_c] = tally.get(arch_c, 0) + 1

    out["_counts"] = dict(sorted(tally.items()))
    json.dump(out, open(OUT, "w"), indent=1)

    print(f"wrote {os.path.relpath(OUT, ROOT)}")
    print(f"  districts      {len(out['districts'])}")
    print(f"  constituencies {len(out['constituencies'])} "
          f"({sum(1 for v in out['constituencies'].values() if v['archetype'])} classified)")
    for k, v in out["_counts"].items():
        print(f"    {k}: {v}")


if __name__ == "__main__":
    main()
