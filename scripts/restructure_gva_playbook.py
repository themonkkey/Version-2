#!/usr/bin/env python3
"""Reshape the sector classification in landing/assets/gva_playbook.json.

Target structure:
    Agriculture  Crops / Horticulture, Livestock & Fisheries, Forestry & Logging
    Industry     Mining & Quarrying, Manufacturing
    Services     one generic entry, no sub-headings

WHY this is a transform and not an edit to build_gva_playbook.py:
that script builds the playbook from ~/Downloads/AP_GDDP_Training_Dashboard (1).html,
and the source HTML is no longer on disk, so it cannot be re-run end to end. The
committed gva_playbook.json is therefore the authoritative artifact and this
script reshapes it in place.

The transform is IDEMPOTENT. Running it on an already-restructured file changes
nothing and reports "already restructured". That matters because it is the only
way the reshaping survives: there is no upstream to regenerate from.

Usage:
    python3 scripts/restructure_gva_playbook.py            # apply, write
    python3 scripts/restructure_gva_playbook.py --check    # report only, exit 1 if it would change
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "landing", "assets", "gva_playbook.json")

# Sub-sectors to remove from Industry. Their content stays recoverable in git
# history; nothing merges it, because folding Electricity and Construction into
# Manufacturing would misdescribe both.
DROP = {"electricity_utilities", "construction"}

# The six Services playbooks collapse into one. Keyed in display order so the
# merged prose reads in the order a reader met these sectors before.
SERVICES_MERGE = [
    ("trade_hotels",   "Trade, hotels and restaurants"),
    ("transport_comm", "Transport, storage and communication"),
    ("financial",      "Financial services"),
    ("real_estate",    "Real estate, dwellings and professional services"),
    ("public_admin",   "Public administration and defence"),
    ("other_services", "Other services, education and health"),
]
SERVICES_KEY = "services"
SERVICES_TITLE = "Services sector"


def dedup(seq):
    """Order-preserving dedup. Lists of indicators arrive as lists, which are
    unhashable, so compare on the JSON form rather than on the value itself."""
    seen, out = set(), []
    for x in seq:
        k = json.dumps(x, sort_keys=True) if isinstance(x, (list, dict)) else x
        if k not in seen:
            seen.add(k)
            out.append(x)
    return out


def restructure(pb):
    """Return (changed, notes). Mutates pb in place."""
    notes = []
    groups = {g["key"]: g for g in pb["groups"]}

    # 1. Agriculture: Crops (Agriculture) -> Crops / Horticulture.
    #    Horticulture is a separate line in the district GDDP tables and rolls
    #    into this playbook, so it belongs in `covers` as well as the title.
    agri = groups.get("agriculture")
    if agri:
        for s in agri["sectors"]:
            if s["key"] == "crops":
                if s["title"] != "Crops / Horticulture":
                    s["title"] = "Crops / Horticulture"
                    notes.append("renamed crops -> Crops / Horticulture")
                if "Horticulture" not in s.get("covers", []):
                    s.setdefault("covers", []).append("Horticulture")
                    notes.append("added Horticulture to crops covers")

    # 2. Industry: keep Mining & Quarrying and Manufacturing only.
    ind = groups.get("industry")
    if ind:
        before = [s["key"] for s in ind["sectors"]]
        ind["sectors"] = [s for s in ind["sectors"] if s["key"] not in DROP]
        gone = [k for k in before if k in DROP]
        if gone:
            notes.append("dropped from industry: " + ", ".join(gone))

    # 3. Services: merge six playbooks into one generic entry.
    svc = groups.get("services")
    if svc and not (len(svc["sectors"]) == 1 and svc["sectors"][0]["key"] == SERVICES_KEY):
        by_key = {s["key"]: s for s in svc["sectors"]}
        parts = [(by_key[k], label) for k, label in SERVICES_MERGE if k in by_key]
        # Anything unexpected still gets merged rather than silently dropped.
        for s in svc["sectors"]:
            if s["key"] not in dict(SERVICES_MERGE):
                parts.append((s, s["title"]))

        covers, pathways, actions, policies, indicators, est = [], [], [], [], [], []
        for s, label in parts:
            covers += s.get("covers", [])
            pathways += s.get("pathways", [])
            actions += s.get("actions", [])
            policies += s.get("policies", [])
            indicators += s.get("indicators", [])
            # Each sub-sector is estimated a different way, so the merged
            # estimation note keeps them attributed rather than run together
            # into one sentence that would be true of none of them.
            e = (s.get("estimation") or "").strip()
            if e:
                est.append(label + ": " + e)

        svc["sectors"] = [{
            "key": SERVICES_KEY,
            "title": SERVICES_TITLE,
            "covers": dedup(covers),
            "estimation": " ".join(est),
            "pathways": dedup(pathways),
            "actions": dedup(actions),
            "policies": dedup(policies),
            "indicators": dedup(indicators),
        }]
        notes.append("merged %d services playbooks into one" % len(parts))

    return bool(notes), notes


def main():
    check = "--check" in sys.argv
    with open(PATH, encoding="utf-8") as fh:
        pb = json.load(fh)

    changed, notes = restructure(pb)

    if not changed:
        print("already restructured, nothing to do")
    else:
        for n in notes:
            print(" -", n)

    # Report the resulting shape either way, so a --check run is still useful.
    print()
    for g in pb["groups"]:
        print("%-12s %d  %s" % (g["key"], len(g["sectors"]),
                                ", ".join(s["title"] for s in g["sectors"])))

    if check:
        sys.exit(1 if changed else 0)

    if changed:
        with open(PATH, "w", encoding="utf-8") as fh:
            json.dump(pb, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        print("\nwrote", os.path.relpath(PATH, ROOT))


if __name__ == "__main__":
    main()
