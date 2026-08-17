#!/usr/bin/env python3
"""Guard the two sector classifications the site deliberately runs side by side.

They look contradictory and they are NOT. Do not "reconcile" them.

  METHODOLOGY PAGE  (#page-methodology in landing/index.html)
      The official NSO method for District Domestic Product: eleven broad
      industry groups, arranged Primary 1 / Secondary 4 / Tertiary 6. This is a
      description of how the published estimates are actually produced, so it
      has to match the source method exactly. It is not ours to simplify.

  IMPROVING GVA TAB  (landing/assets/gva_playbook.json)
      An advisory surface: what a district officer can actually pull on. It uses
      the Andhra Pradesh STATE grouping, cut down on purpose to
      Agriculture 3 / Industry 2 / Services 1, because a menu of thirteen
      playbooks was not a menu anyone used. Mining sits under Industry here
      (state convention) where the GoI convention would put it in Primary.

The risk this file exists to stop: someone notices the mismatch, assumes it is a
bug, and edits one to match the other. Editing the methodology page would
misstate the official method. Editing the playbook would undo a deliberate
product decision. If the counts below ever need to change, change them here
consciously, with a reason.

Usage:
    python3 scripts/check_classifications.py     # exit 0 green, 1 on drift
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAYBOOK = os.path.join(ROOT, "landing", "assets", "gva_playbook.json")
INDEX = os.path.join(ROOT, "landing", "index.html")

# The advisory cut. Keys, not just counts, so a rename is caught too.
EXPECTED_PLAYBOOK = {
    "agriculture": ["crops", "livestock_fisheries", "forestry"],
    "industry":    ["mining", "manufacturing"],
    "services":    ["services"],
}

# Markers that the methodology page still teaches the official eleven-industry
# split. Loose enough to survive copy edits, tight enough to catch a rewrite
# that quietly drops the framing.
EXPECTED_METHOD_MARKERS = ["eleven", "PRIMARY", "SECONDARY", "TERTIARY"]


def fail(msg, problems):
    print(msg)
    for p in problems:
        print("  -", p)
    print("\nThese two classifications are meant to differ. See the docstring in")
    print(os.path.relpath(__file__, ROOT) + " before changing either.")
    return 1


def main():
    problems = []

    with open(PLAYBOOK, encoding="utf-8") as fh:
        pb = json.load(fh)
    got = {g["key"]: [s["key"] for s in g["sectors"]] for g in pb["groups"]}

    if set(got) != set(EXPECTED_PLAYBOOK):
        problems.append("playbook groups are %s, expected %s"
                        % (sorted(got), sorted(EXPECTED_PLAYBOOK)))
    for gkey, want in EXPECTED_PLAYBOOK.items():
        have = got.get(gkey)
        if have is None:
            continue
        if have != want:
            problems.append("playbook %s is %s, expected %s" % (gkey, have, want))

    with open(INDEX, encoding="utf-8") as fh:
        html = fh.read()
    i = html.find('id="page-methodology"')
    if i < 0:
        problems.append("methodology page not found in landing/index.html")
    else:
        j = html.find('id="page-', i + 10)
        seg = html[i:j if j > 0 else len(html)]
        for marker in EXPECTED_METHOD_MARKERS:
            if marker not in seg:
                problems.append("methodology page no longer mentions %r; the "
                                "official eleven-industry framing may have been "
                                "edited away" % marker)

    if problems:
        return fail("classification guard FAILED", problems)

    print("classification guard ok")
    for gkey in ("agriculture", "industry", "services"):
        print("  playbook %-12s %d  %s" % (gkey, len(got[gkey]), ", ".join(got[gkey])))
    print("  methodology page still teaches the eleven-industry "
          "Primary/Secondary/Tertiary split")
    print("\nThe two differ on purpose: the methodology page describes the official")
    print("NSO method, the playbook is an advisory cut on the AP state grouping.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
