#!/usr/bin/env python3
"""Build the AP assembly-constituency boundary GeoJSON for the districts dashboard.

Source: Data{Meet} Community Maps, assembly-constituencies/India_AC.shp
  https://projects.datameet.org/maps/assembly-constituencies/
  https://github.com/datameet/maps  —  CC-BY 2.5 India, attribution required.

Two things the source needs correcting for:

1. It predates the 2014 bifurcation, so ST_NAME='ANDHRA PRADESH' still includes
   every Telangana constituency. Filtered out by district below.
2. Its DIST_NAME is the pre-2022 13-district layout. We ignore it entirely and
   take the district assignment from district_tree.json instead, which is on the
   current official 28-district list.

Geometry is already WGS84 (see India_AC.prj), matching ap_districts.geojson, so
no reprojection is needed.

Output: landing/assets/ap_constituencies.geojson
  Each feature carries {ac_name, district_key, display} so the dashboard can
  match a polygon to its node in district_tree.json.

Requires the four shapefile parts (.shp/.shx/.dbf/.prj) in SHP_DIR.
    python3 scripts/build_constituency_geojson.py
"""
import json
import os
import re

import shapefile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHP_DIR = os.environ.get("AC_SHP_DIR", "")
TREE_JSON = os.path.join(ROOT, "landing", "assets", "district_tree.json")
OUT = os.path.join(ROOT, "landing", "assets", "ap_constituencies.geojson")

# Telangana districts still filed under ANDHRA PRADESH in the pre-2014 source
TELANGANA_DISTRICTS = {
    "ADILABAD", "HYDERABAD", "KARIMNAGAR", "KHAMMAM", "MAHBUBNAGAR",
    "MEDAK", "NALGONDA", "NIZAMABAD", "RANGAREDDI", "WARANGAL",
}

# shapefile spelling -> district_tree.json spelling, for the handful that don't
# normalize to the same string
NAME_ALIASES = {
    "anakapalle": "anakapalli",
    "cheepurupalle": "cheepurupalli",
    "kodursc": "railwaykodursc",
    "pulivendla": "pulivendula",
    "salurst": "salurust",
    "tadpatri": "tadipatri",
}


def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def main():
    if not SHP_DIR:
        raise SystemExit(
            "set AC_SHP_DIR to the folder holding India_AC.shp/.shx/.dbf/.prj\n"
            "download from https://github.com/datameet/maps/tree/master/assembly-constituencies"
        )

    with open(TREE_JSON) as f:
        tree = json.load(f)

    # normalized constituency name -> (original name, district key)
    lookup = {}
    for dkey, dval in tree.items():
        for cname in dval.get("constituencies", {}):
            lookup[norm(cname)] = (cname, dkey)

    reader = shapefile.Reader(os.path.join(SHP_DIR, "India_AC"))
    features = []
    unmatched = []

    for sr in reader.shapeRecords():
        rec = sr.record
        if rec["ST_NAME"] != "ANDHRA PRADESH":
            continue
        if rec["DIST_NAME"] in TELANGANA_DISTRICTS:
            continue
        ac_name = (rec["AC_NAME"] or "").strip()
        if not ac_name:
            continue

        key = norm(ac_name)
        key = NAME_ALIASES.get(key, key)
        hit = lookup.get(key)
        if not hit:
            unmatched.append(ac_name)
            continue
        tree_name, district_key = hit

        features.append({
            "type": "Feature",
            "properties": {
                "ac_name": tree_name,
                "district_key": district_key,
                "display": ac_name,
            },
            "geometry": sr.shape.__geo_interface__,
        })

    if unmatched:
        print("WARNING: no district_tree match for:", sorted(unmatched))

    matched_names = {f["properties"]["ac_name"] for f in features}
    missing = sorted(set(n for n, _ in lookup.values()) - matched_names)
    if missing:
        print(f"WARNING: {len(missing)} tree constituencies have no polygon:", missing)

    with open(OUT, "w") as f:
        json.dump({"type": "FeatureCollection", "features": features}, f)
    size_mb = os.path.getsize(OUT) / 1e6
    print(f"wrote {os.path.relpath(OUT, ROOT)} — {len(features)} constituencies, {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
