#!/usr/bin/env python3
"""Build the Capacity Building page data from the district status-report PDFs.

Source: ~/Downloads/District_Wise_Consolidated_Status_Reports/*.pdf — one PDF per
district, each a concatenation of the daily status reports filed during that
district's training run.

Two things come out of every PDF:

  1. Structured text  -> landing/assets/capacity.json
  2. The session photos -> landing/assets/capacity/<district-slug>/<slug>-NN.jpg

The photos are already embedded JPEGs, so `pdfimages -j` lifts them out at their
authored resolution. Rasterising the page and cropping would only resample what is
already there — the embedded image IS the source, and it tops out around 240px
wide, so nothing is gained by going through a page render.

THREE report formats appear across the 18 PDFs, filed by different teams as the
programme's template evolved. They are detected per report, not per file, because
a single district's PDF can carry all three:

  A  "CAPACITY BUILDING PROGRAMME - ANDHRA PRADESH"
     "Swarna Andhra @ 2047 | <report type> | <date> | Day N"
     field table -> TRAINING GLIMPSES -> PROGRAMME COVERAGE -> ...HIGHLIGHTS

  B  "CAPACITY BUILDING PROGRAMME [– ANDHRA PRADESH]"
     "Day N Status Report - <focus> - <date>"
     DISTRICT-WISE ACTIVITY SUMMARY -> "District N <NAME>" -> Field/Details table
     One report covers several districts; only the block naming this PDF's own
     district is kept.

  C  "SWARNA ANDHRA @ 2047 | CONSOLIDATED STATUS REPORT"
     "<NAME> DISTRICT" -> District/Date/Training coverage/participants
     -> Participants -> Training Glimpses -> Brief of the Training

Usage:  python3 scripts/build_capacity.py [--no-images]
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from collections import OrderedDict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF_DIR = os.path.expanduser("~/Downloads/District_Wise_Consolidated_Status_Reports")
OUT_JSON = os.path.join(ROOT, "landing", "assets", "capacity.json")
IMG_ROOT = os.path.join(ROOT, "landing", "assets", "capacity")

# PDF stem -> (display name, districts_data.json key). The key is what joins this
# data to the map and the dashboard; a district with no dashboard entry gets None
# rather than a guessed key, so a bad join can never silently mislabel figures.
DISTRICTS = OrderedDict([
    ("Srikakulam",                 ("Srikakulam",                "Srikakulam")),
    ("Vizianagaram",               ("Vizianagaram",              "Vizianagaram")),
    ("Parvathipuram_Manyam",       ("Parvathipuram Manyam",      "Parvathipuram_Manyam")),
    ("Visakhapatnam",              ("Visakhapatnam",             "Visakhapatnam")),
    ("Kakinada",                   ("Kakinada",                  "Kakinada")),
    ("Dr_B_R_Ambedkar_Konaseema",  ("Dr. B.R. Ambedkar Konaseema", "Dr.B.R.Ambedkar_Konaseema")),
    ("East_Godavari",              ("East Godavari",             "East_Godavari")),
    ("Eluru",                      ("Eluru",                     "Eluru")),
    ("Krishna",                    ("Krishna",                   "Krishna")),
    ("NTR",                        ("NTR",                       "Ntr")),
    ("Guntur",                     ("Guntur",                    "Guntur")),
    ("Prakasam",                   ("Prakasam",                  "Prakasam")),
    ("Nellore",                    ("SPSR Nellore",              "Sps_Nellore")),
    ("Kurnool",                    ("Kurnool",                   "Kurnool")),
    ("Nandyal",                    ("Nandyal",                   "Nandyal")),
    ("YSR_Kadapa",                 ("YSR Kadapa",                "Ysr_Kadapa")),
    ("Chittoor",                   ("Chittoor",                  "Chittoor")),
    ("Tirupati",                   ("Tirupati",                  "Tirupati")),
])

# Alternate spellings that appear inside the format-B "District N <NAME>" rows.
NAME_ALIASES = {
    "Kakinada": ["KAKINADA"],
    "Prakasam": ["PRAKASAM"],
    # "VISHAKAPATNAM" is how the format-B reports spell it; matching the correct
    # spelling alone loses every Visakhapatnam block in those files.
    "Visakhapatnam": ["VISAKHAPATNAM", "VISAKHAPATANAM", "VISHAKAPATNAM",
                      "VISHAKHAPATNAM"],
    "SPSR Nellore": ["NELLORE", "SPSR NELLORE", "SPS NELLORE"],
    "Dr. B.R. Ambedkar Konaseema": ["KONASEEMA", "DR. B.R. AMBEDKAR KONASEEMA",
                                    "DR B R AMBEDKAR KONASEEMA", "AMBEDKAR KONASEEMA"],
    "Parvathipuram Manyam": ["PARVATHIPURAM MANYAM", "PARVATHIPURAM"],
    "YSR Kadapa": ["YSR KADAPA", "KADAPA", "Y.S.R. KADAPA"],
    "East Godavari": ["EAST GODAVARI"],
    "NTR": ["NTR", "N.T.R."],
}

MONTHS = {m: i + 1 for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"])}

# --- section labels -------------------------------------------------------
# "TRAINNING" is a typo that survives in most of the later reports; matching it
# is not optional, it is how the majority of the photo blocks are labelled.
RE_GLIMPSES = re.compile(r"^\s*[A-Za-z ]{0,28}GLIMPSES\s*$", re.I)
# "Brief of the Training", "Brief of Constituency Profiling", "Brief of the
# Session" — the wording drifts report to report, so match the stem.
RE_COVERAGE = re.compile(r"^\s*(PROGRAMME COVERAGE|BRIEF OF [A-Za-z ]{3,40})\s*$", re.I)
RE_HIGHLIGHTS = re.compile(r"^\s*[A-Z][A-Z\-& ]{4,}HIGHLIGHTS\s*$", re.I)
RE_PARTICIPANTS_HEAD = re.compile(r"^\s*PARTICIPANTS\s*$", re.I)
RE_PAGEFOOT = re.compile(r"^\s*Page \d+ of \d+\s*$", re.I)
RE_BULLET = re.compile(r"^\s*[•›▪◦\-•›]\s+(.*)$")
RE_NUMBULLET = re.compile(r"^\s*\d{1,2}[.)]\s+(.+)$")

# --- report-start detection ----------------------------------------------
RE_HDR_A = re.compile(r"CAPACITY BUILDING PROGRAMME\s*[-–—]\s*ANDHRA PRADESH", re.I)
RE_HDR_B = re.compile(r"^\s*CAPACITY BUILDING PROGRAMME\s*$", re.I | re.M)
RE_HDR_C = re.compile(r"SWARNA ANDHRA @\s*2047\s*\|\s*CONSOLIDATED STATUS REPORT", re.I)

RE_SUBHDR_A = re.compile(
    r"Swarna Andhra @\s*2047\s*\|(?P<rest>[^\n]+)", re.I)
RE_SUBHDR_B = re.compile(
    r"Day[:\s]*(?P<day>\d+)\s*Status Report\s*[-–—]\s*(?P<rest>[^\n]+)", re.I)

RE_DATE = re.compile(
    r"(\d{1,2})\s*(?:st|nd|rd|th)?\s+"
    r"(January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+(\d{4})", re.I)
RE_DAY = re.compile(r"Day[:\s]*0?(\d{1,2})\b", re.I)
# Ordered most-explicit first: a bare "Participants 72" is only trusted once the
# stated-count phrasings have all failed, because loose digits near the word turn
# up inside designation lists ("Participants (7 Deputy Director Agriculture…)").
RE_PARTICIPANT_COUNT = re.compile(
    r"No\.?\s*of\s*Participants[^0-9]{0,30}(\d{1,4})"
    r"|Number\s+of\s+participants[^0-9]{0,30}(\d{1,4})"
    r"|\(\s*(\d{1,4})\s*Participants?\s*\)"
    r"|Total\s+(\d{1,4})\s+Officials?"
    r"|Approximately\s+(\d{1,4})\s+(?:officers?|officials?)"
    r"|(\d{1,4})\s+Officials?\s+were\s+present"
    r"|Participants\s*[:\-]\s*(\d{1,4})\b", re.I)

# Field labels used by the left column of the A/B/C field tables.
FIELD_LABELS = [
    "Session Format", "Training Format", "Training Level", "Training coverage",
    "Constituency", "Constituencies", "Participants", "Key Officials", "Sector Focus", "Method",
    "Activity", "District", "Date", "Number of participants", "Focus", "Key Findings",
]
RE_FIELD = re.compile(
    r"^\s*(" + "|".join(re.escape(f) for f in FIELD_LABELS) + r")\s*$", re.I)
RE_FIELD_INLINE = re.compile(
    r"^\s*(" + "|".join(re.escape(f) for f in FIELD_LABELS) + r")\s{2,}(\S.*)$", re.I)

RE_DISTRICT_ROW = re.compile(r"^\s*District\s+(\d+)\s+([A-Z][A-Z .&'\-]{2,})\s*$")

# Report-type -> the level it was delivered at. Everything the programme ran is
# one of these three, and the page groups sessions by them.
LEVEL_RULES = [
    (re.compile(r"master", re.I), "master"),
    (re.compile(r"constituency|mandal", re.I), "constituency"),
    (re.compile(r"district", re.I), "district"),
]


def title_forms(display_name):
    """Every way a report might print this district's name as its title line.

    The banner uses the district's own short name — "NELLORE DISTRICT" for SPSR
    Nellore, "DR. B R AMBEDKAR KONASEEMA DISTRICT" for Konaseema — so matching
    the display name alone leaves the title sitting at the front of the session
    format string.
    """
    forms = {display_name.upper()} | {a.upper() for a in NAME_ALIASES.get(display_name, [])}
    forms |= {re.sub(r"[^A-Z0-9 ]", " ", f) for f in list(forms)}
    forms |= {re.sub(r"\s{2,}", " ", f).strip() for f in list(forms)}
    return forms | {f + " DISTRICT" for f in list(forms)}


def slugify(s):
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return re.sub(r"-{2,}", "-", s)


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, check=False, **kw)


def parse_date(text):
    """First real date in `text`, as (iso, pretty). None when there isn't one."""
    m = RE_DATE.search(text or "")
    if not m:
        return None, None
    d, mon, y = int(m.group(1)), MONTHS[m.group(2).lower()], int(m.group(3))
    if not (1 <= d <= 31) or not (2024 <= y <= 2030):
        return None, None
    return "%04d-%02d-%02d" % (y, mon, d), m.group(0)


def clean(line):
    return re.sub(r"\s{2,}", " ", line.strip())


def strip_chrome(lines):
    """Drop page furniture that would otherwise land inside a body paragraph."""
    out = []
    for l in lines:
        if RE_PAGEFOOT.match(l):
            continue
        if RE_HDR_A.search(l) or RE_HDR_C.search(l):
            continue
        if re.match(r"^\s*CAPACITY BUILDING PROGRAMME\s*$", l, re.I):
            continue
        if RE_SUBHDR_A.search(l) or RE_SUBHDR_B.search(l):
            continue
        out.append(l)
    return out


def join_wrapped(lines):
    """Rejoin PDF line-wrapping into paragraphs.

    A layout-mode extract breaks every visual line, and several of these reports
    set their body in a narrow column, so a single bullet can run to eight lines.
    A bullet therefore OPENS a buffer that keeps collecting its own continuation
    lines; it does not close one. Emitting the bullet's first line on its own is
    what produced sentences that began mid-clause ("level government officials.
    The consultations focused on…") — the opening words stayed with the previous
    paragraph and the remainder became a fragment of its own.

    A heading is only recognised with an empty buffer, i.e. straight after a
    blank line. Inside a wrapped run, a short title-case line is far more likely
    to be the tail of a sentence than a new sub-heading.
    """
    paras, buf, bulleted = [], [], False

    def flush():
        if buf:
            paras.append(("• " if bulleted else "") + " ".join(buf))
        return [], False

    for l in lines:
        s = l.strip()
        if not s:
            buf, bulleted = flush()
            continue
        m = RE_BULLET.match(l) or RE_NUMBULLET.match(l)
        if m:
            buf, bulleted = flush()
            buf, bulleted = [clean(m.group(1))], True
            continue
        if not buf and heading_like(s):
            paras.append(s)
            continue
        buf.append(s)
    flush()
    return stitch(paras)


def stitch(paras):
    """Rejoin a paragraph that a PAGE BREAK cut in half.

    Pages are concatenated with a newline, so a bullet running over the foot of
    one page resumes as a separate paragraph at the top of the next. The tell is
    a paragraph opening in lower case behind one that has no terminal
    punctuation — prose does not start a new point that way.
    """
    out = []
    for p in paras:
        if (out and p[:1].islower()
                and not RE_BULLET.match(p) and not RE_NUMBULLET.match(p)
                and not out[-1].rstrip().endswith((".", "!", "?", ":"))):
            out[-1] = out[-1].rstrip() + " " + p
            continue
        out.append(p)
    return out


def heading_like(s):
    """A short, title-ish line with no terminal punctuation — a sub-heading."""
    if len(s) > 60 or not s:
        return False
    if s.endswith((".", ",", ";", ":")):
        return False
    if RE_BULLET.match(s) or RE_NUMBULLET.match(s):
        return False
    words = s.split()
    if not (1 <= len(words) <= 6):
        return False
    # Sector names and constituency names are the two things that appear as
    # sub-headings inside a HIGHLIGHTS block.
    return bool(re.match(r"^[A-Z][A-Za-z().,'\-/ ]*$", s))


def sentences_ok(text):
    """Reject fragments that are page furniture rather than prose."""
    t = text.strip()
    return len(t) > 40 and " " in t


# -------------------------------------------------------------------------
# report splitting
# -------------------------------------------------------------------------

def split_reports(pages):
    """Group 1-indexed pages into reports, one per status-report header.

    The header is searched across the whole page, not just its top: in layout
    mode pdftotext orders text by column, so on a two-column B-format page the
    banner can land well below the first bullet. Requiring the *sub*-header
    alongside it is what keeps a continuation page from opening a new report —
    the banner alone repeats, the "Day N Status Report" / "Swarna Andhra @ 2047 |"
    line only appears where a report actually begins.
    """
    starts = []
    for i, p in enumerate(pages):
        fmt = None
        # C is one report per page and carries its own district/date table, so
        # its running header is a reliable start marker on its own.
        if RE_HDR_C.search(p):
            fmt = "C"
        elif RE_HDR_A.search(p) and RE_SUBHDR_A.search(p):
            fmt = "A"
        elif RE_HDR_B.search(p) and RE_SUBHDR_B.search(p):
            fmt = "B"
        elif RE_HDR_A.search(p) and RE_SUBHDR_B.search(p):
            fmt = "B"
        if fmt:
            starts.append((i, fmt))
    # Some PDFs open part-way through a report — the Srikakulam file begins on the
    # tail of the previous district's page, so its own "District 4 SRIKAKULAM"
    # block (2-4 July profiling) sat ahead of the first detected banner and was
    # dropped entirely, taking date_from with it. Leading pages that carry a
    # district block are recovered as a format-B report.
    if starts and starts[0][0] > 0:
        lead = "\n".join(pages[:starts[0][0]])
        # re.M matters here: RE_DISTRICT_ROW is anchored, and it is compiled
        # without it for line-by-line use, so searching a multi-page blob with it
        # never matched and the recovery silently did nothing.
        if re.search(RE_DISTRICT_ROW.pattern, lead, re.M) and re.search(
                r"^\s*(Activity|Method|Sector Focus|Key Findings)\s{2,}\S", lead, re.M):
            starts.insert(0, (0, "B"))
    if not starts:
        return []
    reports = []
    for n, (i, fmt) in enumerate(starts):
        end = starts[n + 1][0] if n + 1 < len(starts) else len(pages)
        reports.append({
            "fmt": fmt,
            "page_from": i + 1,        # 1-indexed, matches pdfimages -p
            "page_to": end,
            "text": "\n".join(pages[i:end]),
            "lines": [l for p in pages[i:end] for l in p.split("\n")],
        })
    return reports


# -------------------------------------------------------------------------
# field tables
# -------------------------------------------------------------------------

def parse_fields(lines):
    """Pull the Field/Details table.

    The label sits in a left column and its value wraps across following lines,
    so a label line opens a bucket that stays open until the next label or a
    section heading closes it.
    """
    fields, cur = OrderedDict(), None
    for raw in lines:
        l = raw.rstrip()
        if not l.strip():
            continue
        if (RE_GLIMPSES.match(l) or RE_COVERAGE.match(l) or RE_HIGHLIGHTS.match(l)
                or re.match(r"^\s*DISTRICT-WISE ACTIVITY SUMMARY\s*$", l, re.I)
                or RE_PARTICIPANTS_HEAD.match(l)):
            cur = None
            continue
        if RE_PAGEFOOT.match(l):
            continue
        m = RE_FIELD_INLINE.match(l)
        if m:
            cur = m.group(1).strip().title()
            fields.setdefault(cur, []).append(clean(m.group(2)))
            continue
        m = RE_FIELD.match(l)
        if m:
            cur = m.group(1).strip().title()
            fields.setdefault(cur, [])
            continue
        if re.match(r"^\s*Field\s+Details\s*$", l, re.I):
            cur = None
            continue
        if cur:
            fields[cur].append(clean(l))
    return {k: " ".join(v).strip() for k, v in fields.items() if " ".join(v).strip()}


# The left-hand label of a format-A field row is VERTICALLY CENTRED in its cell,
# so in a layout-mode extract it surfaces part-way down its own value rather than
# above it. Reading the table top-to-bottom therefore mis-files text: the tail of
# the "Session Format" value lands under "Participants" and vice versa. For format
# A the region is split on content markers instead of on label position.
RE_PCOUNT_MARK = re.compile(
    r"(No\.?\s*of\s*Participants|Number of Participants|Total\s+\d+\s+Officials?"
    r"|Approximately\s+\d+\s+officers?|\(\s*\d+\s*Participants?\s*\))", re.I)
RE_LABEL_ONLY = re.compile(
    r"^\s*(" + "|".join(re.escape(f) for f in FIELD_LABELS) + r")\s*$", re.I)


def split_region_a(lines, display_name):
    """(format, participants_blob, constituency) for a format-A header block."""
    body = []
    for l in lines:
        if (RE_GLIMPSES.match(l) or RE_COVERAGE.match(l) or RE_HIGHLIGHTS.match(l)):
            break
        body.append(l)
    body = strip_chrome(body)
    titles = title_forms(display_name)
    kept, consty = [], []
    take_consty = False
    for l in body:
        s = clean(l)
        if not s:
            continue
        if s.upper() in titles:
            continue
        if re.match(r"^(Field\s+Details)$", s, re.I):
            continue
        m = RE_LABEL_ONLY.match(s)
        if m:
            take_consty = m.group(1).lower() == "constituency"
            continue
        m = RE_FIELD_INLINE.match(l)
        if m:
            lab, val = m.group(1).lower(), clean(m.group(2))
            if lab == "constituency":
                consty.append(val)
                take_consty = True
                continue
            take_consty = False
            kept.append(val)
            continue
        if take_consty and len(s) < 90 and not RE_PCOUNT_MARK.search(s):
            consty.append(s)
            continue
        take_consty = False
        kept.append(s)

    blob = kept
    cut = None
    for i, s in enumerate(blob):
        if RE_PCOUNT_MARK.search(s):
            cut = i
            break
    if cut is None:
        # No count is stated. The roles list is the run of designation-dense text
        # at the end; a line with three or more comma-separated title-case chunks.
        for i, s in enumerate(blob):
            if s.count(",") >= 3 and len(s) > 60:
                cut = i
                break
    if cut is None:
        return " ".join(blob), "", " ".join(consty)
    return " ".join(blob[:cut]), " ".join(blob[cut:]), " ".join(consty)


# "<label>- <n>" repeated behind a "No of Participants:" lead-in. Two or more of
# these means the day was counted per constituency or per half, and the session
# total is their sum.
RE_SUB_COUNT = re.compile(
    r"([A-Za-z][A-Za-z .()/&'\-]{2,40}?)\s*[-–—:]\s*(\d{1,4})\b")


def sum_sub_counts(tail):
    """Sum a labelled participant series, or None when there isn't one.

    Only fires on two or more labelled counts, so an ordinary "No of
    Participants: 37" is left to the single-value path.

    The series is bounded by ADJACENCY rather than by a trailing separator. The
    designation list runs on from the last count on the same line, so a lookahead
    for ";" / "," / end-of-string silently dropped whichever count came last
    ("…Nellimarla- 26 and Vizianagaram- 12" summed to 140, not 152). Instead the
    run stops at the first gap wider than a separator, which is exactly where the
    counts stop and the job titles begin.
    """
    tail = tail.split("\n")[0]
    tail = re.split(r"(?i)\bParticipants?\s*[:\-]", tail, maxsplit=1)[-1]

    vals, end = [], None
    for m in RE_SUB_COUNT.finditer(tail):
        if end is not None:
            gap = tail[end:m.start()]
            # " , " / " ; " / " and ", optionally with a mid-series sub-heading:
            # "Tertiary Sector Profiling- 7 ; Constituencies Covered: Rajam- 30"
            # keeps counting after "Constituencies Covered:". Anything else has
            # left the series and the designation list has begun.
            if not re.fullmatch(r"[\s,;]*(and\b)?[\s,;]*([A-Za-z][A-Za-z ]{2,28}:)?[\s,;]*",
                                gap):
                break
        n = int(m.group(2))
        if not (1 <= n <= 2000):
            break
        vals.append(n)
        end = m.end()
    if len(vals) < 2:
        return None
    total = sum(vals)
    return total if 1 <= total <= 5000 else None


def parse_participants(fields, text):
    """(count, roles). Count is only reported when the source states one."""
    roles = fields.get("Participants") or fields.get("Key Officials") or ""
    count = None
    for chunk in (fields.get("Participants", ""), fields.get("Number Of Participants", ""),
                  fields.get("Key Officials", ""), text):
        m = RE_PARTICIPANT_COUNT.search(chunk or "")
        if m:
            # A single day is often filed as several labelled sub-counts —
            # "No of Participants: Bobbili- 37, Chipurupalli- 38, Srungavarupukota-
            # 39, Nellimarla- 26 and Vizianagaram- 12", or "Morning Session - 10;
            # Afternoon Session -16". Taking the first number alone reported 37
            # attendees for a day that had 152, so the labelled series is summed
            # when there is one. A lone number keeps the old behaviour.
            total = sum_sub_counts(chunk[m.start():])
            if total is not None:
                count = total
                break
            val = next((g for g in m.groups() if g), None)
            if val and 1 <= int(val) <= 2000:
                count = int(val)
                break
    # Strip the count phrase out of the roles blob so it does not read twice.
    roles = re.sub(r"(No\.?\s*of\s*Participants|Number of participants)\s*[:\-]?\s*\d+\s*[:,.]?",
                   "", roles, flags=re.I)
    roles = re.sub(r"^\s*(Approximately\s+)?\d+\s+(officers?|officials?)\b.*?(?:including|drawn from)\s*[;:,]?\s*",
                   "", roles, flags=re.I)
    # Column wrapping leaves doubled and dangling separators behind.
    roles = re.sub(r"\s*,\s*(,\s*)+", ", ", roles)
    roles = re.sub(r"^\s*[,;:]\s*", "", roles).rstrip(" ,;:")
    return count, clean(roles)


# -------------------------------------------------------------------------
# body sections
# -------------------------------------------------------------------------

def section_slices(lines):
    """Index the body into {label: [lines]} using the all-caps section headings."""
    out, cur = OrderedDict(), None
    for l in lines:
        if RE_GLIMPSES.match(l):
            cur = "glimpses"; out.setdefault(cur, []); continue
        if RE_COVERAGE.match(l):
            cur = "coverage"; out.setdefault(cur, []); continue
        m = RE_HIGHLIGHTS.match(l)
        if m:
            cur = "highlights"; out.setdefault(cur, []); continue
        if RE_PARTICIPANTS_HEAD.match(l):
            cur = "participants"; out.setdefault(cur, []); continue
        if cur:
            out[cur].append(l)
    return out


def parse_coverage(lines):
    paras = [p for p in join_wrapped(strip_chrome(lines))
             if sentences_ok(p) and not RE_BULLET.match(p)]
    return paras


def parse_highlights(lines):
    """[{head, points}] — sub-headings with their bullets under them."""
    groups, cur = [], None
    for p in join_wrapped(strip_chrome(lines)):
        mb = RE_BULLET.match(p) or RE_NUMBULLET.match(p)
        if mb:
            txt = clean(mb.group(1))
            if len(txt) < 15:
                continue
            if cur is None:
                cur = {"head": "", "points": []}
                groups.append(cur)
            cur["points"].append(txt)
            continue
        if heading_like(p):
            cur = {"head": p, "points": []}
            groups.append(cur)
            continue
        # A long unbulleted line inside highlights is still a point.
        if sentences_ok(p):
            if cur is None:
                cur = {"head": "", "points": []}
                groups.append(cur)
            cur["points"].append(clean(p))
    out = []
    for g in groups:
        pts = [x for x in g["points"] if len(x) > 15]
        # Drop the connective stubs the template leaves behind.
        pts = [x for x in pts
               if not re.match(r"^The following interactions were conducted", x, re.I)]
        if pts:
            out.append({"head": g["head"], "points": pts})
    return out


# -------------------------------------------------------------------------
# per-format report parsers
# -------------------------------------------------------------------------

def level_for(kind):
    for rx, lvl in LEVEL_RULES:
        if rx.search(kind or ""):
            return lvl
    return "district"


def parse_report_a(rep, display_name):
    m = RE_SUBHDR_A.search(rep["text"])
    rest = m.group("rest") if m else ""
    rest = rest.split("\n")[0]
    parts = [x.strip() for x in rest.split("|")]
    kind = parts[0] if parts else "Status Report"
    iso, pretty = parse_date(rest)
    if not iso:
        iso, pretty = parse_date("\n".join(rep["text"].split("\n")[:14]))
    md = RE_DAY.search(rest)
    day = int(md.group(1)) if md else None

    secs = section_slices(rep["lines"])
    fmt_txt, pblob, consty = split_region_a(rep["lines"], display_name)
    count, roles = parse_participants({"Participants": pblob}, pblob or rep["text"])

    coverage = parse_coverage(secs.get("coverage", []))
    highlights = parse_highlights(secs.get("highlights", []))

    # A day with no training filed still says so, in one line, before any table.
    note = None
    if not coverage and not highlights:
        for p in join_wrapped(strip_chrome(rep["lines"])):
            if re.search(r"(could not happen|no training|already concluded|overlapping programme)", p, re.I):
                note = clean(p)
                break
    return {
        "kind": re.sub(r"\s+", " ", kind).strip(),
        "level": level_for(kind),
        "day": day, "date": iso, "date_pretty": pretty,
        "format": clean(fmt_txt), "participants": count, "roles": roles,
        "constituencies": clean(consty),
        "coverage": coverage, "highlights": highlights, "note": note,
    }


def parse_report_b(rep, display_name):
    """Format B carries several districts; keep only this PDF's own block."""
    head = "\n".join(rep["text"].split("\n")[:8])
    m = RE_SUBHDR_B.search(head)
    day = int(m.group("day")) if m else None
    iso, pretty = parse_date(m.group("rest") if m else head)
    if not iso:
        iso, pretty = parse_date(head)
    # A report recovered from the PDF's leading orphan pages has no sub-header at
    # all. Falling back to the raw page text made the report's whole first
    # paragraph its title; the Activity field, or a plain default, is the title.
    if m:
        focus = re.sub(r"[-–—]?\s*\d{1,2}\s+\w+\s+\d{4}\s*$", "",
                       m.group("rest") or "").strip(" -–—")
    else:
        focus = ""

    aliases = [display_name.upper()] + NAME_ALIASES.get(display_name, [])
    # Slice out the "District N <NAME>" block belonging to this district.
    block, taking = [], False
    for l in rep["lines"]:
        dm = RE_DISTRICT_ROW.match(l)
        if dm:
            name = dm.group(2).strip().upper()
            taking = any(name.startswith(a) or a.startswith(name) for a in aliases)
            continue
        if taking:
            block.append(l)
    if not block:
        return None

    fields = parse_fields(block)
    count, roles = parse_participants(fields, "\n".join(block))
    # The value column of the last field row runs on into the bullets, so the
    # bullets are read from the whole block rather than from a labelled section.
    highlights = parse_highlights(block)
    coverage = []
    kind = focus or fields.get("Activity") or "District Profiling"
    kind = clean(re.sub(r"\s+", " ", kind))[:70].strip(" -–—:")
    return {
        "kind": kind.title() if kind.isupper() or kind.islower() else kind,
        "level": level_for(focus + " " + (fields.get("Activity") or "")),
        "day": day, "date": iso, "date_pretty": pretty,
        "format": clean(fields.get("Method") or fields.get("Activity") or ""),
        "participants": count, "roles": roles or clean(fields.get("Key Officials", "")),
        "constituencies": "",
        "coverage": coverage, "highlights": highlights, "note": None,
        "sector_focus": clean(fields.get("Sector Focus", "")),
    }


def split_region_c(lines, display_name):
    """(training_coverage, date_text, count, constituencies) for a format-C header.

    Format C centres its labels in the cell exactly as format A does, so the
    first line of "Training coverage" surfaces ABOVE the label and a
    read-in-order parser files it under the previous row — which is how the
    coverage sentence ended up as the literal string "PM". Here every row that
    IS one of the four known labels is matched explicitly and removed; whatever
    is left in the header block is the coverage text, wherever it sat.
    """
    head = []
    for l in lines:
        if (RE_PARTICIPANTS_HEAD.match(l) or RE_GLIMPSES.match(l)
                or RE_COVERAGE.match(l)):
            break
        head.append(l)
    head = strip_chrome(head)

    # The title line uses the district's own short name ("NELLORE DISTRICT"),
    # which is not always the display name ("SPSR Nellore"), so the aliases have
    # to be consulted or the title leaks into the coverage text.
    titles = title_forms(display_name)

    date_txt, count, cov, consty = "", None, [], []
    for l in head:
        s = clean(l)
        if not s:
            continue
        if s.upper() in titles:
            continue
        m = re.match(r"^Constituenc(?:y|ies)\s+(.+)$", s, re.I)
        if m:
            consty.append(m.group(1))
            continue
        m = re.match(r"^Date\s+(.+)$", s, re.I)
        if m:
            date_txt = m.group(1)
            continue
        m = re.match(r"^Number\s+of\s+participants\s+(\d{1,4})\s*$", s, re.I)
        if m:
            count = int(m.group(1))
            continue
        if re.match(r"^District\s+\S", s, re.I) or re.match(r"^(District|Date)$", s, re.I):
            continue
        # The bare label line itself, centred in its own value block.
        if re.match(r"^(Training coverage|Number of participants)$", s, re.I):
            continue
        m = re.match(r"^Training coverage\s+(.+)$", s, re.I)
        if m:
            cov.append(m.group(1))
            continue
        cov.append(s)
    return clean(" ".join(cov)), date_txt, count, clean("; ".join(consty))


def parse_report_c(rep, display_name):
    secs = section_slices(rep["lines"])
    cov_txt, date_txt, count, consty_c = split_region_c(rep["lines"], display_name)
    iso, pretty = parse_date(date_txt)
    if not iso:
        iso, pretty = parse_date("\n".join(rep["text"].split("\n")[:14]))

    roles = ""
    if secs.get("participants"):
        pts = []
        for l in secs["participants"]:
            m = RE_BULLET.match(l)
            if m:
                # Two bullet columns share a line in these papers.
                for part in re.split(r"\s+[•›]\s+", clean(m.group(1))):
                    part = clean(part)
                    if len(part) > 2:
                        pts.append(part)
        roles = "; ".join(pts)
    if count is None:
        count, _ = parse_participants({}, "\n".join(rep["text"].split("\n")[:30]))

    coverage = parse_coverage(secs.get("coverage", []))
    # Some format-C reports carry no "Brief of the Training" heading at all and
    # put the whole narrative in the Training coverage cell. Left in `format` it
    # would render as the small grey one-liner meant for "in person, 10am-1pm",
    # so a long coverage cell with no brief behind it becomes the body instead.
    fmt_out = cov_txt
    if not coverage and len(cov_txt) > 200:
        coverage, fmt_out = [cov_txt], ""
    # Several of these reports repeat the Training coverage sentence verbatim as
    # the opening of the brief. Rendered, that put the same paragraph on the page
    # twice — once as the grey format line and again as the body. When the brief
    # already opens with it, the format line is the redundant copy.
    elif coverage and cov_txt and len(cov_txt) > 60:
        opener = re.sub(r"\W+", " ", coverage[0][:120]).strip().lower()
        head_txt = re.sub(r"\W+", " ", cov_txt[:120]).strip().lower()
        if opener.startswith(head_txt[:80]) or head_txt.startswith(opener[:80]):
            fmt_out = ""

    return {
        "kind": "Consolidated Status Report",
        "level": level_for(cov_txt),
        "day": None, "date": iso, "date_pretty": pretty,
        "format": fmt_out, "participants": count, "roles": roles,
        "constituencies": consty_c,
        "coverage": coverage, "highlights": parse_highlights(secs.get("highlights", [])),
        "note": None,
    }


# -------------------------------------------------------------------------
# images
# -------------------------------------------------------------------------

def extract_images(pdf_path, slug, display_name, reports, write=True):
    """Lift the embedded JPEGs and tie each to the report whose pages it sits on."""
    outdir = os.path.join(IMG_ROOT, slug)
    if write:
        if os.path.isdir(outdir):
            shutil.rmtree(outdir)
        os.makedirs(outdir, exist_ok=True)

    tmp = os.path.join(outdir, "_raw") if write else None
    if write:
        os.makedirs(tmp, exist_ok=True)
        r = run(["pdfimages", "-j", "-p", pdf_path, os.path.join(tmp, "img")])
        if r.returncode != 0:
            print("  ! pdfimages failed:", r.stderr.strip()[:200], file=sys.stderr)

    listing = run(["pdfimages", "-list", pdf_path]).stdout.splitlines()
    rows = []
    for line in listing[2:]:
        f = line.split()
        if len(f) < 5:
            continue
        try:
            page, num, w, h = int(f[0]), int(f[1]), int(f[3]), int(f[4])
        except ValueError:
            continue
        rows.append((page, num, w, h))

    def report_for(page):
        for i, rep in enumerate(reports):
            if rep["page_from"] <= page < rep["page_to"] + 1:
                return i
        return None

    photos, seq = [], 0
    for page, num, w, h in rows:
        # Logos, rules and spacer slivers are not session photographs.
        if w < 90 or h < 70 or (w * h) < 12000:
            continue
        ar = w / float(h)
        if ar > 4.0 or ar < 0.35:
            continue
        seq += 1
        name = "%s-%02d.jpg" % (slug, seq)
        src = os.path.join(tmp, "img-%03d-%03d.jpg" % (page, num)) if write else None
        if write:
            if not os.path.exists(src):
                alt = os.path.join(tmp, "img-%03d-%03d.ppm" % (page, num))
                if os.path.exists(alt):
                    run(["sips", "-s", "format", "jpeg", alt, "--out",
                         os.path.join(outdir, name)])
                else:
                    seq -= 1
                    continue
            else:
                shutil.move(src, os.path.join(outdir, name))
        ri = report_for(page)
        photos.append({"file": "assets/capacity/%s/%s" % (slug, name),
                       "w": w, "h": h, "page": page, "report": ri})
    if write and tmp and os.path.isdir(tmp):
        shutil.rmtree(tmp)
    return photos


# -------------------------------------------------------------------------
# driver
# -------------------------------------------------------------------------

def build_district(stem, display_name, dkey, write_images=True):
    pdf = os.path.join(PDF_DIR, "Consolidated_Status_Reports_%s.pdf" % stem)
    if not os.path.exists(pdf):
        print("  ! missing PDF:", pdf, file=sys.stderr)
        return None
    txt = run(["pdftotext", "-layout", pdf, "-"]).stdout
    pages = txt.split("\f")
    reports = split_reports(pages)
    slug = slugify(display_name)

    photos = extract_images(pdf, slug, display_name, reports, write=write_images)

    sessions = []
    for i, rep in enumerate(reports):
        if rep["fmt"] == "A":
            s = parse_report_a(rep, display_name)
        elif rep["fmt"] == "B":
            s = parse_report_b(rep, display_name)
        else:
            s = parse_report_c(rep, display_name)
        if s is None:
            continue
        s["photos"] = [p["file"] for p in photos if p["report"] == i]
        s["fmt"] = rep["fmt"]
        sessions.append(s)

    # Order by the date on the report; undated ones keep their file order at the end.
    sessions.sort(key=lambda s: (s["date"] or "9999", s["day"] or 99))

    dated = [s["date"] for s in sessions if s["date"]]
    counts = [s["participants"] for s in sessions if s["participants"]]
    delivered = [s for s in sessions if s["coverage"] or s["highlights"]]

    return {
        "slug": slug, "name": display_name, "district_key": dkey,
        "sessions_total": len(sessions),
        "sessions_delivered": len(delivered),
        "date_from": min(dated) if dated else None,
        "date_to": max(dated) if dated else None,
        "participants_total": sum(counts) if counts else None,
        "participants_reported_for": len(counts),
        "photos_total": len(photos),
        "levels": sorted({s["level"] for s in delivered}),
        "sessions": sessions,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-images", action="store_true",
                    help="parse text only; leave landing/assets/capacity alone")
    args = ap.parse_args()

    if not args.no_images:
        os.makedirs(IMG_ROOT, exist_ok=True)

    out = []
    for stem, (name, dkey) in DISTRICTS.items():
        print("·", name)
        d = build_district(stem, name, dkey, write_images=not args.no_images)
        if d:
            out.append(d)
            print("   %2d sessions (%d delivered) · %s photos · %s participants"
                  % (d["sessions_total"], d["sessions_delivered"],
                     d["photos_total"], d["participants_total"]))

    payload = {
        "districts": out,
        "totals": {
            "districts": len(out),
            "sessions": sum(d["sessions_total"] for d in out),
            "sessions_delivered": sum(d["sessions_delivered"] for d in out),
            "photos": sum(d["photos_total"] for d in out),
            "participants": sum(d["participants_total"] or 0 for d in out),
            "date_from": min([d["date_from"] for d in out if d["date_from"]] or [None]),
            "date_to": max([d["date_to"] for d in out if d["date_to"]] or [None]),
        },
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    t = payload["totals"]
    print("\n→ %s" % os.path.relpath(OUT_JSON, ROOT))
    print("  %d districts · %d sessions (%d delivered) · %d photos · %d participants · %s → %s"
          % (t["districts"], t["sessions"], t["sessions_delivered"], t["photos"],
             t["participants"], t["date_from"], t["date_to"]))


if __name__ == "__main__":
    main()
