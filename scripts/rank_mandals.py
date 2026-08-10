#!/usr/bin/env python3
"""Rank each mandal within its own constituency by GMDP, into a compact side file.

The mandal dashboards need "rank N of M in <constituency>" in their header, and a
rank is inherently a cross-mandal comparison — a single mandal's data file cannot
carry it. Rather than fetch every sibling's file at render time (several network
round trips per mandal view), this precomputes the ranking once here.

Output: landing/assets/mandal_ranks.json
    { "<slug>": { "gmdp": float, "pci": float,
                  "rank": int, "total": int } }   # rank 1 = largest GMDP in its constituency

Kept SEPARATE from mandal_index.json (built by build_mandal_index.py) so the two
generators don't fight: this reads mandal_data/ + mandal_index.json and writes its
own file. Re-run whenever mandal_data/ changes:

    python3 scripts/rank_mandals.py
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "landing", "assets", "mandal_data")
INDEX = os.path.join(ROOT, "landing", "assets", "mandal_index.json")
OUT = os.path.join(ROOT, "landing", "assets", "mandal_ranks.json")


def gmdp_of(data):
    """GMDP if published, else GMVA — either is a fair magnitude for ranking."""
    h = data.get("headline") or {}
    for k in ("GMDP", "GMVA"):
        v = h.get(k)
        if isinstance(v, (int, float)) and v > 0:
            return float(v)
    return None


def pci_of(data):
    v = (data.get("headline") or {}).get("PCI")
    return float(v) if isinstance(v, (int, float)) and v > 0 else None


def main():
    idx = json.load(open(INDEX))
    mandals = idx.get("mandals", {})

    # slug -> {gmdp, pci, constituency}
    figures = {}
    missing = 0
    for slug, rec in mandals.items():
        path = os.path.join(DATA_DIR, slug + ".json")
        if not os.path.exists(path):
            missing += 1
            continue
        try:
            data = json.load(open(path))
        except Exception:
            missing += 1
            continue
        g = gmdp_of(data)
        if g is None:
            missing += 1
            continue
        figures[slug] = {"gmdp": g, "pci": pci_of(data),
                         "constituency": rec.get("constituency") or ""}

    # group by constituency, rank by GMDP descending
    by_con = {}
    for slug, f in figures.items():
        by_con.setdefault(f["constituency"], []).append(slug)

    out = {}
    for con, slugs in by_con.items():
        slugs.sort(key=lambda s: figures[s]["gmdp"], reverse=True)
        total = len(slugs)
        for i, slug in enumerate(slugs, start=1):
            out[slug] = {
                "gmdp": round(figures[slug]["gmdp"], 2),
                "pci": figures[slug]["pci"],
                "rank": i,
                "total": total,
            }

    json.dump(out, open(OUT, "w"), separators=(",", ":"))
    print(f"ranked {len(out)} mandals across {len(by_con)} constituencies "
          f"({missing} had no GMDP/GMVA and were skipped)")
    print(f"wrote {os.path.relpath(OUT, ROOT)}")


if __name__ == "__main__":
    main()
