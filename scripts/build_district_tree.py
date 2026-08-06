#!/usr/bin/env python3
"""Build the District -> Constituency -> Mandal tree for the dashboard.

Source of truth for names/nesting: folder structure under
corpus_files/vision_documents/{constituency,mandal}/ (one dir per district,
one subdir per constituency, mandal PDFs live one level deeper inside that).

Source of truth for district-level numbers: landing/assets/districts_data.json
(already correct — 28 districts + one state aggregate row).

Two folders in the raw export are mis-nested relative to the official 28-district
list (https://igod.gov.in/sg/AP/E042/organizations): "Marakapuram" and "Polavaram"
are themselves districts (matches districts_data.json), not sub-groupings, so they
pass through unchanged here. This script does NOT re-parent them — flagging in case
future exports use a different top-level name for either.

Output: landing/assets/district_tree.json
  { <district_key>: {
      ...district-level fields copied from districts_data.json...,
      "constituencies": { <name>: { "mandals": [<name>, ...] } }
  } }

Constituency/mandal level carries names only — no numeric data exists there yet
(source PDFs are unstructured vision/action-plan documents). A later extraction
pass can add a "stats" key per constituency/mandal without touching this script's
tree-walking logic.

Re-run after any change to corpus_files/vision_documents/ or districts_data.json:
    python3 scripts/build_district_tree.py
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VISION_DIR = os.path.join(ROOT, "corpus_files", "vision_documents")
DISTRICTS_JSON = os.path.join(ROOT, "landing", "assets", "districts_data.json")
OUT = os.path.join(ROOT, "landing", "assets", "district_tree.json")


def subdirs(path):
    if not os.path.isdir(path):
        return []
    return sorted(d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d)))


def mandal_names_from_files(path):
    """Mandal PDFs sit as files directly in the constituency folder, named
    like '<Mandal>_Mandal_Vision_Action_Plan[-2026].pdf' — no subdirectory
    per mandal. Derive the distinct mandal name set from filenames.
    """
    if not os.path.isdir(path):
        return []
    names = set()
    for fname in os.listdir(path):
        if not fname.lower().endswith(".pdf"):
            continue
        m = fname.split("_Mandal_")
        if len(m) >= 2:
            names.add(m[0])
    return sorted(names)


def build_constituency_mandal_map():
    """{district_folder_name: {constituency_name: [mandal_name, ...]}}"""
    const_root = os.path.join(VISION_DIR, "constituency")
    mandal_root = os.path.join(VISION_DIR, "mandal")
    out = {}
    for district in subdirs(const_root):
        constituencies = subdirs(os.path.join(const_root, district))
        out[district] = {}
        for const in constituencies:
            mandal_path = os.path.join(mandal_root, district, const)
            out[district][const] = mandal_names_from_files(mandal_path)
    return out


def main():
    with open(DISTRICTS_JSON) as f:
        districts_data = json.load(f)

    folder_map = build_constituency_mandal_map()

    # districts_data.json keys use underscores/mixed case that don't always match
    # the vision_documents folder names 1:1 (e.g. Sps_Nellore vs Spsr_Nellore).
    # Match case-insensitively on alnum-only to bridge the two naming schemes.
    def norm(s):
        return "".join(c.lower() for c in s if c.isalnum())

    folder_by_norm = {norm(k): k for k in folder_map}

    # a few districts_data.json keys use spellings that don't normalize to match
    # their vision_documents folder name (short forms, alt transliterations).
    ALIASES = {
        "Anakapalle": "Anakapalli",
        "Markapuram": "Marakapuram",
        "Sps_Nellore": "Spsr_Nellore",
        "Nandyal": "Nandyala",
        "Ananthapuramu": "Ananthapur",
    }

    tree = {}
    unmatched = []
    for dkey, dval in districts_data.items():
        if dkey == "Andhra_Pradesh_Pci":
            continue  # state aggregate row, not a district
        folder_key = folder_by_norm.get(norm(ALIASES.get(dkey, dkey)))
        entry = dict(dval)
        entry["constituencies"] = {}
        if folder_key:
            for const, mandals in folder_map[folder_key].items():
                entry["constituencies"][const] = {"mandals": mandals}
        else:
            unmatched.append(dkey)
        tree[dkey] = entry

    if unmatched:
        print("WARNING: no constituency/mandal folder matched for:", unmatched)

    with open(OUT, "w") as f:
        json.dump(tree, f, indent=1)
    print(f"wrote {os.path.relpath(OUT, ROOT)} — {len(tree)} districts")


if __name__ == "__main__":
    main()
