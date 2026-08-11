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


# Filenames that don't norm-match their own portal name. Found by tracing why
# Kurnool's tree had unresolved mandals: "Yemmignaur_Mandal_Vision_Action_Plan.pdf"
# is a genuine typo in the source PDF's filename (transposed letters), not
# something any normalisation can bridge. Add entries here only when confirmed
# against the actual file on disk — this is not a place to guess.
STEM_ALIASES = {
    "yemmignaur": "yemmiganur",
}


def index_pdfs():
    """{normalised mandal name: [(repo-relative path, constituency-folder norm)]}

    The constituency-folder norm travels with each path so a lookup can prefer a
    file that actually sits in the mandal's own constituency folder. Without it,
    Kurnool's own "Kurnool" mandal (portal: "Kurnool-U") picked up
    Kodumur_SC/Kurnool_Mandal_Vision_Action_Plan-2026.pdf — a different
    constituency's file that happened to share a normalised stem — while its own
    folder's file, Kurnool_URBAN_Mandal_Vision_Action_Plan.pdf, went unmatched
    because "_URBAN" survives into the stem and norm() doesn't strip it.
    """
    out = {}
    for path in glob.glob(os.path.join(MANDAL_PDF_DIR, "**", "*.pdf"), recursive=True):
        base = os.path.basename(path)
        stem = base.split("_Mandal_")[0] if "_Mandal_" in base else os.path.splitext(base)[0]
        # the portal's own -R/-U marker has a filename-side counterpart:
        # trailing _URBAN / _RURAL (with or without the underscore)
        stem = re.sub(r"[_\s]*(URBAN|RURAL)$", "", stem, flags=re.IGNORECASE)
        key = norm(stem)
        key = STEM_ALIASES.get(key, key)
        rel = os.path.relpath(path, ROOT)
        # the folder immediately under .../mandal/<District>/<ConstituencyFolder>/file.pdf
        parts = rel.split(os.sep)
        const_folder = norm(parts[-2]) if len(parts) >= 2 else ""
        out.setdefault(key, []).append((rel, const_folder))
    return out


def pdfs_for(pdf_index, name, constituency):
    """Same-constituency matches first; only fall back to a cross-constituency
    match (the old, unscoped behaviour) if the mandal's own folder has nothing —
    that fallback is what let Kodumur_SC's file stand in for Kurnool's own
    before this was scoped, so it stays available rather than turning a working
    match into a gap, but it no longer wins when a same-folder file exists."""
    candidates = pdf_index.get(norm(name), [])
    if not candidates:
        return []
    ck = norm(constituency)
    same = [p for p, cf in candidates if cf == ck]
    return same if same else [p for p, _ in candidates]


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
        used_slugs_here = set()
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

            found = pdfs_for(pdfs, name, constituency)
            slug = slugify(name, constituency)
            if slug in used_slugs_here:
                # Two portal entries for this constituency reduce to the same slug —
                # seen with "Yemmiganur-R" and "Yemmiganur-U" in the same
                # constituency: same base name, different marker. A plain dict
                # write let the second silently overwrite the first, so
                # by_constituency listed the mandal twice while mandals{} only
                # ever kept whichever was written last. Disambiguate by kind so
                # both survive as distinct, addressable entries.
                slug = slug + "_" + (kind[:1] if kind != "unknown" else "x")
            used_slugs_here.add(slug)
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
