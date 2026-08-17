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
# The drop location has moved once already. Try the known places in order and
# use the first that exists, so a rebuild does not silently run on a stale set.
PDF_DIRS = [
    os.path.expanduser("~/Downloads/andhra material/District_Wise_Consolidated_Status_Reports"),
    os.path.expanduser("~/Downloads/District_Wise_Consolidated_Status_Reports"),
]
PDF_DIR = next((d for d in PDF_DIRS if os.path.isdir(d)), PDF_DIRS[0])
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
# "PROGRAMME COVERAGE" is the common heading, but Chittoor files every day as
# "SESSION COVERAGE", Krishna's master day as "PROGRAM COVERAGE", Vizianagaram
# as "DISTRICT LEVEL TRAINING COVERAGE". Only the first was matched, so all
# nine Chittoor sessions shipped with no coverage prose at all.
# Case-SENSITIVE on the COVERAGE part: the section heading is always set in
# capitals, and format C has a mixed-case table LABEL "Training coverage" that
# a case-blind match took for the heading, cutting the header table off
# before its participant count (YSR Kadapa 7 July lost its 32 that way).
RE_COVERAGE = re.compile(r"^\s*(?:(?:[A-Z][A-Z ]{0,30}\s)?COVERAGE|(?i:BRIEF OF [A-Za-z ]{3,40}))\s*$")
RE_HIGHLIGHTS = re.compile(r"^\s*[A-Z][A-Z\-& ]{4,}HIGHLIGHTS\s*$", re.I)
RE_PARTICIPANTS_HEAD = re.compile(r"^\s*PARTICIPANTS\s*$", re.I)
RE_PAGEFOOT = re.compile(r"^\s*Page \d+ of \d+\s*$", re.I)
# The three Word outline glyphs plus the "o" of a second-level list. ● is the one
# that actually costs points: NTR's 29 July master-training report sets every
# bullet with it, so without it that report parsed to zero highlights, and the
# Guntur and Tirupati constituency pages lost all but their first point. The "o"
# needs the uppercase lookahead so the word "o" can never open a bullet.
RE_BULLET = re.compile(r"^\s*(?:[•›▪◦●○‣\-]|o(?=\s{1,3}[A-Z]))\s+(.*)$")
RE_NUMBULLET = re.compile(r"^\s*\d{1,2}[.)]\s+(.+)$")
# A run-in label — "Agriculture-Based Economy: Paddy, groundnut, …". Several
# report writers set their points this way instead of with a bullet glyph, and
# because nothing marks the line as a new item the whole list collapsed into one
# paragraph (Tirupati 3 August shipped 1 point per constituency against 5-6 in
# the PDF). The label has to be short, title-ish and carry text after the colon,
# which is what separates it from an ordinary sentence containing a colon.
RE_RUNIN = re.compile(r"^\s*([A-Z][A-Za-z0-9&()/'’\-, ]{2,58}):\s+(\S.*)$")

# --- report-start detection ----------------------------------------------
# The A-format banner has been typed three ways across the 18 files:
#   "CAPACITY BUILDING PROGRAMME - ANDHRA PRADESH"   (87 reports)
#   "CAPACITY BUILDING TRAINING PROGRAMME"           (Krishna 14 July)
#   "CAPACITY BUILDING PROGRAMME – PHASE II"
# All three sit on their own line in ALL CAPS directly above the
# "Swarna Andhra @ 2047 | ..." sub-header, which is what actually marks a report
# start (see split_reports). Only the first spelling was matched, so Krishna's
# 14 July report was glued onto the tail of 13 July: the day vanished from the
# pager, and its "No of Participants : 51" was read as 13 July's headcount.
# Anchored to a whole line so prose mentions ("Capacity Building Programme was
# conducted at...") cannot start a report.
RE_HDR_A = re.compile(
    r"^\s*CAPACITY BUILDING(?: TRAINING)? PROGRAMME"
    r"(?:\s*[-–—]\s*(?:ANDHRA PRADESH|PHASE\s+[IVX]+))?\s*$", re.I | re.M)
RE_HDR_B = re.compile(r"^\s*CAPACITY BUILDING PROGRAMME\s*$", re.I | re.M)
RE_HDR_C = re.compile(r"SWARNA ANDHRA @\s*2047\s*\|\s*CONSOLIDATED STATUS REPORT", re.I)

RE_SUBHDR_A = re.compile(
    r"Swarna Andhra @\s*2047\s*\|(?P<rest>[^\n]+)", re.I)
RE_SUBHDR_B = re.compile(
    r"Day[:\s]*(?P<day>\d+)\s*Status Report\s*[-–—]\s*(?P<rest>[^\n]+)", re.I)

# The comma is not optional decoration: "1 August, 2026" is how Tirupati's Day 2
# banner is written, and requiring a bare space between month and year shipped
# that whole session as a dateless card at the end of the district.
MONTH_ALT = ("January|February|March|April|May|June|July|August|September"
             "|October|November|December")
RE_DATE = re.compile(
    r"(\d{1,2})\s*(?:st|nd|rd|th)?\s+"
    r"(" + MONTH_ALT + r")"
    r"\s*,?\s*(\d{4})", re.I)
# A dated SECTION LABEL on the multi-district profiling cover cards, which carry
# no full date anywhere: "2nd – 3rd July – District Profiling", "4th July –
# Constituency Profiling (4 Constituencies)". The trailing dash-and-title is what
# makes this safe to read as the card's own date — Visakhapatnam's card also says
# "Constituency Profiling for Kakinada was pre-scheduled for 19th and 20th June",
# a forward note about ANOTHER district, and that phrasing has no dash-title
# behind it, so it is not mistaken for this card's date.
RE_DATE_LABEL = re.compile(
    r"(\d{1,2})\s*(?:st|nd|rd|th)"
    r"(?:\s*[-–—]\s*\d{1,2}\s*(?:st|nd|rd|th))?"
    r"\s+(" + MONTH_ALT + r")"
    r"\s*[-–—]\s*[A-Z]", re.I)
RE_DAY = re.compile(r"Day[:\s]*0?(\d{1,2})\b", re.I)
# Ordered most-explicit first: a bare "Participants 72" is only trusted once the
# stated-count phrasings have all failed, because loose digits near the word turn
# up inside designation lists ("Participants (7 Deputy Director Agriculture…)").
# pdftotext -layout interleaves a table's LEFT label column with its RIGHT value
# column line by line, so a two-line label such as
#     Participants (40
#     Participants)
# comes out with a whole line of the roles list between "(40" and
# "Participants)". A pattern that reads the label as one run can never match
# it, which is why every district that filed its count in the label column
# (Konaseema, Eluru, NTR, Guntur, ...) came out with no headcount at all.
# The bracket form therefore allows one intervening line, and the "No of"
# forms allow the abbreviations actually used ("No.of.", "Participant :").
RE_PARTICIPANT_COUNT = re.compile(
    r"No\.?\s*of\.?\s*Participants?\b[^0-9\n]{0,30}(\d{1,4})"
    r"|Number\s+of\s+participants?\b[^0-9\n]{0,30}(\d{1,4})"
    r"|\(\s*(\d{1,4})\s*(?:[^\n()]*\n)?[^\n()]*?Participants?\s*\)"
    r"|Participants?\s*\(\s*(\d{1,4})\s*\)"
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
    # "constituenc", not "constituency": the plural is "Constituencies", which
    # does not contain the singular, and Srikakulam's 8 July coverage cell —
    # "The profiling for the Amadalavalasa and Tekkali Assembly Constituencies" —
    # matched nothing at all and defaulted to district.
    (re.compile(r"constituenc|mandal", re.I), "constituency"),
    (re.compile(r"district", re.I), "district"),
]

# THE BANNER LIES, THE BODY DOESN'T. Most districts filed every day of their run
# under one boilerplate report type — "Consolidated District Status Report" —
# whatever the day actually was, so the banner alone marked Srikakulam's master
# training and all of Konaseema's constituency days as district sessions. Once,
# it lies the other way: Vizianagaram's 6 August banner says "Constituency
# Profiling Status Report" over a body that says "Training Format: District Level
# Training". So the body is read first and the banner is only the fallback.
#
# Cues are matched two ways. The ROW/HEADING cues are anchored to a laid-out
# line, because that is what makes them structural rather than a passing mention.
# The PHRASE cues are matched against the text with its line breaks collapsed:
# Krishna's 10 July coverage cell wraps as "Format: Constituency Training\n
# Program (In-person)", and a phrase that spans the wrap never matches otherwise.
#
# Order is master, then constituency, then district. A master day is described in
# constituency and district words throughout (it trains mandal officers about the
# district), and a constituency day almost always names the district too, so the
# most specific claim has to win or every day collapses back to "district".
LEVEL_CUES = [
    ("master", [
        # "MASTER TRAINING HIGHLIGHTS", "DISTRICT MASTER TRAINING HIGHLIGHTS".
        re.compile(r"^[ \t]*(?:[A-Z][A-Z&' \-]*\s)?MASTER[A-Z&' \-]*HIGHLIGHTS[ \t]*$", re.M),
     ], [
        re.compile(r"Master Level (?:Capacity Building|Training)", re.I),
        re.compile(r"District Master Training", re.I),
        re.compile(r"Master Trainers?['’]?\s*Training", re.I),
     ]),
    ("constituency", [
        # The "Constituency"/"Constituencies (Covered)" row of the field table.
        re.compile(r"^[ \t]*Constituenc(?:y|ies)(?:[ \t]+Covered)?[ \t]*(?:[ \t]{2}\S.*)?$", re.M),
        # "CONSTITUENCY-LEVEL HIGHLIGHTS", "CONSTITUENCY PROFILE HIGHLIGHTS",
        # and Vizianagaram's "TERTIARY SECTOR AND CONSTITUENCY PROFILING
        # HIGHLIGHTS", which is why words are allowed in front.
        re.compile(r"^[ \t]*(?:[A-Z][A-Z&' \-]*\s)?CONSTITUENCY[A-Z&' \-]*HIGHLIGHTS[ \t]*$", re.M),
        # A title line naming the constituency: "PENAMALURU CONSTITUENCY".
        re.compile(r"^[ \t]*[A-Z][A-Z .&'\-]{2,}\s+CONSTITUENCY[ \t]*$", re.M),
     ], [
        re.compile(r"Constituency Training Program", re.I),
     ]),
    ("district", [
        # Only the structural forms. "District training" turns up in the prose of
        # constituency days too ("as covered in the district training"), and
        # taking that at face value pushed Parvathipuram Manyam's 24 July
        # constituency report back to district.
        re.compile(r"^[ \t]*DISTRICT[A-Z&' \-]*(?:TRAINING|PROFILING)[A-Z&' \-]*"
                   r"(?:HIGHLIGHTS|COVERAGE|GLIMPSES)[ \t]*$", re.M),
        re.compile(r"^[ \t]*(?:Training|Session)\s+Format[ \t]{2,}.{0,40}?"
                   r"District[ \-]?(?:Level Training|Profiling|Training)", re.M | re.I),
     ], []),
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


def parse_date(text, default_year=None):
    """First real date in `text`, as (iso, pretty). None when there isn't one.

    `default_year` opens the second pass over dated section labels, which state
    a day and a month but never a year. It is only ever passed a year read off
    the same PDF: with no year in evidence the card stays undated rather than
    being dated by guesswork.
    """
    m = RE_DATE.search(text or "")
    if m:
        d, mon, y = int(m.group(1)), MONTHS[m.group(2).lower()], int(m.group(3))
        if not (1 <= d <= 31) or not (2024 <= y <= 2030):
            return None, None
        return "%04d-%02d-%02d" % (y, mon, d), m.group(0)
    if default_year is None:
        return None, None
    # Runs of spaces are collapsed first: the label sits in a layout-mode table
    # cell, so "4th July – District Profiling" arrives padded, and a range can be
    # split across the padding.
    m = RE_DATE_LABEL.search(re.sub(r"[ \t]+", " ", text or ""))
    if not m:
        return None, None
    # The FIRST day of a range: "2nd – 3rd July – District Profiling" is a card
    # covering both days, and the session list is ordered by the day work began.
    d, mon = int(m.group(1)), MONTHS[m.group(2).lower()]
    if not (1 <= d <= 31):
        return None, None
    pretty = m.group(0).rstrip()
    pretty = re.sub(r"\s*[-–—]\s*[A-Z]$", "", pretty) + " %d" % default_year
    return "%04d-%02d-%02d" % (default_year, mon, d), pretty


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

    A heading is recognised with an empty buffer, i.e. straight after a blank
    line, or behind a line that closed a sentence. Inside a wrapped run, a short
    title-case line is far more likely to be the tail of a sentence than a new
    sub-heading — but only mid-sentence. Several reports run their sub-headings
    straight on from the previous paragraph with no blank line at all, and the
    empty-buffer rule alone lost every one of them (Guntur 3 August kept only
    "Ponnur Constituency" and swallowed "Guntur East" and "Guntur West"; the ten
    department headings of Konaseema 18 July collapsed to one).
    """
    paras, buf, bulleted = [], [], False

    def flush():
        if buf:
            paras.append(("• " if bulleted else "") + " ".join(buf))
        return [], False

    def sentence_closed():
        return bool(buf) and buf[-1].rstrip().endswith((".", "!", "?"))

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
        if heading_like(s) and (not buf or sentence_closed()):
            buf, bulleted = flush()
            paras.append(clean(s).rstrip(":"))
            continue
        # A run-in label opens its own point. It is only honoured behind a closed
        # sentence or a blank line, so a colon inside a wrapped sentence cannot
        # chop the sentence in half.
        if runin_label(l) and (not buf or sentence_closed()):
            buf, bulleted = flush()
            buf, bulleted = [clean(s)], False
            continue
        # A heading that follows a bullet with NO blank line between them. The
        # source template sets constituency sub-headings flush against the last
        # bullet of the previous constituency, and pdftotext keeps them that way,
        # so the empty-buffer test above never fires and "Alur" was appended as
        # the closing word of Pattikonda's third bullet — its own three bullets
        # then filed under Pattikonda. Kurnool 21 July lost Alur and Panyam this
        # way. It is safe to close the bullet here only because a bullet's true
        # continuation is never a lone one-or-two-word title-case line whose
        # predecessor already ends in a full stop.
        if (bulleted and heading_like(s) and len(s.split()) <= 3
                and buf and buf[-1].rstrip().endswith((".", "!", "?"))):
            buf, bulleted = flush()
            paras.append(s)
            continue
        buf.append(s)
    flush()
    return stitch(paras)


def runin_label(line):
    """The label of a "Label: text" point, or None. Not a sentence with a colon."""
    m = RE_RUNIN.match(line)
    if not m:
        return None
    lab = m.group(1).strip()
    # A label is a name, not a clause: a handful of words. "Infrastructure Gaps"
    # and "Growth Opportunities" pass; a long wrapped line that happens to carry a
    # colon does not, so a sentence is never chopped at its own punctuation.
    if not (1 <= len(lab.split()) <= 7):
        return None
    return lab


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


# Column headings of the Field/Details table, and the label column's own words.
# They are short and title-case, so they read exactly like a sub-heading, and
# they were being filed as one — Prakasam's 18 June card shipped its bullets
# under a heading called "Field Details". They are never a real heading.
RE_TABLE_HEAD = re.compile(
    r"^\s*(?:Field\s+Details|Field|Details|Sector\s+Focus|Method|Activity"
    r"|Key\s+Findings|Key\s+Officials|Constituenc(?:y|ies)\s+Covered|Covered)\b"
    # The label's own value trails it on the same line as often as not, because
    # the two columns collapse into one line in a layout-mode extract
    # ("Sector Focus     Primary Sector"). Heading or heading-plus-value, it is
    # the table talking, not the report.
    r"\s*:?(?:\s.*)?$", re.I)


def heading_like(s):
    """A short, title-ish line with no terminal punctuation — a sub-heading."""
    if len(s) > 60 or not s:
        return False
    if s.endswith((".", ",", ";")):
        return False
    # A trailing colon is how the sector sub-headings are set in the Tirupati
    # 31 July report ("Sericulture:", "Fisheries:", …). Rejecting it merged all
    # six sectors into one blank-headed group. The colon is dropped by the caller.
    if s.endswith(":"):
        s = s[:-1].rstrip()
        if not s:
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


# Primary row labels of the format-A header table. Anything else at column 0 is
# either a continuation fragment of the current row's label ("Kodumuru",
# "(65 Participants)", "Gopalapuram (80") or an unlabelled title row.
HEADER_ROW_LABELS = [
    "Session Format", "Training Format", "Training Level", "Training coverage", "Format",
    "Constituency", "Constituencies", "Constituencies Covered",
    "Participants", "Key Officials", "Key Officers Present", "Key Officers", "Participants from",
    "Number of participants", "No of Participants", "No. of Participants",
    "Sector Focus", "Method", "Activity", "Date", "Focus", "Key Findings",
]
RE_HEADER_ROW = re.compile(
    r"^\s*(" + "|".join(re.escape(x) for x in sorted(HEADER_ROW_LABELS, key=len, reverse=True))
    + r")\b", re.I)
FORMAT_ROWS = ("session format", "training format", "training coverage", "training level", "format")
CONSTY_ROWS = ("constituency", "constituencies", "constituencies covered")
PEOPLE_ROWS = ("participants", "key officials", "key officers present", "key officers",
               "participants from", "number of participants", "no of participants",
               "no. of participants")


def parse_header_table(lines, display_name):
    """Column-aware read of the format-A header table.

    pdftotext -layout emits the table as two interleaved columns: the LABEL
    column at x=0 and the VALUE column at a fixed indent (22-27). A tall cell
    centres its label vertically inside its own value lines, and a label that
    wraps ("Participants (53" / "Participants)") lands on two non-adjacent lines
    with a whole line of the value column between them. Reading line by line
    therefore mixed labels into values (the roles list bled into "format", the
    district title bled into "format") and split counts across lines so no
    regex could see them ("(53 Participants)" was never one string).

    Split each line at the value column instead. The left fragments joined in
    order rebuild every label exactly as printed — "Participants (53
    Participants)", "Participants (40 + 22 Participants)", "Participants
    Gopalapuram (80 Participants) Kovvur (45 Participants)" — and the right
    fragments are the values. Value lines that precede a row's label line
    (a centred label) are given to that row when the row is at least as long
    below the label as above it, which is what vertical centring produces;
    otherwise they stay with the previous row.

    Returns {format, consty, people_blob, label_stream, rows} or None when no
    value column can be established (caller falls back to split_region_a).
    """
    body = []
    for l in lines:
        if RE_GLIMPSES.match(l) or RE_COVERAGE.match(l) or RE_HIGHLIGHTS.match(l):
            break
        body.append(l)
    body = strip_chrome(body)
    titles = title_forms(display_name)

    # Value column. Prefer the start of the value on a line that carries a label
    # inline ("Training Format   Master Training: ..."). But a centred label is
    # often ALONE on its line with every value line indented above and below it
    # (NTR 22 July, Kurnool 18 July), so fall back to the dominant indent of the
    # indented lines that sit between column-0 labels: that indent IS the value
    # column. Nothing is guessed — the table has to have at least one column-0
    # label and at least two indented lines for this to be trusted.
    label_rx = re.compile(r"^\s*(" + "|".join(re.escape(x) for x in HEADER_ROW_LABELS) + r")\b", re.I)
    cols = []
    for l in body:
        m = re.match(r"^\s*(" + "|".join(re.escape(x) for x in HEADER_ROW_LABELS) + r")[^\S\n]{2,}(\S)", l, re.I)
        if m:
            cols.append(m.start(2))
    if not cols:
        has_label = any(label_rx.match(l) and len(l) - len(l.lstrip()) < 4 for l in body)
        indents = [len(l) - len(l.lstrip()) for l in body
                   if l.strip() and 12 <= len(l) - len(l.lstrip()) <= 40]
        if has_label and len(indents) >= 2:
            # the mode of the indents
            cols = [max(set(indents), key=indents.count)]
    if not cols:
        return None
    vcol = min(cols)
    if vcol < 12:
        return None

    rows = []          # [{label, frags:[..], vals:[..]}]
    pending = []       # value lines seen before any row / between rows
    cur = None

    def start_row(label_text):
        nonlocal cur
        # above/below: value lines received before / after the label line. A
        # centred label has as many below as above, which is how the pending
        # lines between two rows are shared out (see below).
        cur = {"label": label_text, "frags": [], "vals": [], "above": 0, "below": 0}
        rows.append(cur)

    for l in body:
        raw = l.rstrip("\n")
        if not raw.strip():
            continue
        s = clean(raw)
        if s.upper() in titles:
            continue
        # An all-caps place title is never a value: "DR. B R AMBEDKAR KONASEEMA
        # DISTRICT" (a spelling title_forms does not carry) and even a WRONG
        # district title in the source ("EAST GODAVARI DISTRICT" printed on a
        # Krishna page) both landed at the front of that day's format text.
        # Constituency title lines ("PENAMALURU CONSTITUENCY (Focus: ...)") are
        # kept aside as the report's title, not as a format value.
        if re.match(r"^[A-Z0-9 .,&'()\-]+$", s) and re.search(r"\bDISTRICT\b", s):
            continue
        indent = len(raw) - len(raw.lstrip())
        left = raw[:vcol].strip() if indent < vcol - 3 else ""
        right = raw[vcol:].strip() if len(raw) > vcol else ""
        # a line whose text runs continuously across the column boundary is one
        # full-width cell (a title such as "PENAMALURU CONSTITUENCY (...)"), not
        # a label beside a value
        if left and right and len(raw) > vcol and raw[vcol - 2:vcol].strip():
            start_row("")
            cur["vals"].append(s)
            continue
        if left:
            m = RE_HEADER_ROW.match(left)
            if m:
                # decide who owns the pending value lines: count how many value
                # lines follow this label before the next label; a centred
                # label has at least as many below as above
                start_row(m.group(1))
                if right:
                    cur["vals"].append(right)
                # Share the pending value lines between the previous row and
                # this one. A label is vertically centred in its cell, so the
                # previous row is still owed as many lines BELOW its label as it
                # received ABOVE it; it takes that many, and the rest belong to
                # this row (as its own lines above a centred label). NTR 25 July:
                # "Training Format" had one line above and one line so far below
                # — the pending line was already the balance, and giving it to
                # "Key Officers" instead put "(18 participants)" into the roles
                # blob and read the day as 108, not 90.
                if pending:
                    prev = rows[-2] if len(rows) >= 2 else None
                    if prev is not None:
                        owed = max(0, prev["above"] - prev["below"])
                        take = pending[:owed]
                        prev["vals"].extend(take)
                        prev["below"] += len(take)
                        pending = pending[owed:]
                    if pending:
                        cur["vals"] = pending + cur["vals"]
                        cur["above"] += len(pending)
                    pending = []
                # any leftover after the label on the same line that is not the
                # value (e.g. "Participants (53") is part of the label
                rest = left[m.end():].strip()
                if rest:
                    cur["frags"].append(rest)
                continue
            # not a primary label: a fragment of the current row's label, or an
            # unlabelled title row when there is no current row
            if cur is not None and (len(left.split()) <= 5 or "(" in left or "articipant" in left):
                # a fragment line settles anything pending onto this row first
                if pending:
                    cur["vals"].extend(pending); cur["below"] += len(pending); pending = []
                cur["frags"].append(left)
                if right:
                    cur["vals"].append(right); cur["below"] += 1
                continue
            start_row("")
            cur["frags"].append(left)
            if right:
                cur["vals"].append(right)
            continue
        # value-only line
        if right:
            if cur is None:
                pending.append(right)
            else:
                # could belong to the NEXT row's centred label; hold it
                pending.append(right)
    if pending and cur is not None:
        cur["vals"].extend(pending)
        cur["below"] += len(pending)

    def flat(vals):
        out = ""
        for v in vals:
            if out.endswith("-") and v[:1].islower():
                out = out[:-1] + v          # "in-per-" + "son" -> "in-person"
            else:
                out = (out + " " + v).strip()
        return out

    fmt, consty, people, label_stream = [], [], [], []
    for r in rows:
        lab = r["label"].lower()
        label_text = " ".join([r["label"]] + r["frags"]).strip()
        label_stream.append(label_text)
        val = flat(r["vals"])
        if lab in FORMAT_ROWS:
            fmt.append(val)
        elif lab in CONSTY_ROWS:
            consty.append(val)
        elif lab in PEOPLE_ROWS or "articipant" in label_text.lower():
            # values only: the label text is already in label_stream, and
            # carrying it here too made every bracketed count read twice
            people.append(val)
    return {
        "format": " ".join(x for x in fmt if x),
        "consty": " ".join(x for x in consty if x),
        "people_blob": " ".join(people),
        "label_stream": " ".join(label_stream),
        "rows": rows,
    }


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
        # The series has to START at the lead-in. Without this the scan wandered
        # into the roles list and read designations that happen to end in a
        # number — "Village Surveyors (VS-1 to VS-4" gave Krishna 14 July a
        # headcount of 5 (1 + 4) in place of the "No of Participants : 51" it
        # had just walked past.
        if end is None and m.start() > 6:
            break
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


# One report, several participant blocks — a table row per constituency or per
# half-day:
#     Participants - Kodumuru    (65 Participants)  <roles...>
#     Participants - Pattikonda  (79 Participants)  <roles...>
# These are separate blocks, not a series on one line, so sum_sub_counts (which
# reads a single line) cannot see them, and the first-match-wins loop below
# reported only the first: Kurnool 28 July went in as 65 of 144, Nellore 14 July
# as 52 of 115, Nandyal 3 August as 15 of 50.
#
# Matching each count back to its own row label is not reliable — pdftotext wraps
# a table cell across several lines, so "Participants -", "Kodumuru" and
# "(65 Participants)" each land on a different line with roles text beside them.
# So collect the EXPLICIT count forms instead and read their arithmetic. Only
# these two forms count: the bracketed "(N Participants)" and an explicit
# "No of Participants: N". Prose like "Approximately 72 officers" is deliberately
# excluded, because it usually restates a figure the table already gave and would
# double it (Kurnool 29 and 30 July both do exactly that).
RE_COUNT_FORMS = [
    # "(40 Participants)", allowing one interleaved roles line inside the bracket
    re.compile(r"\(\s*(\d{1,4})\s*(?:[^\n()]*\n)?[^\n()]*?Participants?\s*\)", re.I),
    # "Participants (48)" — bare number in the label
    re.compile(r"Participants?\s*\(\s*(\d{1,4})\s*\)", re.I),
    # "No of Participants : 51", "No. of Participant: 57", "No.of. Participant:79"
    re.compile(r"No\.?\s*of\.?\s*Participants?\b[^0-9\n]{0,60}?(\d{1,4})", re.I),
]

# ADDITIVE counts, written as one expression: "No of Participants: 100+62",
# "60(Palamaneru) + 72(Chittoor)", "(40 + 22 Participants)",
# "(21 from Saluru +52 from Parvathipuram)". These are the day's parts and the
# day is their sum. Read as a whole so the "+" is never mistaken for the end of
# the number (Chittoor 24 July went in as 100, the "+62" left dangling at the
# start of the roles text).
RE_ADDITIVE = re.compile(
    r"(?:No\.?\s*of\.?\s*Participants?\b[^0-9\n]{0,30}|Participants?\s*\(\s*|\(\s*)"
    r"(\d{1,4})\s*(?:\([^)]{0,30}\)|from\s+[A-Za-z .]{2,30})?"
    r"(?:\s*\+\s*(\d{1,4})\s*(?:\([^)]{0,30}\)|from\s+[A-Za-z .]{2,30})?){1,6}", re.I)


def sum_additive(text):
    """Total of an explicit 'a + b [+ c]' participant expression, else None."""
    best = None
    for m in RE_ADDITIVE.finditer(text or ""):
        nums = [int(x) for x in re.findall(r"\d{1,4}", m.group(0))
                if 1 <= int(x) <= 2000]
        # the leading token may itself be a bracketed sub-label number, e.g.
        # "60(Palamaneru)"; re.findall keeps every integer, which is what we want
        # only when the expression really is a sum: require a "+" in the match
        if "+" not in m.group(0) or len(nums) < 2:
            continue
        tot = sum(nums)
        if 1 <= tot <= 5000:
            best = tot if best is None else max(best, tot)
    return best


def sum_labelled_blocks(text):
    """Total for a report that states several participant counts, else None.

    When one of the figures equals the sum of the others it is the day's stated
    TOTAL and its parts are a breakdown, so the total wins: NTR 25 July files
    "(90 participants)" for the day beside "(72 participants)" and
    "(18 participants)" for the two constituencies, and summing all three would
    report 180 for a 90-officer day. Otherwise the figures are separate blocks
    and the day is their sum.
    """
    hits = []
    for rx in RE_COUNT_FORMS:
        for m in rx.finditer(text or ""):
            n = int(m.group(1))
            if 1 <= n <= 2000:
                hits.append((m.start(), n))
    # the two patterns can match the same figure; keep one per position
    vals, seen = [], []
    for pos, n in sorted(hits):
        if any(abs(pos - q) < 8 for q in seen):
            continue
        seen.append(pos)
        vals.append(n)
    if len(vals) < 2:
        return None
    for i, v in enumerate(vals):
        if v == sum(vals[:i] + vals[i + 1:]):
            return v
    total = sum(vals)
    return total if 1 <= total <= 5000 else None


def count_from(text):
    """The most deliberate count statement in one text, or None: an explicit
    a + b expression, then several separate blocks, then a single figure."""
    if not text:
        return None
    v = sum_additive(text)
    if v is not None:
        return v
    v = sum_labelled_blocks(text)
    if v is not None:
        return v
    m = RE_PARTICIPANT_COUNT.search(text)
    if m:
        v = sum_sub_counts(text[m.start():])
        if v is not None:
            return v
        val = next((g for g in m.groups() if g), None)
        if val and 1 <= int(val) <= 2000:
            return int(val)
    return None


def parse_participants(fields, text, label_stream=None):
    """(count, roles). Count is only reported when the source states one.

    `label_stream` is the header table's rebuilt label column (see
    parse_header_table). It is read ON ITS OWN before the report text: the
    same "(80 Participants)" appears in both, and reading them together
    counted every block twice (East Godavari 14 July came out at 215 for a
    125-officer day)."""
    roles = fields.get("Participants") or fields.get("Key Officials") or ""
    count = count_from(label_stream) if label_stream else None
    # Read the WHOLE report, not just the participants cell. The parts of a day
    # and its stated total often sit in different cells — NTR 25 July puts the
    # two constituency figures in "Training Format" and the day's total in
    # "Key Officers Present" — so looking at one cell alone sees the total and
    # one part, and sums them into a number the day never had (108 for a
    # 90-officer day).
    # Order: an explicit "a + b" expression is the most deliberate statement a
    # report can make, so it wins; then several separate blocks; then one figure.
    if count is None:
        add = sum_additive(text)
        if add is not None:
            count = add
        else:
            blocks = sum_labelled_blocks(text) or sum_labelled_blocks(fields.get("Participants", ""))
            if blocks is not None:
                count = blocks
    for chunk in () if count is not None else (
                  fields.get("Participants", ""), fields.get("Number Of Participants", ""),
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
    # Covers the abbreviated spellings and an additive tail: "No. of Participant
    # : 57", "No of Participants: 100+62", a leading "+62" or "(Palamaneru) +
    # 72(Chittoor)" left over from an expression that started in the label.
    roles = re.sub(r"(No\.?\s*of\.?\s*Participants?|Number of participants?)\s*[:\-]?\s*\d+"
                   r"(?:\s*(?:\([^)]{0,30}\)|from\s+[A-Za-z .]{2,30}))?(?:\s*\+\s*\d+(?:\s*(?:\([^)]{0,30}\)|from\s+[A-Za-z .]{2,30}))?)*\s*[:,.]?",
                   "", roles, flags=re.I)
    roles = re.sub(r"^\s*(?:\([^)]{0,30}\)\s*)?(?:\+\s*\d+\s*(?:\([^)]{0,30}\))?\s*)+", "", roles)
    roles = re.sub(r"^\s*\(?\d{1,4}\s*Participants?\)?\s*", "", roles, flags=re.I)
    # "Approximately 72 officers drawn from mandals across X district, including
    # Younger Professionals..." — cut through to "including" when it is there,
    # otherwise to "drawn from"; the non-greedy form stopped at the first of the
    # two and left "mandals across YSR Kadapa district, including" dangling.
    roles = re.sub(r"^\s*(Approximately\s+)?\d+\s+(officers?|officials?)\b[^.]{0,200}?\bincluding\s*[;:,]?\s*",
                   "", roles, flags=re.I)
    roles = re.sub(r"^\s*(Approximately\s+)?\d+\s+(officers?|officials?)\b.*?drawn from\s*[;:,]?\s*",
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
        if not pts:
            continue
        head = g["head"]
        # This is a standalone status page appended behind the highlights, about
        # OTHER districts entirely — NTR's 27 July report ends with a page on
        # Parvathipuram Manyam and Konaseema. Reported as an NTR highlight group
        # it credited NTR with another district's day.
        if re.match(r"^Status of (?:the\s+)?Remaining\b.*Districts?$", head, re.I):
            continue
        if RE_TABLE_HEAD.match(head):
            head = ""
        # Two unheaded runs in a row are one run: the table header that used to
        # separate them was furniture, not a heading.
        if not head and out and not out[-1]["head"]:
            out[-1]["points"].extend(pts)
            continue
        out.append({"head": head, "points": pts})
    return out


# -------------------------------------------------------------------------
# per-format report parsers
# -------------------------------------------------------------------------

def level_from_body(text):
    """The level the report's own body states, or None when it states none."""
    if not text:
        return None
    # The label column is vertically centred in its cell, so a label line
    # surfaces part-way DOWN its own wrapped value: Krishna's 10 July coverage
    # reads "…Format: Constituency Training / Training coverage / Program
    # (In-person)…". Dropping the label lines before the text is flattened is
    # what lets the phrase cue see "Constituency Training Program" at all.
    flat = re.sub(r"\s+", " ",
                  "\n".join(l for l in text.split("\n") if not RE_LABEL_ONLY.match(l)))
    for lvl, line_rx, phrase_rx in LEVEL_CUES:
        if any(rx.search(text) for rx in line_rx) or any(rx.search(flat) for rx in phrase_rx):
            return lvl
    return None


def level_for(kind, body=""):
    """Delivery level: what the body says, else what the report type says."""
    lvl = level_from_body(body)
    if lvl:
        return lvl
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
    ht = parse_header_table(rep["lines"], display_name)
    if ht:
        fmt_txt, pblob, consty = ht["format"], ht["people_blob"], ht["consty"]
        # the rebuilt label column is where a wrapped count lives; it is read on
        # its own first (see parse_participants)
        label_stream = ht["label_stream"] + "\n" + ht["people_blob"]
    else:
        fmt_txt, pblob, consty = split_region_a(rep["lines"], display_name)
        label_stream = None
    # Always hand over the WHOLE report as `text`. Passing pblob in its place
    # (the old `pblob or rep["text"]`) meant the total-vs-parts check could only
    # see the participants cell, and NTR 25 July, whose two constituency figures
    # sit in the Training Format cell and whose day total sits in Key Officers
    # Present, summed a part with the total and reported 108 for a 90-officer day.
    count, roles = parse_participants({"Participants": pblob}, rep["text"], label_stream)

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
        "level": level_for(kind, rep["text"]),
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
        # The body cues are read from this district's OWN block: a format-B report
        # carries several districts, and the neighbouring block is a different
        # day's work at a different level.
        "level": level_for(focus + " " + (fields.get("Activity") or ""),
                           "\n".join(block)),
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
        # a centred label whose value sits on its OWN lines above and below it
        # (YSR Kadapa 7 July: "32 (reported constituency-wise: Jammalamadugu: 12;
        # ..." on the line above "Number of participants", "Rajampet: 6)" on the
        # line below). The stated day total is the leading figure; the bracket
        # is its breakdown and is not added.
        if re.match(r"^Number\s+of\s+participants\s*$", s, re.I):
            i = head.index(l)
            for l2 in head[max(0, i - 2):i]:
                m2 = re.match(r"^\s*(\d{1,4})\b", l2.strip())
                if m2:
                    count = int(m2.group(1))
                    break
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
        "level": level_for(cov_txt, rep["text"]),
        "day": None, "date": iso, "date_pretty": pretty,
        "format": fmt_out, "participants": count, "roles": roles,
        "constituencies": consty_c,
        "coverage": coverage, "highlights": parse_highlights(secs.get("highlights", [])),
        "note": None,
    }


# -------------------------------------------------------------------------
# images
# -------------------------------------------------------------------------

# The lightbox opens a photo at up to ~760px wide, but the embedded source is
# a median 220px, so the browser was bilinear-stretching it ~3x and it went soft.
# A build-time upscale can't invent detail that was never captured — what it can
# do is replace that stretch with a better-reconstructed one, and put back the
# edge acutance interpolation removes. Enhanced copies live in <slug>/lg/ and are
# loaded ONLY by the lightbox; the thumbnail rail keeps the small originals so the
# grid stays cheap.
LG_TARGET_W = 760          # the lightbox's own max width
LG_MAX_SCALE = 3.2         # past this, upscaling only makes the mush bigger
LG_SKIP_ABOVE = 700        # already big enough to open as-is


def enhance_for_lightbox(src, dst):
    """Write an upscaled, de-blocked, re-sharpened copy. False if not worth it."""
    try:
        import cv2
        import numpy as np  # noqa: F401  (cv2 needs it present)
    except ImportError:
        return False
    im = cv2.imread(src)
    if im is None:
        return False
    h, w = im.shape[:2]
    if w >= LG_SKIP_ABOVE:
        return False
    scale = min(LG_MAX_SCALE, float(LG_TARGET_W) / w)
    if scale <= 1.05:
        return False

    # De-block BEFORE sharpening. These JPEGs are compressed hard enough that an
    # unsharp mask applied straight to them amplifies the 8x8 blocking into a
    # visible lattice — the artefact ends up crisper than the subject.
    den = cv2.bilateralFilter(im, d=5, sigmaColor=28, sigmaSpace=5)
    up = cv2.resize(den, (int(w * scale), int(h * scale)),
                    interpolation=cv2.INTER_LANCZOS4)
    blur = cv2.GaussianBlur(up, (0, 0), 1.4)
    sharp = cv2.addWeighted(up, 1.55, blur, -0.55, 0)

    # Dim indoor phone frames: mild LOCAL contrast on luminance only, so the
    # colour of a sari or a lanyard is not pushed around with it.
    lab = cv2.cvtColor(sharp, cv2.COLOR_BGR2LAB)
    ch = list(cv2.split(lab))
    ch[0] = cv2.createCLAHE(clipLimit=1.6, tileGridSize=(8, 8)).apply(ch[0])
    out = cv2.cvtColor(cv2.merge(ch), cv2.COLOR_LAB2BGR)

    os.makedirs(os.path.dirname(dst), exist_ok=True)
    return bool(cv2.imwrite(dst, out, [int(cv2.IMWRITE_JPEG_QUALITY), 86]))


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
        rec = {"file": "assets/capacity/%s/%s" % (slug, name),
               "w": w, "h": h, "page": page, "report": ri}
        if write and enhance_for_lightbox(os.path.join(outdir, name),
                                          os.path.join(outdir, "lg", name)):
            rec["lg"] = "assets/capacity/%s/lg/%s" % (slug, name)
        photos.append(rec)
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
        # [thumbnail, enhanced-or-null] per photo: the rail loads the first, the
        # lightbox prefers the second and falls back to the first.
        s["photos"] = [[p["file"], p.get("lg")] for p in photos if p["report"] == i]
        s["fmt"] = rep["fmt"]
        sessions.append((s, rep))

    # Second pass for the cards that state a day and a month but no year: the
    # profiling cover card at the front of Srikakulam, East Godavari, Krishna and
    # YSR Kadapa is labelled "2nd – 3rd July – District Profiling" and nothing
    # else. The year is taken from the rest of THIS PDF, and only when every
    # dated report in it agrees on one — a file spanning a year boundary would
    # otherwise have its undated card dated by guesswork.
    years = {s["date"][:4] for s, _ in sessions if s["date"]}
    if len(years) == 1:
        year = int(next(iter(years)))
        for s, rep in sessions:
            if not s["date"]:
                s["date"], s["date_pretty"] = parse_date(rep["text"], default_year=year)
    sessions = [s for s, _ in sessions]

    # Order by the date on the report; undated ones keep their file order at the end.
    sessions.sort(key=lambda s: (s["date"] or "9999", s["day"] or 99))

    # A few PDFs carry the same report twice, once with a "Day: N" label and once
    # without (Nandyal's 3 August profiling round is filed twice, 99.5% identical
    # text). Counting both doubled that day's attendance and put two identical
    # cards in the pager. Same date + same account of the day is the same report,
    # so keep the richer copy: photos are attached per report instance, and the
    # duplicate can be the one that carries them.
    deduped, seen = [], {}
    for s in sessions:
        fingerprint = (s["date"], s["level"],
                       " ".join(s.get("coverage") or [])[:400],
                       str(s.get("highlights"))[:400])
        prev = seen.get(fingerprint)
        if prev is None:
            seen[fingerprint] = len(deduped)
            deduped.append(s)
            continue
        keep = deduped[prev]
        if len(s.get("photos") or []) > len(keep.get("photos") or []):
            merged = dict(s)
            merged["day"] = keep.get("day") if keep.get("day") is not None else s.get("day")
            deduped[prev] = merged
        print("      duplicate report merged: %s %s" % (s["date"], s["kind"][:44]))
    sessions = deduped

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
