#!/usr/bin/env python3
"""Build the baseline / endline / feedback instrument data.

Source: corpus_files/training/{Pre,Post}_Training_Assessment_{District,Constituency,
Master_Trainer}.txt — the six question papers actually administered.

The programme runs a BASELINE before training and an ENDLINE after, at three
levels. Three instrument shapes appear:

  · multiple choice        "Q1. …" followed by "○ a) …" options
  · Likert grid            a markdown table whose header row carries
                           Strongly Disagree (1) … Strongly Agree (5)
  · open response          a prompt with no options

Section C / Section B of every endline paper is TRAINING FEEDBACK — the same
Likert grid, but rating the session rather than the officer. It is split out here
because the page treats feedback and knowledge as two separate things.

No response data exists yet: these are the instruments, not the results. Nothing
in this file invents a score.

Usage:  python3 scripts/build_assessment.py
"""

import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "corpus_files", "training")
OUT = os.path.join(ROOT, "landing", "assets", "capacity_assessment.json")

PAPERS = [
    ("baseline", "district",     "Pre_Training_Assessment_District.txt",       "District-level senior officers"),
    ("endline",  "district",     "Post_Training_Assessment_District.txt",      "District-level senior officers"),
    ("baseline", "constituency", "Pre_Training_Assessment_Constituency.txt",   "Constituency and mandal officers"),
    ("endline",  "constituency", "Post_Training_Assessment_Constituency.txt",  "Constituency and mandal officers"),
    ("baseline", "master",       "Pre_Training_Assessment_Master_Trainer.txt", "Master trainers"),
    ("endline",  "master",       "Post_Training_Assessment_Master_Trainer.txt", "Master trainers"),
]

RE_SECTION = re.compile(r"^Section\s+([A-Z])\s*:?\s*(.*)$")
RE_Q = re.compile(r"^Q(\d+)\.\s*(.+)$")
RE_OPT = re.compile(r"^○\s*([a-e])\)\s*(.+)$")
RE_ROW = re.compile(r"^\|\s*(.+?)\s*\|(?:\s*○\s*\|){3,}\s*$")
# The master-trainer papers print the scale unspaced ("StronglyDisagree(1)"), so
# the gap between the two words has to be optional or those grids go unrecognised.
RE_SCALEHEAD = re.compile(r"Strongly\s*Disagree", re.I)
RE_TABLE_ANY = re.compile(r"^\s*\|")
RE_FEEDBACK = re.compile(r"training\s+feedback", re.I)

# Rating grids in these papers are all 1-5 agreement scales; the label set is
# printed in the header row, so it is read from the paper rather than assumed.
def scale_from(row):
    cells = [c.strip() for c in row.strip().strip("|").split("|")]
    labels = [c for c in cells[1:] if c and c != "○"]
    return labels or ["Strongly Disagree (1)", "Disagree (2)", "Neutral (3)",
                      "Agree (4)", "Strongly Agree (5)"]


def tidy(s):
    s = s.replace("\\~", "~").replace("\\_", "_").replace("\\*", "*")
    s = re.sub(r"\s{2,}", " ", s).strip()
    return s


def parse(path):
    text = open(path, encoding="utf-8").read()
    lines = text.split("\n")

    title = ""
    for l in lines[:12]:
        s = l.strip()
        if s and s.upper() == s and len(s) > 8 and "GOVERNMENT" not in s.upper():
            title = s.title()
            break
    if not title:
        title = os.path.basename(path).replace("_", " ")

    sections, cur, scale = [], None, None
    pending_q = None
    # Not every paper uses "Section X:" headings — the constituency and master
    # baselines drop straight into a rating grid, sometimes under a bare title
    # line. Remembering the last plausible title lets an implicit section open
    # with the paper's own wording instead of a generic placeholder.
    last_title = ""

    def ensure_section():
        nonlocal cur
        if cur is None:
            cur = {"letter": chr(ord("A") + len(sections)),
                   "title": last_title or "Self-rating", "kind": "mixed",
                   "scale": None, "items": []}
            sections.append(cur)
        return cur

    for raw in lines:
        l = raw.rstrip()
        s = l.strip()
        if not s:
            continue

        m = RE_SECTION.match(s)
        if m:
            if pending_q and cur:
                cur["items"].append(pending_q)
                pending_q = None
            cur = {"letter": m.group(1), "title": tidy(m.group(2)) or "Section " + m.group(1),
                   "kind": "mixed", "scale": None, "items": []}
            sections.append(cur)
            scale = None
            continue

        if RE_SCALEHEAD.search(s) and RE_TABLE_ANY.match(s):
            ensure_section()
            scale = scale_from(s)
            cur["scale"] = scale
            cur["kind"] = "rating"
            continue

        if not RE_TABLE_ANY.match(s) and not RE_Q.match(s) and not RE_OPT.match(s):
            # A candidate heading: short, prose-free, not the closing matter.
            # "Officer Profile" / "Profile" caption the name-and-designation form
            # at the top of every paper, not the rating grid that follows, so they
            # must not become a section title.
            if (8 < len(s) < 90 and not s.startswith("○")
                    and not re.match(r"^(Government of|Instructions|Thank you|—)", s, re.I)
                    and not re.match(r"^(Officer\s+)?Profile$", s, re.I)
                    and not re.match(r"^(Pre|Post)\s+Training\s+ASSESSMENT$", s, re.I)
                    and not re.match(r"^(Baseline|Endline)\b.*ASSESSMENT$", s, re.I)
                    and not s.endswith(".")):
                last_title = tidy(s)

        if cur is None and not (RE_ROW.match(s) or RE_Q.match(s)):
            continue
        ensure_section()
        if RE_TABLE_ANY.match(s):
            m = RE_ROW.match(s)
            if m:
                stmt = tidy(re.sub(r"^\d+\.\s*", "", m.group(1)))
                if stmt and stmt.lower() != "statement" and len(stmt) > 12:
                    cur["items"].append({"type": "rating", "text": stmt})
            continue

        m = RE_Q.match(s)
        if m:
            if pending_q:
                cur["items"].append(pending_q)
            pending_q = {"type": "mcq", "n": int(m.group(1)),
                         "text": tidy(m.group(2)), "options": []}
            if cur["kind"] == "mixed":
                cur["kind"] = "mcq"
            continue

        m = RE_OPT.match(s)
        if m and pending_q:
            pending_q["options"].append(tidy(m.group(2)))
            continue

        # A wrapped continuation of the question stem.
        if pending_q and not pending_q["options"] and len(s) > 3 and not s.startswith("○"):
            pending_q["text"] = tidy(pending_q["text"] + " " + s)

    if pending_q and cur:
        cur["items"].append(pending_q)

    # An "open" section is one with prompts but no options and no grid.
    for sec in sections:
        if sec["kind"] == "mixed" and sec["items"]:
            sec["kind"] = "open"
        sec["count"] = len(sec["items"])
    return title, [s for s in sections if s["items"]]


def main():
    papers, feedback = [], None
    for stage, level, fname, audience in PAPERS:
        path = os.path.join(SRC, fname)
        if not os.path.exists(path):
            print("  ! missing", fname)
            continue
        title, sections = parse(path)

        # Section C/B "Training Feedback" rates the session, not the officer, so
        # it is lifted out of the knowledge paper and reported separately.
        knowledge, fb = [], []
        for sec in sections:
            (fb if RE_FEEDBACK.search(sec["title"]) else knowledge).append(sec)
        if fb and feedback is None:
            feedback = {"source": fname, "level": level,
                        "scale": fb[0].get("scale"),
                        "statements": [i["text"] for i in fb[0]["items"]]}
        papers.append({
            "stage": stage, "level": level, "audience": audience,
            "title": title, "source": fname,
            "sections": knowledge,
            "questions": sum(s["count"] for s in knowledge),
            "has_feedback": bool(fb),
            "feedback_statements": [i["text"] for s in fb for i in s["items"]],
        })
        print("· %-12s %-13s %2d sections, %2d items%s"
              % (stage, level, len(knowledge), sum(s["count"] for s in knowledge),
                 "  (+feedback)" if fb else ""))

    payload = {
        "papers": papers,
        "feedback": feedback,
        "totals": {
            "papers": len(papers),
            "levels": sorted({p["level"] for p in papers}),
            "questions": sum(p["questions"] for p in papers),
        },
        # Explicit: the instruments are built, the responses are not digitised.
        # The page reads this rather than hard-coding a claim about results.
        "responses_available": False,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print("\n→ %s  (%d papers, %d items, responses_available=false)"
          % (os.path.relpath(OUT, ROOT), len(papers), payload["totals"]["questions"]))


if __name__ == "__main__":
    main()
