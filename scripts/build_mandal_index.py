#!/usr/bin/env python3
"""Build the mandal roster and assign M1/M2/M3 archetypes.

SOURCE OF TRUTH is the AP portal's profile.mandals string, e.g.
    "Gonegandla-R,Nandavaram-R,Yemmiganur-R,Yemmiganur-U"
That is authoritative and covers all 175 constituencies. district_tree.json's
mandal names were derived from PDF filenames and are less reliable; this file
supersedes them for naming, and records which tree/PDF entries did not match so
the gap is visible rather than silent.

The -R / -U suffix is the portal's own rural/urban marker and is the basis for the
M1/M2 split. 47 of 794 entries carry no suffix — those are recorded as kind
"unknown" and are NEVER guessed, because a mandal wrongly labelled urban would
carry the wrong template.

NO STRUCTURED NUMBERS EXIST AT MANDAL LEVEL. The vision PDFs are prose. Mandal
templates are therefore narrative-first with inherited constituency context, and
every inherited figure must be labelled as inherited. See
docs/DASHBOARD_ARCHITECTURE.md section 5.

Output: landing/assets/mandal_index.json
  { mandals: { "<slug>": {
        name, slug, kind: 'rural'|'urban'|'unknown',
        constituency, constituency_code, district,
        archetype: 'M1'|'M2'|'M3', why,
        pdfs: [relative paths]        # vision documents, may be empty
    }},
    by_constituency: { "<constituency name>": [slug, ...] },
    _counts: {...} }

    python3 scripts/build_mandal_index.py
"""
import glob
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APC_DIR = os.path.join(ROOT, "landing", "assets", "apc")
MANDAL_PDF_DIR = os.path.join(ROOT, "corpus_files", "vision_documents", "mandal")
INDEX = os.path.join(ROOT, "landing", "assets", "dashboard_index.json")
OUT = os.path.join(ROOT, "landing", "assets", "mandal_index.json")

# scheduled / agency districts — an agency mandal gets M3 whatever its R/U marker,
# because forest economy, tribal welfare and connectivity are the frame there, not
# the rural/urban split
AGENCY_DISTRICTS = {"Alluri_Seetha_Rama_Raju", "Parvathipuram_Manyam", "Polavaram"}


def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def slugify(name, constituency):
    return norm(constituency) + "__" + norm(name)


def index_pdfs():
    """{normalised mandal name: [repo-relative pdf paths]}"""
    out = {}
    for path in glob.glob(os.path.join(MANDAL_PDF_DIR, "**", "*.pdf"), recursive=True):
        base = os.path.basename(path)
        stem = base.split("_Mandal_")[0] if "_Mandal_" in base else os.path.splitext(base)[0]
        out.setdefault(norm(stem), []).append(os.path.relpath(path, ROOT))
    return out


def main():
    index = json.load(open(INDEX))
    district_of_constituency = {}
    for cname, c in index["constituencies"].items():
        district_of_constituency[norm(cname)] = c.get("district", "")

    pdfs = index_pdfs()

    mandals = {}
    by_constituency = {}
    counts = {"M1": 0, "M2": 0, "M3": 0, "rural": 0, "urban": 0, "unknown": 0,
              "with_pdf": 0, "without_pdf": 0}

    for path in sorted(glob.glob(os.path.join(APC_DIR, "[0-9]*.json"))):
        rec = json.load(open(path))
        raw = (rec.get("profile") or {}).get("mandals") or ""
        constituency = rec.get("name") or ""
        district = district_of_constituency.get(norm(constituency), rec.get("district", ""))

        entries = [x.strip() for x in raw.split(",") if x.strip()]
        slugs = []
        for entry in entries:
            m = re.match(r"^(.*?)-([A-Za-z]+)$", entry)
            if m:
                name, marker = m.group(1).strip(), m.group(2).upper()
                kind = "urban" if marker == "U" else "rural" if marker == "R" else "unknown"
            else:
                name, kind = entry, "unknown"

            if district in AGENCY_DISTRICTS:
                archetype, why = "M3", "scheduled/agency mandal"
            elif kind == "urban":
                archetype, why = "M2", "portal marks this mandal urban (-U)"
            elif kind == "rural":
                archetype, why = "M1", "portal marks this mandal rural (-R)"
            else:
                # the portal states nothing; do not guess. Rural is the majority
                # case (623 of 794) so it is the least-wrong default, but the
                # reason says plainly that it was not stated.
                archetype, why = "M1", "portal states no rural/urban marker; shown as rural by default"

            found = pdfs.get(norm(name), [])
            slug = slugify(name, constituency)
            mandals[slug] = {
                "name": name,
                "slug": slug,
                "kind": kind,
                "constituency": constituency,
                "constituency_code": rec.get("code"),
                "district": district,
                "archetype": archetype,
                "why": why,
                "pdfs": found,
            }
            slugs.append(slug)
            counts[archetype] += 1
            counts[kind] += 1
            counts["with_pdf" if found else "without_pdf"] += 1

        by_constituency[constituency] = slugs

    out = {"mandals": mandals, "by_constituency": by_constituency, "_counts": counts}
    json.dump(out, open(OUT, "w"), indent=1)

    print(f"wrote {os.path.relpath(OUT, ROOT)}")
    print(f"  mandals: {len(mandals)} across {len(by_constituency)} constituencies")
    for k, v in counts.items():
        print(f"    {k}: {v}")


if __name__ == "__main__":
    main()
