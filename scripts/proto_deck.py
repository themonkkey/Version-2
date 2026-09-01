#!/usr/bin/env python3
"""Horizontal "deck" reader for one case study, rendered from typed content.

Consumes scripts/deck_content/<slug>.json (see scripts/deck_schema.md) and
writes landing/cases/<slug>.html. Each section is a full-viewport slide laid
out horizontally; left/right arrows, keyboard and swipe move between slides.
Content is typed one block per source structure and each block type owns a
purpose-built layout, so the flattening failures of the old parse-based
pipeline (peer items losing their grouping, headers reading as items, stats
losing labels, flows/tables/phases collapsed into chip walls) cannot recur.

The visual chrome (page skeleton, glass panel, cover/agenda/closing, role
tinting, nav) is unchanged; only the content pipeline is new.

    python3 scripts/proto_deck.py [slug|File.txt]   # write pages
    python3 scripts/proto_deck.py --check           # integrity engine
    python3 scripts/proto_deck.py --fixture         # render the fixture
"""
import re
import os
import sys
import json
import math
import tempfile

import build_case_studies as B

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deck_content")

# theme tint by keyword — CVD-aware base hues, matched to the dashboard palette
TINTS = [
    (("agri", "coconut", "coir", "banana", "paddy", "farm", "fpo", "fpc", "organic"),
     ("#6FA817", "#B7D66B")),           # green
    (("shrimp", "aqua", "blue", "fish", "biofloc", "tilapia", "marine", "ethanol"),
     ("#2B93BF", "#7FD4E8")),           # aqua
    (("ceramic", "manufactur", "textile", "cluster", "port", "industrial"),
     ("#BF8A2B", "#E8C46B")),           # amber
    (("tourism", "responsible"),
     ("#1FA69A", "#7FE3D6")),           # teal
]
DEFAULT_TINT = ("#8FC93A", "#C6EC8F")


def tint_for(m):
    hay = (m.get("theme", "") + " " + m.get("title", "") + " " + m.get("eyebrow", "")).lower()
    for keys, pair in TINTS:
        if any(k in hay for k in keys):
            return pair
    return DEFAULT_TINT


# Map a section title to a REUSABLE role, so one common asset (media/common/<role>.jpg
# or .mp4) can back the same kind of slide across every case study. Per-case assets
# still win when present; this is the shared fallback layer before the mesh gradient.
ROLES = [
    ("action",      ("problem", "case for action", "why", "trap", "challenge we", "gap")),
    ("solution",    ("answer", "solution", "ecosystem", "build the", "opportunity", "strategy", "vision")),
    ("key-factors", ("key factor", "pillar", "driver", "enabler", "initiative", "what worked",
                     "success", "model", "how ")),
    ("policy",      ("government", "policy", "scheme", "support", "incentive", "institution")),
    ("context",     ("bigger picture", "global", "standing", "context", "overview", "landscape",
                     "evolution", "background")),
    ("challenges",  ("challenge", "risk", "constraint", "barrier", "bottleneck", "threat")),
    ("takeaways",   ("takeaway", "lesson", "roadmap", "way forward", "recommendation", "conclusion",
                     "replicat", "action plan", "next step")),
]


def role_for(title, blocks=None):
    """Pick the background role from the section title, then from its own text.

    Titles in these decks are often generic ("Overview", "PILOT LAUNCHED"), so a
    title-only match filed nearly every Kurnool section as `context` and every
    slide ended up wearing the same background. Falling through to the section
    body is still a content match - it just reads the content that is actually
    there rather than the label on top of it.
    """
    t = (title or "").lower()
    for role, keys in ROLES:
        if any(k in t for k in keys):
            return role
    if blocks:
        body = (blocks if isinstance(blocks, str)
                else " ".join(str(x) for b in blocks for x in b[1:])).lower()
        best, hits = None, 0
        for role, keys in ROLES:
            n = _hits(body, keys)
            if n > hits:
                best, hits = role, n
        if best:
            return best
    return "context"


# ---------------------------------------------------------------- icons
# Inline SVG sprite rather than an icon webfont: these pages already reach out
# for Google Fonts and gsap, and an icon set is exactly the kind of thing that
# renders as tofu when a network is slow. 24x24, stroke, currentColor, so every
# icon inherits the slide's accent with no per-icon colour to maintain.
ICONS = {
    "leaf":    '<path d="M5 21c.5-4.5 2.5-8 7-10"/><path d="M9 18c6.2 0 10-3.4 10-9V5h-4.5C9 5 6 8 6 12.5 6 15.5 7.5 18 9 18z"/>',
    "drop":    '<path d="M12 3l4.6 6.1a6 6 0 1 1-9.2 0z"/>',
    "fish":    '<path d="M16.7 9.3a7.5 7.5 0 0 1 0 5.4M2 12c3-4 6.5-6 10-6s6.5 2 10 6c-3.5 4-6.5 6-10 6s-7-2-10-6z"/><circle cx="8" cy="11" r="1"/>',
    "pin":     '<path d="M12 21s7-5.5 7-11a7 7 0 1 0-14 0c0 5.5 7 11 7 11z"/><circle cx="12" cy="10" r="2.5"/>',
    "rupee":   '<path d="M7 4h10M7 9h10M7 4c5 0 7 1.8 7 4.5S12 13 7 13l8 7"/>',
    "users":   '<circle cx="9" cy="8" r="3"/><path d="M3 20a6 6 0 0 1 12 0M16 5.5a3 3 0 0 1 0 5M17 20a5.8 5.8 0 0 0-2-4.2"/>',
    "school":  '<path d="M3 9l9-5 9 5-9 5-9-5z"/><path d="M7 11.5V17c0 1.4 2.2 2.5 5 2.5s5-1.1 5-2.5v-5.5"/>',
    "cart":    '<circle cx="9" cy="20" r="1.4"/><circle cx="17" cy="20" r="1.4"/><path d="M2 3h3l2.4 11.2a2 2 0 0 0 2 1.6h7.4a2 2 0 0 0 2-1.6L21 7H6"/>',
    # the smoke dot rides above the tallest stack; it is inert until the idle
    # puff loop fades it in and lifts it (see the icon-animation CSS)
    "factory": '<path d="M3 21V10l6 4V10l6 4V7l6 3v11z"/><path d="M7 21v-3M13 21v-3M18 21v-3"/>'
               '<circle class="smoke" cx="18" cy="5" r="1.15"/>',
    "trend":   '<path d="M3 17l6-6 4 4 8-8"/><path d="M15 7h6v6"/>',
    "calendar":'<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>',
    "target":  '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="4"/><circle cx="12" cy="12" r="1"/>',
    "truck":   '<path d="M3 16V6h11v10M14 9h4l3 3v4h-7"/><circle cx="7" cy="18" r="1.8"/><circle cx="17.5" cy="18" r="1.8"/>',
    "bolt":    '<path d="M13 2L4 14h7l-1 8 9-12h-7z"/>',
    "doc":     '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 13h6M9 17h4"/>',
    "alert":   '<path d="M12 4l9 16H3z"/><path d="M12 10v4M12 17.5v.5"/>',
    "gov":     '<path d="M3 10l9-6 9 6M5 10v9M19 10v9M9 19v-6M15 19v-6M3 21h18"/>',
    "gear":    '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M19.1 4.9L17 7M7 17l-2.1 2.1"/>',
    "sun":     '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M19.1 4.9l-1.4 1.4M6.3 17.7l-1.4 1.4"/>',
    "spark":   '<path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z"/>',
}

# First match wins, so the more specific words are listed first.
ICON_WORDS = [
    ("fish",    ("fish", "aqua", "shrimp", "prawn", "pond", "biofloc", "tilapia")),
    ("drop",    ("water", "irrigat", "rain", "effluent", "dye", "zld", "moisture")),
    ("leaf",    ("farm", "crop", "horticult", "agri", "organic", "natural", "soil",
                 "mango", "banana", "coconut", "cotton", "paddy", "forest")),
    ("school",  ("train", "school", "learn", "skill", "educat", "curricul", "module",
                 "demonstrat", "capacity")),
    ("users",   ("farmer", "women", "shg", "employ", "communit", "member", "visitor",
                 "tourist", "family", "families", "people", "persona")),
    ("pin",     ("village", "district", "cluster", "site", "locat", "region", "mandal",
                 "tour", "destination", "stay", "heritage")),
    ("rupee",   ("income", "revenue", "price", "cost", "invest", "fund", "credit",
                 "crore", "lakh", "subsid", "fee", "financ", "econom")),
    ("cart",    ("market", "brand", "sell", "sales", "buyer", "demand", "export",
                 "booking", "packag", "product")),
    ("factory", ("factory", "unit", "process", "manufactur", "plant", "mill",
                 "industr", "machin", "capacity build",
                 # clearly-typed clusters that otherwise fell to the generic spark
                 "textile", "apparel", "garment", "loom", "yarn", "weav", "knit",
                 "spinning", "ceramic", "pottery", "kiln", "porcelain", "coir")),
    ("trend",   ("growth", "grew", "rise", "rising", "increas", "scale", "share",
                 "trajector", "outlook", "project")),
    ("calendar",("year", "phase", "timeline", "pilot", "launch", "90-day", "roadmap",
                 "milestone", "day")),
    ("target",  ("goal", "target", "objective", "vision", "ambition", "propositio",
                 "focus", "priorit")),
    ("truck",   ("logistic", "transport", "supply", "road", "connect", "access")),
    ("bolt",    ("energy", "power", "electric", "solar", "fuel", "ethanol", "pellet")),
    ("gov",     ("government", "policy", "scheme", "department", "administrat",
                 "official", "nodal", "institut", "council", "board")),
    ("alert",   ("risk", "challenge", "constraint", "barrier", "gap", "threat",
                 "problem", "caveat", "load", "waste", "pollut")),
    ("doc",     ("report", "study", "survey", "data", "document", "plan", "sop",
                 "guideline", "registry")),
    ("gear",    ("model", "system", "operate", "mechanis", "how ", "structure",
                 "framework", "hub")),
    ("sun",     ("environment", "climate", "sustain", "green", "ecolog")),
]


def _hits(text, words):
    """Count word-START matches.

    Plain substring matching put a water drop on "ATDC support" because its body
    said "Training" and that contains "rain". Anchoring to a word boundary keeps
    the deliberate stems ("irrigat", "increas") working while killing that class
    of accident.
    """
    return sum(len(re.findall(r"\b" + re.escape(w), text)) for w in words)


def icon_for(text):
    """Deterministic keyword match, so the same heading always draws the same icon."""
    t = (text or "").lower()
    for name, words in ICON_WORDS:
        if _hits(t, words):
            return name
    return "spark"


def icon_html(text, cls="ic"):
    # the icon name rides along as a class (ic-leaf, ic-factory...) so the
    # idle-animation CSS can key a motion to what the glyph depicts
    name = icon_for(text)
    return ('<span class="' + cls + ' ic-' + name + '" aria-hidden="true"><svg viewBox="0 0 24 24">'
            '<use href="#i-' + name + '"/></svg></span>')


# pathLength normalises every shape to 100 units so one stroke-dasharray/offset
# pair draws every icon uniformly on entrance, whatever its real geometry.
_SHAPE = re.compile(r'<(path|circle|rect|line|polyline|polygon)\b')


def _sprite_shape(v):
    return _SHAPE.sub(r'<\1 pathLength="100"', v)


ICON_SPRITE = ('<svg class="sprite" aria-hidden="true"><defs>'
               + "".join('<g id="i-' + k + '">' + _sprite_shape(v) + '</g>' for k, v in ICONS.items())
               + '</defs></svg>')


# ---------------------------------------------------------------- role furniture
# The PPTX built by the deck engine signposts every slide twice: a kicker line
# above the title that says what KIND of slide this is, and a large line
# illustration that carries the same idea visually. Both are reproduced here so a
# reader moving between the .pptx and this page meets the same structure.
ROLE_KICKER = {
    "action":      "The case for action",
    "solution":    "The answer",
    "key-factors": "What made it work",
    "policy":      "Policy and institutions",
    "context":     "The bigger picture",
    "challenges":  "Risks and constraints",
    "takeaways":   "Lessons and next steps",
}

# 120x120 stroke line-art, drawn once per role and stamped faintly into the panel
# corner. Not decoration for its own sake: it is the same visual index as the
# kicker, so the role of a slide is readable before a word is.
WATERMARKS = {
    "action":      '<path d="M14 96h92M22 96V64M46 96V46M70 96V72M94 96V30"/>'
                   '<path d="M22 40h26l-9-9M22 40l9 9"/>',
    "solution":    '<circle cx="60" cy="52" r="24"/><path d="M52 76h16M54 86h12"/>'
                   '<path d="M60 12v10M28 52H18M102 52h-10M32 24l7 7M88 24l-7 7"/>',
    "key-factors": '<path d="M18 100h84M26 100V44M50 100V44M74 100V44M98 100V44"/>'
                   '<path d="M14 44h92L60 18z"/>',
    "policy":      '<path d="M16 52 60 24l44 28M26 52v44M94 52v44M44 96V64M76 96V64M12 104h96"/>',
    "context":     '<circle cx="60" cy="58" r="38"/><path d="M22 58h76M60 20c14 16 14 60 0 76'
                   'M60 20c-14 16-14 60 0 76"/>',
    "challenges":  '<path d="M60 20 104 96H16z"/><path d="M60 48v22M60 82v4"/>',
    "takeaways":   '<path d="M30 100V18M30 22h52l-12 16 12 16H30"/><path d="M30 100h60"/>',
}


def kicker_for(role):
    return ROLE_KICKER.get(role, "In this section")


def wm_html(role):
    d = WATERMARKS.get(role)
    if not d:
        return ""
    return ('<svg class="wm" viewBox="0 0 120 120" aria-hidden="true">' + d + '</svg>')


def sections_of(blocks):
    """Split the block stream into title-led sections; drop title-only stubs."""
    secs, cur = [], {"title": None, "blocks": []}
    for b in blocks:
        if b[0] == "h2":
            if cur["blocks"]:
                secs.append(cur)
            cur = {"title": b[1], "blocks": []}
        else:
            cur["blocks"].append(b)
    if cur["blocks"]:
        secs.append(cur)
    return secs


# The case-study corpus is research prose and is left exactly as written, but the
# site itself carries no em dashes. Rather than rewrite the source files, the
# dash is resolved here, at the render layer: a colon when what follows is a
# gloss that runs on with its own commas, a comma otherwise. En dashes (ranges)
# are untouched.
_DASH = re.compile(r"\s*\u2014\s*")


def dedash(t):
    """Resolve source em dashes at the render layer (the JSON keeps the dash).
    A PAIR of dashes sets off an aside and becomes parentheses ('What Drives
    (and Constrains) the Cluster'); a single dash introduces a gloss and
    becomes a colon, unless the clause already carries a colon, where a comma
    keeps a double colon impossible. A clause already ending in punctuation
    gets only a space. En dashes (ranges like 80\u201390%) are untouched, and
    no em dash ever reaches the HTML."""
    if not t or "\u2014" not in t:
        return t
    sentences = re.split(r"(?<=[.!?])\s+", t)
    out = []
    for s in sentences:
        n = s.count("\u2014")
        if n == 0:
            out.append(s)
            continue
        if n == 2:
            s = _DASH.sub(" (", s, count=1)
            s = _DASH.sub(") ", s, count=1)
            s = s.replace("( ", "(").replace(" )", ")").replace(") ,", "),")
            out.append(re.sub(r"\)\s+([.,;:])", r")\1", s))
            continue
        parts, i2 = [], 0
        for m in _DASH.finditer(s):
            parts.append(s[i2:m.start()])
            prev = "".join(parts).rstrip()
            if prev.endswith((",", ":", ";")):
                parts.append(" ")
            elif ":" in prev:
                parts.append(", ")
            else:
                parts.append(": ")
            i2 = m.end()
        parts.append(s[i2:])
        out.append("".join(parts))
    return " ".join(out)


def e(t):
    return B.e(dedash(t))


# ---------------------------------------------------------------- typed blocks
# The renderer consumes typed content JSON (scripts/deck_content/<slug>.json),
# one block per structure the source carries. Each block type below owns a
# layout built for its shape, so the flattening failures the audit catalogued
# (peer items losing their grouping, headers reading as items, stats losing
# labels, flows/tables/phases collapsed into chip walls) cannot recur.


# --- kept from the previous renderer: the SWOT matrix and bar chart primitives,
# unchanged in output, now fed from typed JSON instead of recovered from a run
# of flattened lines. ---
SWOT_QUADS = [
    ("strengths",     "Strengths",     "#9ED44A", "trend"),
    ("weaknesses",    "Weaknesses",    "#E0B25E", "gear"),
    ("opportunities", "Opportunities", "#63BFE6", "target"),
    ("threats",       "Threats",       "#E88A8A", "alert"),
]


def swot_html(caption, quads):
    cap = ('<p class="swot-cap">' + e(caption) + '</p>') if caption else ""
    cells = []
    for key, lab, col, ic, points in quads:
        lis = "".join('<li>' + e(pt) + '</li>' for pt in points)
        cells.append(
            '<div class="swot-q swot-' + key + '" style="--q:' + col + '">'
            '<div class="swot-h">'
            '<span class="swot-ic" aria-hidden="true"><svg viewBox="0 0 24 24">'
            '<use href="#i-' + ic + '"/></svg></span>'
            '<span class="swot-t">' + e(lab) + '</span></div>'
            '<ul class="swot-l">' + lis + '</ul></div>')
    return cap + '<div class="swot">' + "".join(cells) + '</div>'


def _num(v):
    """Parse a stat/series value to a float, or None if it is not a plain number."""
    t = str(v if v is not None else "").replace(",", "").strip()
    try:
        return float(t)
    except ValueError:
        return None


def chart_html(periods, vals, unit):
    """Column chart. Bars scale to the largest value; every bar prints its own
    figure, so nothing depends on reading the height."""
    top = max(vals) or 1
    cols = []
    for lab, v in zip(periods, vals):
        h = max(6.0, v / top * 100.0)
        txt = ("%.0f" % v) if v == int(v) else ("%g" % v)
        cols.append('<div class="col"><div class="colv">' + e(txt) + '</div>'
                    '<div class="colbar" style="height:' + ("%.1f" % h) + '%"></div>'
                    '<div class="coll">' + e(lab) + '</div></div>')
    cap = ('<div class="chartunit">' + e(unit) + '</div>') if unit else ""
    return '<div class="chart">' + cap + '<div class="cols">' + "".join(cols) + '</div></div>'


def grid_cols(n):
    """Columns for a peer grid, chosen so a row never leaves a single-cell hole.

    The audit's most common presentation defect was asymmetry: 4 items in a
    3-column grid (3+1 with a dead cell), a 5-stat panel split across four
    layouts. Here the count alone fixes the geometry: 4 -> 2x2, 5 -> 3+2, and
    for larger runs a width is chosen that never leaves exactly one orphan.
    """
    if n <= 3:
        return max(1, n)
    if n == 4:
        return 2
    if n in (5, 6):
        return 3
    for c in (4, 3):            # >=7: avoid a trailing row of one
        if n % c != 1:
            return c
    return 3


# ---- stats: value + full label in one tile; 2-4 big, 5+ tiled ----
def stats_html(b):
    items = b.get("items", [])
    n = len(items)
    big = 2 <= n <= 4
    cols = grid_cols(n)
    cells = []
    for it in items:
        q = ('<div class="q">' + e(it["qualifier"]) + '</div>') if it.get("qualifier") else ""
        cells.append('<div class="cell"><div class="v">' + e(it.get("value", "")) + '</div>'
                     '<div class="l">' + e(it.get("label", "")) + '</div>' + q + '</div>')
    foot = ('<p class="grid-foot">' + e(b["footnote"]) + '</p>') if b.get("footnote") else ""
    return ('<div class="grid' + (' big' if big else '') + '" style="--cols:' + str(cols) + '">'
            + "".join(cells) + '</div>' + foot)


# ---- cards: heading + body peers; iconrow for a short trio/quartet, else
# numbered/plain pillars. `n` on items keeps the source's asserted ordinals. ----
def _card_grid(items, numbered):
    cols = grid_cols(len(items))
    cells = []
    for idx, it in enumerate(items, start=1):
        title, body = it.get("title", ""), it.get("body", "")
        num = ('<span class="pnum">' + e(str(it.get("n", idx))) + '</span>') if numbered else ""
        seed = title if icon_for(title) != "spark" else (title + " " + body)
        cells.append('<div class="card">' + num + icon_html(seed)
                     + '<h3>' + e(title) + '</h3>'
                     + ('<p>' + e(body) + '</p>' if body else '') + '</div>')
    cls = "cards pillars num" if numbered else "cards"
    return '<div class="' + cls + '" style="--cols:' + str(cols) + '">' + "".join(cells) + '</div>'


def cards_html(b):
    items = b.get("items", [])
    numbered = any("n" in it for it in items)
    short = all(len(it.get("body", "")) <= 150 for it in items)
    if not numbered and len(items) in (3, 4) and short:
        # ICON ROW: a short peer set, read left to right, no implied order
        cols = grid_cols(len(items))
        cells = []
        for it in items:
            title, body = it.get("title", ""), it.get("body", "")
            seed = title if icon_for(title) != "spark" else (title + " " + body)
            cells.append('<div class="card">' + icon_html(seed, "ic xl")
                         + '<h3>' + e(title) + '</h3>'
                         + ('<p>' + e(body) + '</p>' if body else '') + '</div>')
        return ('<div class="cards iconrow" style="--cols:' + str(cols) + '">'
                + "".join(cells) + '</div>')
    return _card_grid(items, numbered)


def steps_html(b):
    """A numbered sequence / roadmap: the same pillar card, always numbered."""
    return _card_grid(b.get("items", []), True)


# ---- list: titled bullet list; items are full statements ----
def list_html(b):
    title = ('<p class="blist-title">' + e(b["title"]) + '</p>') if b.get("title") else ""
    lis = "".join('<li>' + e(x) + '</li>' for x in b.get("items", []))
    return '<div class="blist">' + title + '<ul>' + lis + '</ul></div>'


# ---- chips: short standalone phrases only ----
def chips_html(b):
    return ('<div class="chips">'
            + "".join('<div class="chip">' + icon_html(x, "ic sm") + '<span>' + e(x) + '</span></div>'
                      for x in b.get("items", []))
            + '</div>')


# ---- pairs: term + gloss definition cards ----
def pairs_html(b):
    items = b.get("items", [])
    cols = grid_cols(len(items))
    cells = []
    for it in items:
        term, desc = it.get("term", ""), it.get("desc", "")
        cells.append('<div class="card dl-card">' + icon_html(term + " " + desc)
                     + '<h3>' + e(term) + '</h3><p>' + e(desc) + '</p></div>')
    title = ('<p class="blist-title">' + e(b["title"]) + '</p>') if b.get("title") else ""
    return title + '<div class="cards deflist" style="--cols:' + str(cols) + '">' + "".join(cells) + '</div>'


# ---- callout / quote: emphasis boxes, deliberately unlike cards ----
def callout_html(b):
    label = ""
    if b.get("label"):
        label = ('<p class="callout-label">' + icon_html(b["label"], "ic sm")
                 + '<span>' + e(b["label"]) + '</span></p>')
    return '<div class="callout">' + label + '<p>' + e(b.get("text", "")) + '</p></div>'


def quote_html(b):
    attr = ('<footer class="quote-attr">' + e(b["attribution"]) + '</footer>') if b.get("attribution") else ""
    return '<blockquote class="quote"><p>' + e(b.get("text", "")) + '</p>' + attr + '</blockquote>'


# ---- flow: horizontal stage chain; arrows are CSS/SVG connectors, never chips ----
_FLOW_ARROW = ('<div class="flow-arrow" aria-hidden="true"><svg viewBox="0 0 24 24">'
               '<path d="M4 12h14M13 6l6 6-6 6"/></svg></div>')


def flow_html(b):
    stages = b.get("stages", [])
    parts = []
    for i, s in enumerate(stages):
        parts.append('<div class="flow-stage"><div class="fs-name">' + e(s.get("name", "")) + '</div>'
                     '<div class="fs-desc">' + e(s.get("desc", "")) + '</div></div>')
        if i < len(stages) - 1:
            parts.append(_FLOW_ARROW)
    closing = ('<p class="flow-closing">' + e(b["closing"]) + '</p>') if b.get("closing") else ""
    # an optional title labels the chain (BEFORE / AFTER comparisons need it);
    # reuses the bullet-list title style so labels never float as bare prose
    title = ('<p class="blist-title">' + e(b["title"]) + '</p>') if b.get("title") else ""
    return title + '<div class="flow">' + "".join(parts) + '</div>' + closing


# ---- phases: each group a labelled cluster in balanced columns ----
def phases_html(b):
    groups = b.get("groups", [])
    cols = grid_cols(len(groups))
    cells = []
    for g in groups:
        period = ('<span class="phase-period">' + e(g["period"]) + '</span>') if g.get("period") else ""
        name = ('<div class="phase-name">' + e(g["name"]) + '</div>') if g.get("name") else ""
        tasks = "".join('<li>' + e(t) + '</li>' for t in g.get("tasks", []))
        cells.append('<div class="phase"><div class="phase-head">'
                     '<span class="phase-label">' + e(g.get("label", "")) + '</span>' + period + '</div>'
                     + name + '<ul>' + tasks + '</ul></div>')
    return '<div class="phases" style="--cols:' + str(cols) + '">' + "".join(cells) + '</div>'


# ---- timeline: era / date rows on a rail ----
def timeline_html(b):
    rows = []
    for it in b.get("items", []):
        title = ('<p class="tl-title">' + e(it["title"]) + '</p>') if it.get("title") else ""
        rows.append('<div class="tl-row"><div class="tl-period">' + e(it.get("period", "")) + '</div>'
                    '<div class="tl-body">' + title
                    + '<p class="tl-desc">' + e(it.get("desc", "")) + '</p></div></div>')
    # optional block-level title, same label style as lists and flows
    head = ('<p class="blist-title">' + e(b["title"]) + '</p>') if b.get("title") else ""
    return head + '<div class="timeline">' + "".join(rows) + '</div>'


# ---- table: a real table; cells verbatim, row integrity sacred ----
def table_html(b):
    cols = b.get("cols", [])
    head = "".join('<th>' + e(str(c)) + '</th>' for c in cols)
    body = ""
    for row in b.get("rows", []):
        body += '<tr>' + "".join('<td>' + e(str(c)) + '</td>' for c in row) + '</tr>'
    foot = ('<p class="tbl-foot">' + e(b["footnote"]) + '</p>') if b.get("footnote") else ""
    return ('<div class="tbl-wrap"><table class="tbl"><thead><tr>' + head + '</tr></thead>'
            '<tbody>' + body + '</tbody></table></div>' + foot)


# ---- compare: two/three column lists, headers distinct from items ----
def compare_html(b):
    cols = b.get("cols", [])
    parts = []
    for c in cols:
        lis = "".join('<li>' + e(x) + '</li>' for x in c.get("items", []))
        parts.append('<div class="cmp-col"><div class="cmp-h">' + e(c.get("title", "")) + '</div>'
                     '<ul>' + lis + '</ul></div>')
    return '<div class="compare" style="--cols:' + str(len(cols)) + '">' + "".join(parts) + '</div>'


# ---- groups: grouped checklist, header distinct; items strings or term/desc ----
def groups_html(b):
    groups = b.get("groups", [])
    cols = grid_cols(len(groups))
    parts = []
    for g in groups:
        lis = []
        for x in g.get("items", []):
            if isinstance(x, dict):
                lis.append('<li><span class="grp-term">' + e(x.get("term", "")) + '</span> '
                           + e(x.get("desc", "")) + '</li>')
            else:
                lis.append('<li>' + e(x) + '</li>')
        parts.append('<div class="grp"><div class="grp-h">' + e(g.get("name", "")) + '</div>'
                     '<ul>' + "".join(lis) + '</ul></div>')
    return '<div class="groups" style="--cols:' + str(cols) + '">' + "".join(parts) + '</div>'


# ---- hierarchy: org tiers, level label distinct from entity + gloss ----
def hierarchy_html(b):
    rows = []
    for t in b.get("tiers", []):
        lvl = ('<div class="tier-level">' + e(t["level"]) + '</div>') if t.get("level") else ""
        rows.append('<div class="tier">' + lvl + '<div class="tier-body">'
                    '<p class="tier-name">' + e(t.get("name", "")) + '</p>'
                    '<p class="tier-desc">' + e(t.get("desc", "")) + '</p></div></div>')
    closing = ('<p class="tiers-closing">' + e(b["closing"]) + '</p>') if b.get("closing") else ""
    return '<div class="tiers">' + "".join(rows) + '</div>' + closing


# ---- fanout: one input to many component -> product branches ----
def fanout_html(b):
    branches = b.get("branches", [])
    cols = grid_cols(len(branches))
    hub = ('<div class="fan-hub"><div class="fan-input">' + icon_html(b.get("input", ""))
           + '<span>' + e(b.get("input", "")) + '</span></div></div>')
    cells = []
    for br in branches:
        prods = "".join('<li>' + e(p) + '</li>' for p in br.get("products", []))
        cells.append('<div class="fan-branch"><div class="fan-comp">' + e(br.get("component", "")) + '</div>'
                     '<ul>' + prods + '</ul></div>')
    return ('<div class="fanout">' + hub + '<div class="fan-branches" style="--cols:' + str(cols) + '">'
            + "".join(cells) + '</div></div>')


# ---- series: bar chart, drawn by the kept chart_html ----
def series_html(b):
    pts = b.get("points", [])
    periods = [p.get("label", "") for p in pts]
    vals = [(_num(p.get("value", "")) or 0.0) for p in pts]
    return chart_html(periods, vals, b.get("unit", ""))


# ---- swot: the 2x2 matrix, drawn by the kept swot_html ----
_SWOT_SRC = {"strengths": "s", "weaknesses": "w", "opportunities": "o", "threats": "t"}


def swot_block_html(b):
    quads = [(k, lab, col, ic, b.get(_SWOT_SRC[k], []))
             for (k, lab, col, ic) in SWOT_QUADS]
    return swot_html("", quads)


def p_html(b):
    return '<p>' + e(b.get("text", "")) + '</p>'


RENDERERS = {
    "p": p_html, "callout": callout_html, "quote": quote_html, "stats": stats_html,
    "cards": cards_html, "list": list_html, "chips": chips_html, "pairs": pairs_html,
    "steps": steps_html, "flow": flow_html, "phases": phases_html, "timeline": timeline_html,
    "table": table_html, "compare": compare_html, "groups": groups_html, "series": series_html,
    "swot": swot_block_html, "hierarchy": hierarchy_html, "fanout": fanout_html,
}


def render_block(b):
    fn = RENDERERS.get(b.get("type"))
    if not fn:
        raise ValueError("unknown block type: " + repr(b.get("type")))
    return fn(b)


def render_blocks(blocks):
    return "\n".join(render_block(b) for b in blocks)


# ---------------------------------------------------------------- fit engine
# A slide must never scroll: the old split counted cards and "heavy" blocks,
# which has no idea how TALL a block actually renders, so a five-stat band and a
# nine-row table both counted as "one heavy" and one of them overflowed. The
# packer below estimates each block's rendered height in pixels and fills a slide
# to a fixed budget, continuing a section onto CONT slides at block boundaries
# and, when a single block is itself taller than the panel, splitting that block
# by its own items/rows/groups.
#
# The height model is calibrated empirically: every block in all 17 decks was
# measured in the browser at the tighter of the two reference viewports
# (1280x800), and each per-type formula is a least-squares fit shifted up so the
# estimate is an UPPER BOUND of the measured height (est >= actual for every
# sampled block). Over-estimating only ever adds a CONT slide; under-estimating
# would scroll, so the model leans high on purpose. Recalibrate (scripts measure
# `.glass` content boxes and per-block offsetHeights) if the CSS metrics change.
#
# Budget geometry at 1280x800: .glass max-height is min(94vh,940px)=752px
# border-box; minus 2px border and 2x33.28px padding leaves a 683px content box
# that holds the section head plus the body. _SAFETY absorbs margin-collapse
# between blocks and real-font jitter. The wider 1440x860 viewport has a taller
# panel AND less text wrapping, so a layout that fits 1280x800 fits it too, which
# is why the model is calibrated to the smaller box.
_AVAIL = 683
_SAFETY = 22
_AUX = 34          # a block's own title/closing/footnote renders as an extra line


def _tlen(b):
    """Total characters of visible text in a block, the wrapping driver."""
    return sum(len(s) for s in block_strings(b))


def _grid_rows(n, cols):
    return max(1, math.ceil(n / max(1, cols)))


def _card_kind(b):
    """Which card layout cards_html/steps_html will pick, so the height formula
    matches the class that actually renders (iconrow, numbered pillars, plain)."""
    items = b.get("items", [])
    if b.get("type") == "steps":
        return "steps"
    numbered = any("n" in it for it in items)
    short = all(len(it.get("body", "")) <= 150 for it in items)
    if not numbered and len(items) in (3, 4) and short:
        return "iconrow"
    if numbered:
        return "steps"
    return "cards"


def est_height(b):
    """Estimated rendered footprint of one block in px (height + bottom margin).
    Coefficients are browser-calibrated upper bounds; see the fit-engine note."""
    t = b.get("type")
    tl = _tlen(b)
    if t == "p":
        return 23 + 0.268 * tl + 13
    if t == "callout":
        return 69 + 0.245 * tl + 18
    if t == "quote":
        return 21 + 0.682 * tl + 18
    if t == "chips":
        rows = math.ceil(max(1, len(b.get("items", []))) / 4)   # auto-fit ~4/row
        return rows * 48 + (rows - 1) * 10 + 18
    if t == "list":
        n = len(b.get("items", []))
        return 32 + 28.2 * n + 0.138 * tl + 18
    if t == "stats":
        items = b.get("items", [])
        n = len(items)
        rows = _grid_rows(n, grid_cols(n))
        foot = _AUX if b.get("footnote") else 0
        if 2 <= n <= 4:                                          # the big-number band
            return 6 + 116 * rows + 0.204 * tl + 20 + foot
        return 23 + 69 * rows + 0.198 * tl + 20 + foot
    if t in ("cards", "steps"):
        kind = _card_kind(b)
        n = len(b.get("items", []))
        rows = _grid_rows(n, grid_cols(n))
        if kind == "iconrow":
            return 13 + 156.5 * rows + 0.132 * tl + 20
        if kind == "steps":
            return 6 + 125.6 * rows + 0.205 * tl + 20
        return 6 + 124.1 * rows + 0.195 * tl + 20
    if t == "pairs":
        n = len(b.get("items", []))
        rows = _grid_rows(n, grid_cols(n))
        return 122.2 * rows + 0.142 * tl + 20 + (_AUX if b.get("title") else 0)
    if t == "flow":
        n = len(b.get("stages", []))
        extra = (_AUX if b.get("title") else 0) + (_AUX if b.get("closing") else 0)
        return 26 + 6.95 * n + 0.263 * tl + 6 + extra
    if t == "phases":
        return 128 + 38.8 * len(b.get("groups", [])) + 0.117 * tl + 18
    if t == "groups":
        return 194 + 27.5 * len(b.get("groups", [])) + 0.084 * tl + 18
    if t == "compare":
        # more columns read shorter (the fit's negative per-column term)
        return 201 - 14.4 * len(b.get("cols", [])) + 0.142 * tl + 18
    if t == "hierarchy":
        return 82.2 * len(b.get("tiers", [])) + 0.341 * tl + 6 + (_AUX if b.get("closing") else 0)
    if t == "timeline":
        return 20 + 46 * len(b.get("items", [])) + 0.55 * tl + 18 + (_AUX if b.get("title") else 0)
    if t == "table":
        # Length-aware rows: a cell past ~45 chars wraps to a second line at
        # mid widths (the Shenzhen quarterly dashboard measured 68px/row), so
        # flat 58/row under-budgeted exactly the tables that most need splitting
        rows_h = sum(74 if max((len(str(c)) for c in r), default=0) > 45 else 48
                     for r in b.get("rows", []))
        return 48 + rows_h + 6 + (_AUX if b.get("footnote") else 0)
    if t == "series":
        return 260                                              # fixed 210px plot + labels
    if t == "swot":
        def qh(k):
            return 74 + 24 * len(b.get(k, []))
        return max(qh("s"), qh("w")) + max(qh("o"), qh("t")) + 36
    if t == "fanout":
        br = b.get("branches", [])
        rows = _grid_rows(len(br), grid_cols(len(br)))
        maxp = max((len(x.get("products", [])) for x in br), default=0)
        return 70 + rows * (46 + 24 * maxp) + 18
    return 0.35 * tl + 60                                        # unknown: rough guess


def _sechead_h(heading, kick):
    """Section-head footprint: 64px one-line (88 with a kicker eyebrow), plus a
    line every ~60 chars when the title wraps. Matches the measured envelope."""
    base = 88 if kick else 64
    lines = max(1, math.ceil(len(heading or "") / 60))
    return base + (lines - 1) * 35


def _lead_h(text):
    return 16 + math.ceil(len(text) / 85) * 27 if text else 0


def _src_h(text):
    return 16 + math.ceil(len(text) / 100) * 22 if text else 0


# List/dict key that carries the splittable items for each block type; a type not
# here (swot, series, compare, quote, callout, p) is kept whole - splitting it
# would break the shape that is its whole point.
_SPLIT_KEY = {"cards": "items", "steps": "items", "stats": "items", "pairs": "items",
              "list": "items", "chips": "items", "timeline": "items",
              "phases": "groups", "groups": "groups", "hierarchy": "tiers",
              "flow": "stages", "fanout": "branches"}


def _split_table(b, budget):
    """Split a tall table by rows, repeating the header on each piece; the
    footnote rides the last piece. If even one row will not fit, the table is
    left whole and keeps its own internal scroll (the sanctioned exception)."""
    rows = b.get("rows", [])
    if len(rows) <= 1:
        return [b]
    room = budget - 48 - 6 - (_AUX if b.get("footnote") else 0)
    # pack rows greedily by the same length-aware cost est_height uses; a flat
    # divisor let two-line wrapped rows (long cells) overshoot the budget
    def row_h(r):
        return 74 if max((len(str(c)) for c in r), default=0) > 45 else 48
    chunks, cur, h = [], [], 0
    for r in rows:
        rh = row_h(r)
        if cur and h + rh > room:
            chunks.append(cur)
            cur, h = [], 0
        cur.append(r)
        h += rh
    if cur:
        chunks.append(cur)
    if len(chunks) <= 1:
        return [b]
    out = []
    for ch in chunks:
        sub = dict(b)
        sub["rows"] = ch
        out.append(sub)
    for idx, s in enumerate(out):                # footnote only on the final piece
        if idx < len(out) - 1:
            s.pop("footnote", None)
    return out


def _split_block(b, budget):
    """Break one oversized block into same-type pieces that each fit `budget`,
    preserving item order. Grids recompute their column count per piece (grid_cols
    runs again in the renderer) so each piece stays symmetric; the block-level
    title stays on the first piece and the closing on the last."""
    t = b.get("type")
    if t == "table":
        return _split_table(b, budget)
    key = _SPLIT_KEY.get(t)
    if not key:
        return [b]
    items = b.get(key, [])
    if len(items) <= 1:
        return [b]
    pieces, i = [], 0
    while i < len(items):
        k = 1
        while i + k < len(items):
            trial = dict(b)
            trial[key] = items[i:i + k + 1]
            if est_height(trial) > budget:
                break
            k += 1
        sub = dict(b)
        sub[key] = items[i:i + k]
        pieces.append(sub)
        i += k
    for idx, p in enumerate(pieces):
        if idx > 0:
            p.pop("title", None)                 # title leads the first piece only
        if idx < len(pieces) - 1:
            p.pop("closing", None)               # closing tails the last piece only
    return pieces


_ORPHAN_SMALL = 190          # a lone block under this reads as a widow on a CONT slide


def _budget_at(i, P, avail0, availc, src_h):
    """Room for page i of P: page 0 shares with the lead, the last page with the
    source line, every page after the first repeats the (same-height) head."""
    b = avail0 if i == 0 else availc
    if i == P - 1:
        b -= src_h
    return b


def _minmax_partition(hs, budgets):
    """Cut the atom heights `hs` into len(budgets) contiguous pages, each within
    its budget, minimising the fullest page's FILL RATIO. Balancing on the ratio
    (not the raw height) shares the load evenly even though page 0 has less room,
    so a section never ends on one packed slide plus a near-empty tail. Returns
    the (start, end) spans or None when no split keeps every page within budget."""
    n, P = len(hs), len(budgets)
    INF = float("inf")
    dp = [[INF] * (P + 1) for _ in range(n + 1)]
    cut = [[None] * (P + 1) for _ in range(n + 1)]
    dp[0][0] = 0.0
    for p in range(1, P + 1):
        for i in range(p, n + 1):
            s = 0.0
            for j in range(i - 1, p - 2, -1):    # last group = atoms[j:i]
                s += hs[j]
                if s > budgets[p - 1]:
                    break
                val = max(dp[j][p - 1], s / budgets[p - 1])
                if val < dp[i][p]:
                    dp[i][p] = val
                    cut[i][p] = j
    if dp[n][P] == INF:
        return None
    groups, i, p = [], n, P
    while p > 0:
        j = cut[i][p]
        groups.append((j, i))
        i, p = j, p - 1
    groups.reverse()
    return groups


def _partition(atoms, avail0, availc, src_h):
    """Fewest pages that hold `atoms`, balanced by fill ratio. Grows the page
    count only until a feasible balanced cut exists; falls back to one block per
    page (and, last resort, drops the source reservation) if a tail block is too
    tall to share its page with the source line."""
    hs = [est_height(a) for a in atoms]
    for P in range(1, len(atoms) + 1):
        g = _minmax_partition(hs, [_budget_at(i, P, avail0, availc, src_h) for i in range(P)])
        if g:
            return g
    # a final atom too tall to sit with the source: let the source ride anyway
    # (the browser safety net absorbs the few px), rather than invent a blank page
    for P in range(1, len(atoms) + 1):
        g = _minmax_partition(hs, [_budget_at(i, P, avail0, availc, 0) for i in range(P)])
        if g:
            return g
    return [(i, i + 1) for i in range(len(atoms))]


def pack_section(sec):
    """Pack one section's blocks into slide-sized pages by estimated height.
    Page 0 also carries the lead; the last page carries the source line; every
    page repeats the section head (as a CONT slide after the first). Returns a
    list of block lists, one per slide, in reading order.

    The packer (1) pre-splits any block taller than a panel, (2) balances the
    blocks across the fewest pages by fill ratio, then (3) cures a leftover widow
    (a CONT slide holding one small block) by splitting the section's largest
    splittable block so the balancer has finer pieces to even out."""
    blocks = sec.get("blocks", [])
    heading = sec_heading(sec)
    kick = bool(sec.get("kicker") and sec.get("title"))
    sh = _sechead_h(heading, kick)               # a CONT head is the same height
    lead_h = _lead_h(sec.get("lead") or "")
    src_h = _src_h(sec.get("source") or "")
    avail0 = _AVAIL - sh - lead_h - _SAFETY       # first page shares room with the lead
    availc = _AVAIL - sh - _SAFETY                # a continuation page

    # 1. pre-split any block too tall for even a continuation page
    atoms = []
    for b in blocks:
        if est_height(b) > availc:
            atoms.extend(_split_block(b, availc))
        else:
            atoms.append(b)
    if not atoms:
        return [[]]

    # 2. balance across the fewest pages, then 3. break a widow if splitting a
    #    block lets the balancer fill the tail. Bounded so it always terminates.
    for _ in range(5):
        groups = _partition(atoms, avail0, availc, src_h)
        pages = [atoms[a:b] for (a, b) in groups]
        widow = (len(pages) > 1 and len(pages[-1]) == 1
                 and est_height(pages[-1][0]) < _ORPHAN_SMALL)
        if not widow:
            break
        # split the tallest splittable atom into halves so the tail can fill out
        cand = [(est_height(a), k) for k, a in enumerate(atoms)
                if a.get("type") in _SPLIT_KEY and len(a.get(_SPLIT_KEY[a["type"]], [])) > 1]
        if not cand:
            break
        _, k = max(cand)
        halves = _split_block(atoms[k], est_height(atoms[k]) * 0.55)
        if len(halves) < 2:
            break
        atoms[k:k + 1] = halves
    return pages


def sec_text(sec):
    """All human-readable strings in a section, for role/icon inference."""
    out = [sec.get("title") or "", sec.get("kicker") or "", sec.get("lead") or ""]
    for b in sec.get("blocks", []):
        out.extend(block_strings(b))
    return " ".join(x for x in out if x)


def sec_heading(sec):
    """The section's visible headline: its title, or its kicker when title-only
    sections (e.g. Morbi's ALL-CAPS banners) carry the heading in the kicker.
    A source's own manual numbering ('1. Why this matters...') is stripped:
    the deck stamps section numbers itself, and keeping both left every badge
    one off from the embedded number."""
    t = sec.get("title") or sec.get("kicker") or "Overview"
    return re.sub(r"^\d+\.\s+", "", t)


def section_head(idx, sec, cont=False):
    heading = sec_heading(sec)
    # A kicker eyebrow is shown only when the author supplied BOTH a kicker and a
    # distinct title; no role-derived eyebrows are fabricated, so the duplicated
    # "The bigger picture" labels the audit flagged cannot appear.
    kick = ""
    if sec.get("kicker") and sec.get("title"):
        kick = '<p class="kick">' + e(sec["kicker"]) + '</p>'
    cont_mark = ' <span class="cont">CONT.</span>' if cont else ""
    return ('<div class="sechead r"><span class="secnum">' + ("%02d" % idx) + '</span>'
            + icon_html(heading, "ic lg")
            + '<div class="sectext">' + kick
            + '<h2>' + e(heading) + cont_mark + '</h2></div></div>')


def slides_html(content, m):
    sections = content.get("sections", [])
    roles = [role_for(sec_heading(s), sec_text(s)) for s in sections]
    titles = [sec_heading(s) for s in sections]

    title = content.get("title") or m.get("title", "")
    eyebrow = content.get("eyebrow") or m.get("eyebrow", "")
    subtitle = content.get("subtitle") or m.get("summary", "")

    slides = []

    # ---- cover ----
    tags = []
    if m.get("place"):
        tags.append('<span class="tag place">' + e(m["place"]) + '</span>')
    if m.get("theme"):
        tags.append('<span class="tag">' + e(m["theme"]) + '</span>')
    tags.append('<span class="tag">'
                + ("Andhra Pradesh district" if m.get("group") == "ap" else "Replicable model")
                + '</span>')
    hero = content.get("hero_stats") or []
    herohtml = ""
    if hero:
        cells = "".join('<div class="scell"><div class="v">' + e(h.get("value", "")) + '</div>'
                        '<div class="l">' + e(h.get("label", "")) + '</div></div>' for h in hero)
        herohtml = '<div class="hero">' + cells + '</div>'
    aud = ('<p class="cover-aud r">' + e(content["audience"]) + '</p>') if content.get("audience") else ""
    slides.append(
        '<section class="slide cover" data-i="0">'
        '<div class="media" data-media="0" data-role="cover"></div>'
        '<div class="glass cover-glass reveal-root' + (' has-hero' if herohtml else '') + '">'
        '<div class="cover-l">'
        '<p class="eyebrow r">' + e(eyebrow) + '</p>'
        '<h1 class="r">' + e(title) + '</h1>'
        '<p class="summary r">' + e(subtitle) + '</p>'
        '<div class="meta r">' + "".join(tags) + '</div>' + aud +
        '</div>' +
        # no hero stats: skip the right column entirely so the desktop grid
        # does not strand a blank panel beside the title
        ('<div class="cover-r r">' + herohtml + '</div>' if herohtml else '') +
        '<p class="hint r">Use ← → or the arrows to move through the story</p>'
        '</div></section>')

    # ---- agenda: one entry per section, sequential numbers, no duplicates,
    # built straight off the section headings so it can never drift ----
    items = "".join(
        '<li class="ag-i" style="--i:' + str(i) + '"><span class="ag-n">' + ("%02d" % i) + '</span>'
        + icon_html(t, "ic")
        + '<span class="ag-t">' + e(t) + '</span></li>'
        for i, t in enumerate(titles, start=1))
    slides.append(
        '<section class="slide" data-i="1">'
        '<div class="media" data-media="0" data-role="context"></div>'
        '<div class="glass reveal-root">'
        + wm_html("context") +
        '<div class="sechead r"><span class="secnum">Contents</span>'
        + icon_html("plan document", "ic lg")
        + '<h2>What this story covers</h2></div>'
        '<ul class="agenda r">' + items + '</ul>'
        '</div></section>')

    # ---- section slides (one section = one slide; overflow continues with CONT.) ----
    di = 2
    for idx, (sec, role) in enumerate(zip(sections, roles), start=1):
        pages = pack_section(sec)
        for pi, page in enumerate(pages):
            lead = ('<p class="seclead">' + e(sec["lead"]) + '</p>') if (pi == 0 and sec.get("lead")) else ""
            src = ('<p class="secsrc">' + e(sec["source"]) + '</p>') if (pi == len(pages) - 1 and sec.get("source")) else ""
            slides.append(
                '<section class="slide" data-i="' + str(di) + '">'
                '<div class="media" data-media="' + str(idx) + '" data-role="' + role + '"></div>'
                '<div class="glass reveal-root">'
                + wm_html(role)
                + section_head(idx, sec, cont=(pi > 0))
                + '<div class="secbody r">' + lead + render_blocks(page) + src + '</div>'
                '</div></section>')
            di += 1

    # ---- closing plate ----
    src_line = content.get("source_note") or m.get("source")
    src = ('<p class="cl-src r">' + e(src_line) + '</p>') if src_line else ""
    slides.append(
        '<section class="slide closing" data-i="' + str(di) + '">'
        '<div class="media" data-media="' + str(len(sections) + 1) + '" data-role="takeaways"></div>'
        '<div class="glass cl-glass reveal-root">'
        + wm_html("takeaways") +
        '<p class="eyebrow r">End of the story</p>'
        '<h2 class="cl-h r">' + e(title) + '</h2>'
        '<p class="summary r">' + e(subtitle) + '</p>'
        + src +
        '<div class="cl-foot r"><span>Pahlé India Foundation</span>'
        '<span class="cl-dot">·</span><span>Swarna Andhra @2047</span></div>'
        '<a class="cl-cta r" href="../index.html#districts">Back to the case library</a>'
        '</div></section>')
    return slides


TMPL = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%%TITLE%% · Swarna Andhra case study</title>
<script>
(function(){try{var ok=!matchMedia('(prefers-reduced-motion: reduce)').matches&&'IntersectionObserver' in window;if(ok)document.documentElement.className+=' anim';}catch(e){}})();
</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Public+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{
  --ink:#06140F;--fg:#EEF5EF;--mut:rgba(238,245,239,.74);--mut2:rgba(238,245,239,.5);
  --t1:%%TINT1%%;--t2:%%TINT2%%;
  --glass:rgba(8,22,16,.52);--glass2:rgba(8,22,16,.34);--line:rgba(255,255,255,.16);
}
*{box-sizing:border-box;}
html,body{margin:0;height:100%;}
body{background:var(--ink);color:var(--fg);overflow:hidden;
  font-family:'Public Sans',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  line-height:1.6;-webkit-font-smoothing:antialiased;}
a{color:var(--t2);}

/* ---------- horizontal deck ---------- */
.stage{position:fixed;inset:0;overflow:hidden;}
.track{display:flex;height:100%;width:100%;
  transition:transform .72s cubic-bezier(.76,0,.24,1);will-change:transform;}
.slide{position:relative;flex:0 0 100%;height:100%;overflow:hidden;
  display:flex;align-items:center;justify-content:center;
  padding:clamp(10px,1.6vw,20px) clamp(16px,5.5vw,88px);}

/* full-bleed background: animated mesh, tinted; photo/video overlays it if present */
.media{position:absolute;inset:0;z-index:0;
  /* The tint used to sit at 42%/34% of the theme hue. For the agri cases that hue
     is #6FA817 - a yellow-green - so the whole stage read olive rather than the
     site's deep forest green. Dropped to a whisper: enough to tell the themes
     apart, not enough to cast. The deep-green base now dominates. */
  background:
    radial-gradient(62% 72% at 18% 22%, color-mix(in srgb, var(--t1) 13%, transparent), transparent 72%),
    radial-gradient(58% 66% at 82% 78%, color-mix(in srgb, var(--t2) 9%, transparent), transparent 72%),
    radial-gradient(95% 95% at 50% 45%, #0B241B, #050F0B 78%);
  background-size:180% 180%,180% 180%,100% 100%;
  animation:drift 26s ease-in-out infinite alternate;}
@keyframes drift{
  0%{background-position:0% 0%,100% 100%,50% 50%;}
  100%{background-position:60% 40%,40% 60%,50% 50%;}}
.media::after{content:"";position:absolute;inset:0;
  background:radial-gradient(120% 80% at 50% 120%, rgba(0,0,0,.5), transparent 60%);}
.media img,.media video{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;
  opacity:0;transition:opacity .8s ease;}
/* Pixel-art assets opt in per-file via a .pixel class; cinematic footage must NOT
   be nearest-neighbour scaled or it aliases badly. */
.media.pixel img,.media.pixel video{image-rendering:pixelated;}
.media.has-asset img,.media.has-asset video{opacity:1;}
.media.has-asset::before{content:"";position:absolute;inset:0;z-index:1;
  background:linear-gradient(180deg, rgba(4,12,9,.35), rgba(4,12,9,.68));}

/* ---------- glass panel ---------- */
.glass{position:relative;z-index:2;width:min(1500px,100%);
  height:auto;max-height:min(94vh,940px);overflow:auto;
  background:var(--glass);
  -webkit-backdrop-filter:blur(30px) saturate(1.3);backdrop-filter:blur(30px) saturate(1.3);
  border:1px solid var(--line);border-radius:24px;
  padding:clamp(22px,2.6vw,40px);
  box-shadow:0 30px 80px -30px rgba(0,0,0,.7), inset 0 1px 0 rgba(255,255,255,.08);
  scrollbar-width:thin;scrollbar-color:var(--t2) transparent;}
.glass::-webkit-scrollbar{width:8px;}
.glass::-webkit-scrollbar-thumb{background:color-mix(in srgb,var(--t2) 50%,transparent);border-radius:8px;}
.cover-glass{width:min(1500px,100%);}
/* cover content sits centred in the same fixed box rather than hugging the top */
.cover-glass{display:flex;flex-direction:column;justify-content:center;}
/* At the widened panel size a single centred column stranded the whole right
   half. Split it: identity left, the hero figures as a column on the right.
   Collapses back to one column below 900px, where the stack is correct. */
@media (min-width:900px){
  .cover-glass.has-hero{display:grid;grid-template-columns:1.35fr .85fr;
    align-items:center;align-content:center;gap:clamp(28px,4vw,64px);}
  .cover-glass .cover-l,.cover-glass .cover-r{min-width:0;}
  .cover-glass .cover-r .hero{grid-template-columns:1fr;margin:0;}
  .cover-glass .cover-r .scell{padding:18px 20px 16px;}
  .cover-glass .hint{grid-column:1/-1;margin:4px 0 0;}
}

.eyebrow{font-size:12px;font-weight:700;letter-spacing:.11em;text-transform:uppercase;
  color:var(--t2);margin:0 0 16px;}
h1{font-family:'Trebuchet MS','Verdana Pro',Verdana,sans-serif;font-weight:600;font-size:clamp(30px,5.2vw,52px);
  line-height:1.05;letter-spacing:-.01em;margin:0 0 18px;}
.summary{font-size:clamp(16px,2vw,20px);color:var(--mut);margin:0 0 22px;max-width:60ch;}
.meta{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 20px;}
.tag{font-size:12px;font-weight:600;padding:6px 12px;border-radius:999px;
  background:var(--glass2);border:1px solid var(--line);color:var(--mut);}
.tag.place{color:var(--fg);}
.hint{font-size:12.5px;color:var(--mut2);margin:22px 0 0;letter-spacing:.02em;}

.sechead{display:flex;align-items:center;gap:14px;margin:0 0 20px;
  padding-bottom:14px;border-bottom:1px solid var(--line);position:relative;}
/* the accent rule the methodology deck puts under every action title */
.sechead::after{content:"";position:absolute;left:0;bottom:-1px;width:64px;height:3px;
  border-radius:3px;background:linear-gradient(90deg,var(--t2),transparent);}
.sechead h2 .cont{font-size:.5em;font-weight:600;letter-spacing:.08em;
  text-transform:uppercase;color:var(--mut2);vertical-align:middle;margin-left:6px;}
.secnum{font-family:'Trebuchet MS','Verdana Pro',Verdana,sans-serif;font-weight:700;font-size:13px;
  color:var(--t2);letter-spacing:.1em;flex:0 0 auto;
  padding:3px 12px;border-radius:999px;
  border:1px solid color-mix(in srgb,var(--t2) 45%,transparent);
  background:color-mix(in srgb,var(--t2) 12%,transparent);}
.sechead h2{font-family:'Trebuchet MS','Verdana Pro',Verdana,sans-serif;font-weight:600;
  font-size:clamp(22px,3.2vw,32px);letter-spacing:-.01em;color:#fff;margin:0;line-height:1.1;}
.secbody{counter-reset:cardno;}
.secbody h3{font-family:'Public Sans',sans-serif;font-weight:700;font-size:clamp(16px,2vw,20px);
  color:#fff;margin:22px 0 6px;}
.secbody h3:first-child{margin-top:0;}
.secbody p{margin:0 0 13px;color:var(--mut);max-width:78ch;}
.secbody .k{margin:16px 0 4px;font-weight:700;font-size:13.5px;color:var(--t2);letter-spacing:.02em;}

/* hero + stat grids as inner glass chips */
.hero,.grid{display:grid;gap:12px;margin:18px 0 4px;
  grid-template-columns:repeat(auto-fit,minmax(140px,1fr));}
.grid{margin:14px 0 20px;}
.scell,.cell{background:var(--glass2);border:1px solid var(--line);border-radius:14px;
  padding:15px 16px 13px;transition:transform .26s cubic-bezier(.2,.7,.2,1),border-color .26s ease;}
.scell:hover,.cell:hover{transform:translateY(-3px);border-color:color-mix(in srgb,var(--t2) 50%,var(--line));}
.scell .v,.cell .v{font-family:'Trebuchet MS','Verdana Pro',Verdana,sans-serif;font-weight:600;
  font-size:clamp(22px,3vw,30px);line-height:1;color:var(--t2);}
.scell .l,.cell .l{margin-top:7px;font-size:13px;line-height:1.4;color:var(--mut);font-weight:600;}

/* icons: inline sprite, tinted by the slide accent, in a soft disc so they read
   against both the mesh gradient and a photo background */
/* The sprite is visually hidden but NOT display:none: a display:none subtree runs
   no CSS animations, and the factory smoke dot lives here and must keep puffing
   for every <use> clone to reflect it. Zero-boxed and clipped, it paints nothing
   itself. */
.sprite{position:absolute;width:0;height:0;overflow:hidden;}
.ic{flex:0 0 auto;display:inline-grid;place-items:center;width:30px;height:30px;
  border-radius:9px;background:color-mix(in srgb,var(--t2) 15%,transparent);
  border:1px solid color-mix(in srgb,var(--t2) 28%,transparent);color:var(--t2);}
.ic svg{width:17px;height:17px;fill:none;stroke:currentColor;stroke-width:1.7;
  stroke-linecap:round;stroke-linejoin:round;}
.ic.sm{width:22px;height:22px;border-radius:7px;}
.ic.sm svg{width:13px;height:13px;}
.ic.lg{width:38px;height:38px;border-radius:11px;}
.ic.lg svg{width:21px;height:21px;}
.card>.ic{margin-bottom:10px;}
.chip{display:flex;align-items:center;gap:10px;}

/* card grid - peer sub-sections, from the deck template's SWOT/objectives layout */
.cards{display:grid;gap:14px;margin:18px 0 20px;
  grid-template-columns:repeat(auto-fit,minmax(280px,1fr));}
.card{position:relative;background:var(--glass2);border:1px solid var(--line);
  border-radius:16px;padding:18px 20px 16px;
  transition:transform .26s cubic-bezier(.2,.7,.2,1),border-color .26s ease;}
.card:hover{transform:translateY(-3px);border-color:color-mix(in srgb,var(--t2) 50%,var(--line));}
.card::before{counter-increment:cardno;content:counter(cardno,decimal-leading-zero);
  position:absolute;top:18px;right:18px;
  font-family:'Trebuchet MS','Verdana Pro',Verdana,sans-serif;font-weight:600;font-size:13px;
  color:var(--t2);letter-spacing:.04em;display:block;margin-bottom:8px;}
/* .secbody h3 carries list spacing; inside a card it is the card's own title */
.card h3{margin:0 0 8px;font-size:clamp(15px,1.5vw,17.5px);line-height:1.3;}
.card p{margin:0 0 8px;font-size:14.5px;line-height:1.55;max-width:none;}
.card p:last-child{margin-bottom:0;}

/* chips - the parser's leftover emphasis lines, laid out as peers not a column */
.chips{display:grid;gap:10px;margin:14px 0 18px;
  grid-template-columns:repeat(auto-fit,minmax(220px,1fr));}
.chip>.ic{flex:0 0 auto;}
.chip{background:var(--glass2);border:1px solid var(--line);border-left:3px solid var(--t2);
  border-radius:10px;padding:12px 15px;font-size:14px;font-weight:600;
  color:var(--fg);line-height:1.45;}

/* column chart, recovered from a flattened value/period table */
.chart{margin:18px 0 22px;}
.chartunit{font-size:12px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;
  color:var(--mut2);margin:0 0 12px;}
.cols{display:grid;grid-auto-flow:column;grid-auto-columns:1fr;gap:clamp(8px,1.2vw,18px);
  align-items:end;min-height:210px;padding-bottom:2px;
  border-bottom:1px solid var(--line);}
.col{display:flex;flex-direction:column;justify-content:flex-end;align-items:center;
  height:100%;gap:8px;min-width:0;}
.colv{font-weight:700;font-size:13px;color:var(--fg);font-variant-numeric:tabular-nums;
  white-space:nowrap;}
.colbar{width:100%;max-width:64px;border-radius:7px 7px 2px 2px;
  background:linear-gradient(180deg,var(--t2),color-mix(in srgb,var(--t1) 70%,transparent));
  border:1px solid color-mix(in srgb,var(--t2) 45%,transparent);border-bottom:none;
  transition:filter .25s ease;}
.col:hover .colbar{filter:brightness(1.18);}
.coll{font-size:11.5px;color:var(--mut);white-space:nowrap;margin-top:2px;}
@media (max-width:900px){ .coll{font-size:10px;writing-mode:vertical-rl;} }

/* milestone band - the deck template's timeline layout. The rail is drawn on the
   row rather than per cell so it reads as one continuous sequence. */
.steps{position:relative;display:grid;gap:18px;margin:20px 0 22px;
  grid-template-columns:repeat(auto-fit,minmax(190px,1fr));}
.step{position:relative;padding-top:66px;}
.step::after{content:"";position:absolute;left:0;right:-18px;top:6px;height:1px;
  background:var(--line);}
.step:last-child::after{right:0;
  background:linear-gradient(90deg,var(--line),transparent);}
.step::before{content:"";position:absolute;left:0;top:1px;width:11px;height:11px;
  border-radius:50%;background:var(--t2);box-shadow:0 0 0 4px var(--ink);}
.step-v{position:absolute;top:26px;left:0;font-weight:700;font-size:clamp(20px,2.6vw,27px);
  line-height:1;color:var(--t2);letter-spacing:-.01em;}
.step-b p{margin:0 0 7px;font-size:14px;line-height:1.55;color:var(--mut);max-width:none;}
.step-b p:last-child{margin-bottom:0;}

/* a lone milestone is not a sequence: figure beside its text, not a band across
   the slide with an orphan line under it */
.statnote{display:grid;grid-template-columns:minmax(120px,190px) 1fr;gap:clamp(18px,2.4vw,34px);
  align-items:start;background:var(--glass2);border:1px solid var(--line);
  border-radius:16px;padding:20px 22px;margin:18px 0 20px;}
.statnote-v{font-weight:700;font-size:clamp(30px,4.4vw,52px);line-height:.95;
  color:var(--t2);letter-spacing:-.02em;}
.statnote-b p{margin:0 0 9px;font-size:14.5px;line-height:1.6;color:var(--mut);max-width:70ch;}
.statnote-b p:last-child{margin-bottom:0;}
@media (max-width:700px){ .statnote{grid-template-columns:1fr;gap:10px;} }

/* timeline entry */
.entry{display:grid;grid-template-columns:minmax(90px,124px) 1fr;gap:16px;
  padding:14px 0;border-top:1px solid var(--line);}
.entry:first-of-type{border-top:none;}
.entry.noterm{grid-template-columns:1fr;}
.entry.noterm .term{display:none;}
.entry .term{font-weight:700;font-size:13px;color:var(--t2);}
.entry .eh{font-weight:700;font-size:15px;color:#fff;margin:0 0 5px;}
.entry .eb{margin:0;font-size:14.5px;color:var(--mut);line-height:1.55;}

/* ---------- chrome: arrows, dots, progress, back ---------- */
.nav{position:fixed;top:50%;transform:translateY(-50%);z-index:30;
  width:52px;height:52px;border-radius:50%;display:grid;place-items:center;cursor:pointer;
  background:var(--glass);border:1px solid var(--line);color:var(--fg);
  font:inherit;padding:0;margin:0;appearance:none;-webkit-appearance:none;
  -webkit-backdrop-filter:blur(14px);backdrop-filter:blur(14px);
  transition:transform .2s ease,background .2s ease,opacity .2s ease,box-shadow .25s ease;user-select:none;}
.nav:focus-visible{outline:2px solid var(--lime);outline-offset:2px;}
.nav:hover{background:color-mix(in srgb,var(--t1) 30%,var(--glass));transform:translateY(-50%) scale(1.07);}
.nav.prev{left:clamp(12px,2.5vw,30px);}
.nav.next{right:clamp(12px,2.5vw,30px);}
.nav[disabled]{opacity:.3;pointer-events:none;}
.nav svg{width:20px;height:20px;}
/* Glow + directional pulse. With wheel paging removed the arrows carry the whole
   "which way now" job, so they are made unmissable: an enabled arrow wears a soft
   lime halo, the suggested arrow (.nudge, set per slide by the deck JS) breathes
   and its chevron leans toward the direction of travel. Disabled arrows stay dim. */
.nav:not([disabled]){color:var(--lime);border-color:rgba(198,236,143,.5);
  box-shadow:0 0 0 1px rgba(198,236,143,.2),0 0 18px rgba(198,255,106,.24);}
.nav:not([disabled]):hover{
  box-shadow:0 0 0 1px rgba(198,236,143,.5),0 0 28px rgba(198,255,106,.55);}
.nav svg{transition:transform .2s ease;}
@keyframes navGlow{0%,100%{box-shadow:0 0 0 1px rgba(198,236,143,.2),0 0 15px rgba(198,255,106,.22);}
  50%{box-shadow:0 0 0 1px rgba(198,236,143,.6),0 0 32px rgba(198,255,106,.6);}}
@keyframes navNudgeR{0%,100%{transform:translateX(0);}50%{transform:translateX(3px);}}
@keyframes navNudgeL{0%,100%{transform:translateX(0);}50%{transform:translateX(-3px);}}
.nav.nudge{animation:navGlow 1.9s ease-in-out infinite;}
.nav.next.nudge svg{animation:navNudgeR 1.9s ease-in-out infinite;}
.nav.prev.nudge svg{animation:navNudgeL 1.9s ease-in-out infinite;}
@media (prefers-reduced-motion:reduce){
  /* Match the pulse rules' specificity (.nav.next.nudge svg is 0,3,1) so these
     overrides win inside the query rather than being outranked. */
  .nav.nudge{animation:none;}
  .nav.next.nudge svg,.nav.prev.nudge svg{animation:none;}
}
.dots{position:fixed;left:50%;bottom:26px;transform:translateX(-50%);z-index:30;
  display:flex;gap:10px;align-items:center;
  background:var(--glass);border:1px solid var(--line);border-radius:999px;padding:9px 14px;
  -webkit-backdrop-filter:blur(14px);backdrop-filter:blur(14px);}
.dot{width:8px;height:8px;border-radius:50%;background:rgba(255,255,255,.28);cursor:pointer;
  transition:all .3s ease;}
.dot.on{width:26px;border-radius:6px;background:linear-gradient(90deg,var(--t1),var(--t2));}
.count{position:fixed;top:22px;right:clamp(16px,3vw,30px);z-index:30;font-size:13px;
  color:var(--mut);font-variant-numeric:tabular-nums;}
.count b{color:var(--fg);font-family:'Trebuchet MS','Verdana Pro',Verdana,sans-serif;font-size:17px;}
.back{position:fixed;top:20px;left:clamp(16px,3vw,30px);z-index:30;
  display:inline-flex;align-items:center;gap:7px;font-size:13px;font-weight:600;
  color:var(--mut);text-decoration:none;background:var(--glass);border:1px solid var(--line);
  padding:8px 13px;border-radius:999px;-webkit-backdrop-filter:blur(14px);backdrop-filter:blur(14px);
  transition:gap .2s ease,color .2s ease;}
.back:hover{gap:11px;color:var(--fg);}

/* entrance reveals (gsap sets these when .anim survives the rAF probe) */
.anim .slide.active .r{opacity:0;}

/* Staggered pop-in for the repeating units, the rhythm the methodology deck
   uses: each card/chip/step/figure arrives just after the one before it, so a
   slide assembles rather than appearing whole. CSS only, so it runs with or
   without the script layer, and it is disabled on the stacked mobile layout
   and under reduced motion with everything left visible. */
@keyframes cdPop{from{opacity:0;transform:translateY(10px) scale(.985);}
  to{opacity:1;transform:none;}}
/* Gated on .anim, the class the page only sets when rAF and IntersectionObserver
   are both alive and motion is allowed. Without it nothing is hidden at rest, so
   a frozen or throttled animation timeline can never leave a slide blank - the
   same guarantee the .r reveals above are built on. */
@media (min-width:761px) and (prefers-reduced-motion:no-preference){
  .anim .slide .card,.anim .slide .chip,.anim .slide .step,.anim .slide .scell,
  .anim .slide .cell,.anim .slide .entry,.anim .slide .statnote,.anim .slide .col,
  .anim .slide .ag-i{opacity:0;}
  .anim .slide.active .card,.anim .slide.active .chip,.anim .slide.active .step,
  .anim .slide.active .scell,.anim .slide.active .cell,.anim .slide.active .entry,
  .anim .slide.active .statnote,.anim .slide.active .col,.anim .slide.active .ag-i{
    animation:cdPop .5s cubic-bezier(.2,.8,.3,1) forwards;}
  .anim .slide.active .card:nth-child(n),.anim .slide.active .chip:nth-child(n),
  .anim .slide.active .step:nth-child(n),.anim .slide.active .scell:nth-child(n),
  .anim .slide.active .cell:nth-child(n),.anim .slide.active .entry:nth-child(n),
  .anim .slide.active .col:nth-child(n){animation-delay:.12s;}
  .anim .slide.active .card:nth-child(2),.anim .slide.active .chip:nth-child(2),
  .anim .slide.active .step:nth-child(2),.anim .slide.active .scell:nth-child(2),
  .anim .slide.active .cell:nth-child(2),.anim .slide.active .entry:nth-child(2),
  .anim .slide.active .col:nth-child(2){animation-delay:.22s;}
  .anim .slide.active .card:nth-child(3),.anim .slide.active .chip:nth-child(3),
  .anim .slide.active .step:nth-child(3),.anim .slide.active .scell:nth-child(3),
  .anim .slide.active .cell:nth-child(3),.anim .slide.active .entry:nth-child(3),
  .anim .slide.active .col:nth-child(3){animation-delay:.32s;}
  .anim .slide.active .card:nth-child(4),.anim .slide.active .chip:nth-child(4),
  .anim .slide.active .step:nth-child(4),.anim .slide.active .scell:nth-child(4),
  .anim .slide.active .cell:nth-child(4),.anim .slide.active .entry:nth-child(4),
  .anim .slide.active .col:nth-child(4){animation-delay:.42s;}
  .anim .slide.active .card:nth-child(n+5),.anim .slide.active .chip:nth-child(n+5),
  .anim .slide.active .step:nth-child(n+5),.anim .slide.active .scell:nth-child(n+5),
  .anim .slide.active .cell:nth-child(n+5),.anim .slide.active .entry:nth-child(n+5),
  .anim .slide.active .col:nth-child(n+5){animation-delay:.52s;}
  /* the column chart grows from its baseline instead of sliding */
  .anim .slide.active .colbar{transform-origin:bottom;animation:cdGrow .55s cubic-bezier(.2,.8,.3,1) .3s both;}
}
@keyframes cdGrow{from{transform:scaleY(0);}to{transform:scaleY(1);}}
@media (max-width:760px),(prefers-reduced-motion:reduce){
  .slide .card,.slide .chip,.slide .step,.slide .scell,
  .slide .cell,.slide .entry,.slide .statnote,.slide .col,
  .slide .ag-i{opacity:1!important;}
  .slide .colbar{animation:none!important;transform:none!important;}
}

/* ================= METHODOLOGY SKIN =================
   Same soul as the methodology deck on the dashboard: one lime accent for all
   the furniture (slide-number pill, title rule, card heads, numbered badges,
   icons), the same glass recipe on the panel, and the same staggered pop-in for
   the repeating units. The per-case tint stays where it belongs - in the
   background mesh and the chart bars - so a case still reads as its own theme
   without every deck inventing its own accent colour. Declared last on purpose:
   it overrides the base rules above rather than editing each of them. */
:root{--lime:#C6EC8F;--lime-hot:#C6FF6A;}

.glass{border-radius:18px;border:1px solid rgba(255,255,255,.16);
  background:linear-gradient(180deg,rgba(9,26,19,.36),rgba(6,18,13,.46));
  -webkit-backdrop-filter:blur(26px) saturate(150%);backdrop-filter:blur(26px) saturate(150%);
  clip-path:inset(0 round 18px);isolation:isolate;
  scrollbar-color:rgba(198,236,143,.4) transparent;}
.glass::-webkit-scrollbar-thumb{background:rgba(198,236,143,.4);}

/* the slide-role watermark: the same idea the methodology deck carries as a
   figure, reduced to a quiet index mark so it never competes with the text */
.wm{position:absolute;right:clamp(14px,2.2vw,34px);bottom:clamp(14px,2.2vh,30px);
  width:clamp(120px,15vw,210px);height:auto;z-index:0;pointer-events:none;
  fill:none;stroke:var(--lime);stroke-width:1.6;stroke-linecap:round;
  stroke-linejoin:round;opacity:.13;}
.glass>*:not(.wm){position:relative;z-index:1;}
@media (max-width:900px){ .wm{display:none;} }

/* ---- section head: number pill, icon, kicker, ruled title ---- */
.sechead{align-items:flex-start;gap:clamp(11px,1.3vw,16px);border-bottom:none;
  padding-bottom:0;margin-bottom:clamp(14px,2vh,22px);}
.sechead::after{display:none;}
.sectext{min-width:0;}
.secnum{color:var(--lime);border:1px solid rgba(198,236,143,.45);
  background:rgba(198,236,143,.10);align-self:center;}
.kick{color:var(--lime);font-size:11.5px;font-weight:700;letter-spacing:.09em;
  text-transform:uppercase;margin:0 0 5px;}
.sechead h2{position:relative;}
.sechead h2::after{content:"";display:block;width:52px;height:3px;border-radius:3px;
  margin-top:10px;background:linear-gradient(90deg,var(--lime),rgba(198,236,143,0));}
.sechead .ic{align-self:center;}

/* ---- icons in the template's tile language ---- */
.ic{color:var(--lime);border-color:rgba(198,236,143,.32);
  background:rgba(198,255,106,.08);}
.ic.xl{width:52px;height:52px;border-radius:14px;border-width:1.5px;}
.ic.xl svg{width:28px;height:28px;stroke-width:1.5;}
@media (min-width:901px) and (prefers-reduced-motion:no-preference){
  .anim .slide.active .cards.iconrow .ic svg{animation:mtFloat 3.4s ease-in-out infinite;}
  .anim .slide.active .cards.iconrow .card:nth-child(2) .ic svg{animation-delay:.25s;}
  .anim .slide.active .cards.iconrow .card:nth-child(3) .ic svg{animation-delay:.5s;}
}
@keyframes mtFloat{0%,100%{transform:translateY(0);}50%{transform:translateY(-3px);}}

/* ---- ANIMATED CONTENT ICONS ----
   Two layers of life, pure CSS, no runtime: an entrance stroke-DRAW when a slide
   becomes active, and a slow, tiny IDLE loop keyed to what each glyph depicts
   (leaf sways, droplet bobs, fish swims, cart/truck nudge, spark twinkles, bolt
   flickers, sun/gear turn, trend/target pulse, factory puffs a smoke dot).
   WHY the split across two elements: the sprite normalises every shape to
   pathLength 100, and stroke-* properties INHERIT into each <use> clone, so the
   draw is set on the <use> (stroke-dashoffset) while the idle transform sits on
   the parent <svg> - keeping them on different elements means neither `animation`
   overwrites the other. Amplitudes stay under a few px / degrees and periods run
   4-8s so nothing distracts a reader. Everything is gated on
   (prefers-reduced-motion:no-preference), so a reduced-motion reader simply never
   sees these rules and gets fully drawn, perfectly still icons - no lower-
   specificity override left to be beaten. */
.ic svg use{stroke-dasharray:100;}                 /* pathLength-normalised: solid at offset 0 */
#i-factory .smoke{stroke:none;fill:currentColor;opacity:0;transform-box:fill-box;transform-origin:center;}
@keyframes icDraw{from{stroke-dashoffset:100;}to{stroke-dashoffset:0;}}
@keyframes idLeaf{0%,100%{transform:rotate(-3deg);}50%{transform:rotate(3deg);}}
@keyframes idBob{0%,100%{transform:translateY(0);}50%{transform:translateY(-1.6px);}}
@keyframes idSwim{0%,100%{transform:translateX(-2px);}50%{transform:translateX(2px);}}
@keyframes idNudge{0%,100%{transform:translateX(-1.4px);}50%{transform:translateX(1.4px);}}
@keyframes idTwinkle{0%,100%{opacity:1;transform:scale(1);}50%{opacity:.55;transform:scale(.9);}}
@keyframes idFlic{0%,40%,60%,100%{opacity:1;}50%{opacity:.5;}}
@keyframes idSpin{0%,100%{transform:rotate(-9deg);}50%{transform:rotate(9deg);}}
@keyframes idPulse{0%,100%{transform:scale(1);}50%{transform:scale(1.06);}}
@keyframes idPuff{0%{opacity:0;transform:translateY(0) scale(.5);}
  15%{opacity:.7;}100%{opacity:0;transform:translateY(-7px) scale(1.15);}}
@media (min-width:761px) and (prefers-reduced-motion:no-preference){
  .anim .slide.active .ic svg use{animation:icDraw .7s ease .05s both;}
  .anim .slide.active .ic-leaf svg{transform-origin:28% 82%;animation:idLeaf 6s ease-in-out .7s infinite;}
  .anim .slide.active .ic-drop svg{transform-origin:50% 60%;animation:idBob 4.5s ease-in-out .7s infinite;}
  .anim .slide.active .ic-fish svg{transform-origin:50% 50%;animation:idSwim 5s ease-in-out .7s infinite;}
  .anim .slide.active .ic-cart svg{transform-origin:50% 80%;animation:idNudge 5s ease-in-out .7s infinite;}
  .anim .slide.active .ic-truck svg{transform-origin:50% 80%;animation:idNudge 5.5s ease-in-out .7s infinite;}
  .anim .slide.active .ic-spark svg{transform-origin:50% 50%;animation:idTwinkle 4s ease-in-out .7s infinite;}
  .anim .slide.active .ic-bolt svg{transform-origin:50% 50%;animation:idFlic 4.5s ease-in-out .7s infinite;}
  .anim .slide.active .ic-sun svg{transform-origin:50% 50%;animation:idSpin 7s ease-in-out .7s infinite;}
  .anim .slide.active .ic-gear svg{transform-origin:50% 50%;animation:idSpin 6.5s ease-in-out .7s infinite;}
  .anim .slide.active .ic-trend svg{transform-origin:50% 70%;animation:idPulse 5s ease-in-out .7s infinite;}
  .anim .slide.active .ic-target svg{transform-origin:50% 50%;animation:idPulse 4.5s ease-in-out .7s infinite;}
  .anim .slide.active .ic-alert svg{transform-origin:50% 60%;animation:idFlic 5s ease-in-out .7s infinite;}
  /* the smoke dot lives in the shared sprite, not inside any one .ic span, so it
     is driven on the referenced element and puffs in every factory glyph at once
     (off-screen instances animate invisibly, which costs nothing to a reader) */
  #i-factory .smoke{animation:idPuff 5s ease-in-out infinite;}
}

/* ---- ICON ROW: three peers, icon-led, centred (the .pptx iconrow) ---- */
.cards.iconrow{grid-template-columns:repeat(auto-fit,minmax(210px,1fr));}
.cards.iconrow .card{text-align:center;padding:22px 20px 20px;
  background:rgba(255,255,255,.05);border-color:rgba(198,236,143,.22);}
.cards.iconrow .card::before{display:none;}
.cards.iconrow .card>.ic{margin:0 auto 12px;}
.cards.iconrow .card h3{color:#e4ffb0;}
@media (max-width:900px){ .cards.iconrow{grid-template-columns:1fr;} }

/* ---- PILLARS: an ordered set, each under its own accent rail ---- */
.cards.pillars .card{background:rgba(255,255,255,.05);
  border-color:rgba(198,236,143,.22);padding-top:22px;}
.cards.pillars .card::after{content:"";position:absolute;left:20px;right:20px;top:0;
  height:3px;border-radius:0 0 3px 3px;
  background:linear-gradient(90deg,var(--lime),rgba(198,236,143,0));}
.cards.pillars .card h3{color:#e4ffb0;}
.cards.pillars .card::before{top:20px;color:var(--lime);}
.cards .card>.ic{margin-bottom:10px;}

/* ---- BIG NUMBER band ---- */
.grid.big{grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:clamp(10px,1.4vw,16px);}
.grid.big .cell{border-color:rgba(198,236,143,.30);background:rgba(198,236,143,.06);
  padding:22px 22px 18px;}
.grid.big .cell .v{font-size:clamp(30px,4.4vw,46px);color:var(--lime);letter-spacing:-.02em;}
.grid.big .cell .l{font-size:13.5px;color:rgba(255,255,255,.8);}
.cell .v,.scell .v{color:var(--lime);}
.scell{border-color:rgba(198,236,143,.26);background:rgba(198,236,143,.05);}

/* ---- chips, steps, entries, quotes: the same numbered-card rhythm ---- */
.chip{border-color:rgba(198,236,143,.22);border-left:3px solid var(--lime);
  background:rgba(255,255,255,.05);}
.step::before{background:var(--lime);}
.step-v,.statnote-v,.entry .term{color:var(--lime);}
.statnote{border-color:rgba(198,236,143,.22);background:rgba(255,255,255,.05);}
.secbody .k{color:var(--lime);}
.secbody h3{color:#e4ffb0;}
.colbar{background:linear-gradient(180deg,var(--lime),color-mix(in srgb,var(--t1) 70%,transparent));
  border-color:rgba(198,236,143,.45);}

/* ---- SWOT: the real 2x2 matrix, colour-keyed per quadrant ---- */
.swot-cap{font-size:12.5px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;
  color:var(--mut2);margin:2px 0 14px;}
.swot{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:clamp(10px,1.4vw,16px);
  margin:4px 0 20px;}
.swot-q{position:relative;border-radius:16px;padding:16px 18px 14px;
  background:color-mix(in srgb,var(--q) 8%,rgba(255,255,255,.04));
  border:1px solid color-mix(in srgb,var(--q) 34%,transparent);
  border-top:3px solid var(--q);}
.swot-h{display:flex;align-items:center;gap:10px;margin:0 0 10px;
  padding-bottom:9px;border-bottom:1px solid color-mix(in srgb,var(--q) 26%,transparent);}
.swot-ic{flex:0 0 auto;display:inline-grid;place-items:center;width:30px;height:30px;
  border-radius:9px;color:var(--q);
  background:color-mix(in srgb,var(--q) 16%,transparent);
  border:1px solid color-mix(in srgb,var(--q) 34%,transparent);}
.swot-ic svg{width:17px;height:17px;fill:none;stroke:currentColor;stroke-width:1.7;
  stroke-linecap:round;stroke-linejoin:round;}
.swot-t{font-family:'Trebuchet MS','Verdana Pro',Verdana,sans-serif;font-weight:700;
  font-size:clamp(15px,1.6vw,18px);letter-spacing:.02em;color:var(--q);}
.swot-l{list-style:none;margin:0;padding:0;display:grid;gap:8px;}
.swot-l li{position:relative;padding-left:16px;font-size:14px;line-height:1.5;
  color:var(--mut);}
.swot-l li::before{content:"";position:absolute;left:0;top:8px;width:6px;height:6px;
  border-radius:50%;background:var(--q);}
@media (max-width:820px){ .swot{grid-template-columns:1fr;} }
/* the four quadrants pop in on a diagonal, like the deck template's SWOT build */
@media (min-width:761px) and (prefers-reduced-motion:no-preference){
  .anim .slide .swot-q{opacity:0;}
  .anim .slide.active .swot-q{animation:cdPop .5s cubic-bezier(.2,.8,.3,1) forwards;}
  .anim .slide.active .swot-q:nth-child(1){animation-delay:.12s;}
  .anim .slide.active .swot-q:nth-child(2){animation-delay:.24s;}
  .anim .slide.active .swot-q:nth-child(3){animation-delay:.36s;}
  .anim .slide.active .swot-q:nth-child(4){animation-delay:.48s;}
}
@media (max-width:760px),(prefers-reduced-motion:reduce){ .swot-q{opacity:1!important;} }

/* ---- DEFINITION LIST: label leads, its definition beneath ---- */
.dl-cap{font-size:14.5px;line-height:1.5;color:var(--mut);margin:0 0 14px;max-width:78ch;}
.cards.deflist{grid-template-columns:repeat(auto-fit,minmax(232px,1fr));}
.cards.deflist .dl-card{padding:16px 18px 14px;background:rgba(255,255,255,.05);
  border-color:rgba(198,236,143,.22);}
.cards.deflist .dl-card::before{display:none;}
.cards.deflist .dl-card>.ic{margin-bottom:10px;}
.cards.deflist .dl-card h3{color:#e4ffb0;margin:0 0 5px;font-size:clamp(15px,1.5vw,17px);}
.cards.deflist .dl-card p{margin:0;font-size:14px;line-height:1.5;color:var(--mut);max-width:none;}

/* ---- AGENDA: what the deck covers, straight off the section titles ---- */
.agenda{list-style:none;margin:0;padding:0;display:grid;gap:9px;
  grid-template-columns:repeat(2,minmax(0,1fr));}
.ag-i{display:flex;align-items:center;gap:12px;padding:11px 15px;border-radius:12px;
  background:rgba(255,255,255,.05);border:1px solid rgba(198,236,143,.2);
  transition:transform .26s cubic-bezier(.2,.7,.2,1),border-color .26s ease;}
.ag-i:hover{transform:translateX(3px);border-color:rgba(198,236,143,.5);}
.ag-n{flex:0 0 auto;font-weight:750;font-size:12.5px;letter-spacing:.06em;
  color:var(--lime);width:24px;}
.ag-t{font-weight:650;font-size:14.5px;line-height:1.35;color:#fff;}
@media (max-width:900px){ .agenda{grid-template-columns:1fr;} }
@media (min-width:761px) and (prefers-reduced-motion:no-preference){
  .anim .slide.active .ag-i:nth-child(n){animation-delay:calc(.10s + var(--i,0) * .05s);}
}

/* ---- CLOSING plate ---- */
.cl-glass{display:flex;flex-direction:column;justify-content:center;text-align:center;}
.cl-glass .summary{margin-left:auto;margin-right:auto;}
.cl-h{font-family:'Trebuchet MS','Verdana Pro',Verdana,sans-serif;font-weight:600;
  font-size:clamp(26px,4.4vw,44px);line-height:1.1;letter-spacing:-.02em;color:#fff;margin:0 0 16px;}
.cl-h::after{content:"";display:block;width:64px;height:3px;border-radius:3px;
  margin:16px auto 0;background:linear-gradient(90deg,rgba(198,236,143,0),var(--lime),rgba(198,236,143,0));}
.cl-src{font-size:12.5px;color:rgba(255,255,255,.5);margin:6px 0 0;}
.cl-foot{display:flex;gap:9px;justify-content:center;align-items:center;margin-top:18px;
  font-size:12.5px;font-weight:650;letter-spacing:.04em;color:rgba(255,255,255,.72);}
.cl-dot{color:var(--lime);}
.cl-cta{display:inline-block;margin:20px auto 0;padding:11px 22px;border-radius:999px;
  font-size:14px;font-weight:700;text-decoration:none;color:#0B2E20;background:var(--lime);
  transition:transform .2s ease,background .2s ease;}
.cl-cta:hover{transform:translateY(-2px);background:var(--lime-hot);}

/* ---------- mobile: degrade to a vertical stack ---------- */
@media (max-width:760px){
  body{overflow:auto;}
  .stage{position:static;}
  .track{display:block;height:auto;transform:none!important;transition:none;}
  .slide{flex:none;height:auto;min-height:88vh;padding:64px 16px;}
  .glass{height:auto;max-height:none;overflow:visible;width:100%;}
  .nav,.dots,.count{display:none;}
  .anim .slide .r{opacity:1!important;}
}
@media (prefers-reduced-motion:reduce){
  .track{transition:none;} .media{animation:none;}
  .anim .r{opacity:1!important;}
}

/* ================= TYPED-BLOCK LAYOUTS (JSON content pipeline) =================
   The renderer now consumes typed content JSON, so each block type gets a
   purpose-built layout instead of being recovered from a flattened chip run.
   Declared after the base rules so the column-count control wins over the old
   auto-fit grids. WHY per-type: the audit's presentation_issues were all one
   family - peer items losing their grouping, headers reading as items, stats
   losing labels, flows/tables/phases flattened. A dedicated layout per shape
   removes that whole class. */

/* SYMMETRY: item count drives the column count (never a 3+1 hole). --cols is set
   inline per block from grid_cols(); mobile collapses every peer grid to one. */
.cards,.grid,.grid.big,.cards.iconrow,.cards.pillars,.cards.deflist,
.phases,.compare,.groups,.fan-branches{
  grid-template-columns:repeat(var(--cols,3),minmax(0,1fr));}
/* equal card heights within a row: grid stretch + full-height card */
.cards .card{height:100%;}

/* explicit ordinals for numbered sets (steps, n-tagged cards): the asserted n,
   not a CSS counter, so the source's own numbering survives */
.cards.num .card::before{display:none;}
.pnum{position:absolute;top:18px;right:18px;
  font-family:'Trebuchet MS','Verdana Pro',Verdana,sans-serif;font-weight:700;font-size:13px;
  color:var(--lime);letter-spacing:.04em;}

/* stats footnote + qualifier line (stat keeps value AND full label in one tile) */
.grid-foot,.tbl-foot{font-size:12px;color:var(--mut2);margin:2px 0 18px;font-style:italic;}
.cell .q{margin-top:5px;font-size:12px;color:var(--mut2);line-height:1.4;}

/* CALLOUT: an emphasis box, deliberately unlike a card (accent fill + left rail) */
.callout{position:relative;margin:16px 0 18px;padding:15px 20px 13px;border-radius:14px;
  background:rgba(198,255,106,.07);border:1px solid rgba(198,236,143,.30);
  border-left:4px solid var(--lime);}
.callout-label{display:flex;align-items:center;gap:8px;margin:0 0 6px;
  font-size:11.5px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--lime);}
.callout-label .ic{flex:0 0 auto;}
.callout>p{margin:0;color:var(--fg);font-size:15px;line-height:1.55;max-width:82ch;}

/* QUOTE: a pull quote, distinct from both card and callout */
.quote{position:relative;margin:16px 0 18px;padding:18px 22px 16px 48px;border-radius:14px;
  background:rgba(255,255,255,.04);border:1px solid var(--line);}
.quote::before{content:"\201C";position:absolute;left:15px;top:4px;font-size:46px;line-height:1;
  color:var(--lime);opacity:.5;font-family:Georgia,'Times New Roman',serif;}
.quote p{margin:0;font-size:clamp(16px,1.9vw,20px);line-height:1.5;color:#fff;
  font-style:italic;max-width:74ch;}
/* attribution dash is chrome (CSS escape, never a literal em dash in the HTML) */
.quote-attr{margin-top:10px;font-size:13px;font-weight:600;color:var(--lime);font-style:normal;}
.quote-attr::before{content:"\2014\00a0";}

/* titled bullet LIST */
.blist{margin:14px 0 18px;}
.blist-title{font-weight:700;font-size:14px;color:#e4ffb0;margin:0 0 8px;}
.blist ul{list-style:none;margin:0;padding:0;display:grid;gap:8px;}
.blist li{position:relative;padding-left:20px;font-size:14.5px;line-height:1.55;
  color:var(--mut);max-width:82ch;}
.blist li::before{content:"";position:absolute;left:2px;top:9px;width:7px;height:7px;
  border-radius:2px;background:var(--lime);transform:rotate(45deg);}

/* FLOW: horizontal stage chain, arrows are CSS/SVG connectors (never content) */
.flow{display:flex;flex-wrap:wrap;align-items:stretch;gap:10px;margin:16px 0 6px;}
.flow-stage{flex:1 1 150px;min-width:138px;background:rgba(255,255,255,.05);
  border:1px solid rgba(198,236,143,.24);border-radius:12px;padding:13px 16px;}
.fs-name{font-weight:700;font-size:15px;color:#e4ffb0;margin-bottom:5px;}
.fs-desc{font-size:13px;line-height:1.5;color:var(--mut);}
.flow-arrow{flex:0 0 auto;align-self:center;display:grid;place-items:center;color:var(--lime);}
.flow-arrow svg{width:22px;height:22px;fill:none;stroke:currentColor;stroke-width:2;
  stroke-linecap:round;stroke-linejoin:round;}
.flow-closing{margin:12px 0 18px;font-size:14px;font-weight:600;color:#e4ffb0;
  padding-left:12px;border-left:3px solid var(--lime);}

/* PHASES: each group a labelled cluster (pill + optional period/name + tasks) */
.phases{display:grid;gap:14px;margin:16px 0 18px;}
.phase{background:rgba(255,255,255,.05);border:1px solid rgba(198,236,143,.22);
  border-radius:14px;padding:15px 18px 13px;}
.phase-head{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:9px;}
.phase-label{font-family:'Trebuchet MS','Verdana Pro',Verdana,sans-serif;font-weight:700;
  font-size:12px;letter-spacing:.05em;text-transform:uppercase;color:#0B2E20;
  background:var(--lime);padding:4px 11px;border-radius:999px;}
.phase-period{font-size:12px;color:var(--mut2);}
.phase-name{font-weight:700;font-size:14.5px;color:#e4ffb0;margin-bottom:8px;}
.phase ul{list-style:none;margin:0;padding:0;display:grid;gap:6px;}
.phase li{position:relative;padding-left:16px;font-size:13.5px;line-height:1.5;color:var(--mut);}
.phase li::before{content:"";position:absolute;left:2px;top:8px;width:5px;height:5px;
  border-radius:50%;background:var(--lime);}

/* TIMELINE: era rows on a continuous rail (chronology is now expressed) */
.timeline{position:relative;margin:16px 0 18px;padding-left:6px;}
.timeline::before{content:"";position:absolute;left:5px;top:6px;bottom:6px;width:2px;
  background:linear-gradient(180deg,var(--lime),rgba(198,236,143,.15));}
.tl-row{position:relative;padding:0 0 16px 22px;}
.tl-row:last-child{padding-bottom:0;}
.tl-row::before{content:"";position:absolute;left:0;top:5px;width:11px;height:11px;
  border-radius:50%;background:var(--lime);box-shadow:0 0 0 4px var(--ink);}
.tl-period{font-family:'Trebuchet MS','Verdana Pro',Verdana,sans-serif;font-weight:700;
  font-size:13px;color:var(--lime);letter-spacing:.03em;margin-bottom:3px;}
.tl-title{font-weight:700;font-size:15px;color:#fff;margin:0 0 3px;}
.tl-desc{margin:0;font-size:14px;line-height:1.55;color:var(--mut);max-width:82ch;}

/* real TABLE: header row, zebra body, scrolls horizontally when wide */
.tbl-wrap{overflow-x:auto;margin:16px 0 6px;border:1px solid var(--line);border-radius:12px;
  scrollbar-width:thin;scrollbar-color:rgba(198,236,143,.4) transparent;}
.tbl-wrap::-webkit-scrollbar{height:8px;}
.tbl-wrap::-webkit-scrollbar-thumb{background:rgba(198,236,143,.4);border-radius:8px;}
.tbl{border-collapse:collapse;width:100%;min-width:420px;font-size:14px;}
.tbl th,.tbl td{text-align:left;padding:11px 16px;border-bottom:1px solid var(--line);}
.tbl thead th{font-family:'Trebuchet MS','Verdana Pro',Verdana,sans-serif;font-weight:700;
  font-size:12.5px;letter-spacing:.04em;text-transform:uppercase;color:#0B2E20;
  background:var(--lime);border-bottom:none;white-space:nowrap;}
.tbl tbody tr:nth-child(even){background:rgba(255,255,255,.04);}
.tbl tbody tr:hover{background:rgba(198,236,143,.08);}
.tbl td{color:var(--mut);}
.tbl td:first-child{color:#e4ffb0;font-weight:600;}

/* COMPARE: two/three columns, header visually distinct from its items */
.compare{display:grid;gap:14px;margin:16px 0 18px;align-items:start;}
.cmp-col{background:rgba(255,255,255,.04);border:1px solid var(--line);border-radius:14px;
  padding:0 0 12px;overflow:hidden;}
.cmp-h{font-family:'Trebuchet MS','Verdana Pro',Verdana,sans-serif;font-weight:700;
  font-size:14.5px;color:#0B2E20;background:var(--lime);padding:11px 16px;margin-bottom:10px;}
.cmp-col ul{list-style:none;margin:0;padding:0 16px;display:grid;gap:8px;}
.cmp-col li{position:relative;padding-left:16px;font-size:14px;line-height:1.5;color:var(--mut);}
.cmp-col li::before{content:"";position:absolute;left:0;top:8px;width:6px;height:6px;
  border-radius:50%;background:var(--lime);}

/* GROUPS: grouped checklist, group header distinct from its items */
.groups{display:grid;gap:14px;margin:16px 0 18px;align-items:start;}
.grp{background:rgba(255,255,255,.05);border:1px solid rgba(198,236,143,.2);border-radius:14px;
  padding:14px 18px 12px;}
.grp-h{font-family:'Trebuchet MS','Verdana Pro',Verdana,sans-serif;font-weight:700;font-size:13px;
  letter-spacing:.05em;text-transform:uppercase;color:var(--lime);margin-bottom:10px;
  padding-bottom:8px;border-bottom:1px solid rgba(198,236,143,.22);}
.grp ul{list-style:none;margin:0;padding:0;display:grid;gap:7px;}
.grp li{position:relative;padding-left:16px;font-size:14px;line-height:1.5;color:var(--mut);}
.grp li::before{content:"";position:absolute;left:2px;top:8px;width:6px;height:6px;
  border-radius:50%;background:var(--lime);}
.grp-term{font-weight:700;color:#e4ffb0;}

/* HIERARCHY: org tiers, level label distinct from the entity + gloss */
.tiers{display:grid;gap:12px;margin:16px 0 6px;}
.tier{display:grid;grid-template-columns:minmax(120px,188px) 1fr;gap:16px;align-items:center;
  background:rgba(255,255,255,.05);border:1px solid rgba(198,236,143,.2);border-radius:14px;
  padding:14px 18px;}
.tier-level{font-family:'Trebuchet MS','Verdana Pro',Verdana,sans-serif;font-weight:700;
  font-size:13px;letter-spacing:.03em;text-transform:uppercase;color:#0B2E20;
  background:var(--lime);padding:7px 12px;border-radius:8px;text-align:center;}
.tier-name{font-weight:700;font-size:15px;color:#e4ffb0;margin:0 0 4px;}
.tier-desc{margin:0;font-size:14px;line-height:1.5;color:var(--mut);}
.tiers-closing{margin:8px 0 18px;font-size:14px;font-weight:600;color:#e4ffb0;
  padding-left:12px;border-left:3px solid var(--lime);}
@media(max-width:640px){.tier{grid-template-columns:1fr;gap:8px;}}

/* FANOUT: one input hub fanning out to component -> product branches */
.fanout{margin:16px 0 18px;}
.fan-hub{display:flex;justify-content:center;margin-bottom:6px;}
.fan-input{display:inline-flex;align-items:center;gap:10px;font-weight:700;font-size:16px;
  color:#0B2E20;background:var(--lime);padding:9px 20px;border-radius:999px;}
.fan-input .ic{color:#0B2E20;border-color:rgba(11,46,32,.3);background:rgba(11,46,32,.12);}
.fan-branches{display:grid;gap:12px;position:relative;padding-top:16px;}
.fan-branches::before{content:"";position:absolute;left:0;right:0;top:0;height:1px;
  background:linear-gradient(90deg,transparent,rgba(198,236,143,.45),transparent);}
.fan-branch{background:rgba(255,255,255,.05);border:1px solid rgba(198,236,143,.22);
  border-radius:12px;padding:12px 16px;}
.fan-comp{font-weight:700;font-size:14px;color:#e4ffb0;margin-bottom:8px;
  padding-bottom:6px;border-bottom:1px solid rgba(198,236,143,.2);}
.fan-branch ul{list-style:none;margin:0;padding:0;display:grid;gap:6px;}
.fan-branch li{position:relative;padding-left:14px;font-size:13.5px;line-height:1.45;color:var(--mut);}
.fan-branch li::before{content:"";position:absolute;left:0;top:8px;width:5px;height:5px;
  border-radius:50%;background:var(--lime);}

/* section standfirst (lead) + per-section source footnote + CONT. marker */
.seclead{font-size:clamp(15px,1.8vw,17px);line-height:1.55;color:#dfeee0;margin:0 0 14px;
  max-width:84ch;font-weight:500;}
.secsrc{margin:16px 0 0;font-size:12px;color:var(--mut2);font-style:italic;}
.sechead h2 .cont{font-size:.46em;font-weight:700;letter-spacing:.09em;color:var(--mut2);
  vertical-align:middle;margin-left:8px;text-transform:uppercase;}
.cover-aud{font-size:13px;color:var(--mut2);margin:14px 0 0;line-height:1.5;}

/* mobile: every peer grid collapses to a single column */
@media(max-width:760px){
  .cards,.grid,.grid.big,.cards.iconrow,.cards.pillars,.cards.deflist,
  .phases,.compare,.groups,.fan-branches{grid-template-columns:1fr!important;}
}
</style>
</head>
<body>
<a class="back" href="../index.html#districts">&#8592; Library</a>
<div class="count"><b id="cnum">01</b> / <span id="ctot">%%COUNT%%</span></div>
%%SPRITE%%
<div class="stage">
  <div class="track" id="track">
%%SLIDES%%
  </div>
</div>
<button class="nav prev" id="prev" type="button" aria-label="Previous slide"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg></button>
<button class="nav next" id="next" type="button" aria-label="Next slide"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18l6-6-6-6"/></svg></button>
<div class="dots" id="dots"></div>

<script src="../assets/dash/gsap.js"></script>
<script>
(function(){
  var root=document.documentElement;
  var track=document.getElementById('track');
  var slides=[].slice.call(track.querySelectorAll('.slide'));
  var N=slides.length, cur=0;
  var prev=document.getElementById('prev'), next=document.getElementById('next');
  var dotsWrap=document.getElementById('dots'), cnum=document.getElementById('cnum');
  var ctot=document.getElementById('ctot');
  var dots=null;
  var mobile=function(){return matchMedia('(max-width:760px)').matches;};

  // ---------- pagination: a slide never scrolls, it overflows into another slide
  // The panel used to scroll internally, which broke the deck illusion - a slide
  // that scrolls is a web page. So each section's body is filled block by block
  // and cut the moment it would exceed the panel, with the remainder continuing
  // on a fresh slide that keeps the same number, title and background role.
  // This is measured in the browser rather than estimated at build time, because
  // the break point depends on the viewport and on the actual rendered font.
  function paginate(){
    if(mobile()) return;   // mobile stacks vertically; there are no slides to fill
    var out=[];
    slides.forEach(function(sl){
      var glass=sl.querySelector('.glass');
      var body=glass && glass.querySelector('.secbody');
      if(!body || glass.scrollHeight<=glass.clientHeight+2){ out.push(sl); return; }

      var kids=[].slice.call(body.children);
      kids.forEach(function(k){ body.removeChild(k); });

      var page=sl, pbody=body;
      out.push(page);
      // A grid of peer cards (icon row, pillars, definition list, chips) can be
      // broken between its cards when it alone is taller than the panel; a SWOT
      // never is, because splitting it would break the 2x2 that is the point.
      function splittable(el){ return el && /(^|\s)(cards|chips)(\s|$)/.test(el.className); }
      function fits(){ var g=page.querySelector('.glass'); return g.scrollHeight<=g.clientHeight+2; }
      kids.forEach(function(k){
        pbody.appendChild(k);
        if(fits()) return;
        if(pbody.children.length>1){
          pbody.removeChild(k);
          page=newPage(sl); out.push(page);
          pbody=page.querySelector('.secbody');
          pbody.appendChild(k);
          if(fits()) return;
        }
        // k is now alone on its page and still overflows.
        if(splittable(k) && k.children.length>1){
          var items=[].slice.call(k.children);
          k.textContent='';
          var grid=k;
          items.forEach(function(it){
            grid.appendChild(it);
            if(fits()) return;
            if(grid.children.length===1) return; // one card taller than panel: unavoidable
            grid.removeChild(it);
            page=newPage(sl); out.push(page);
            pbody=page.querySelector('.secbody');
            grid=k.cloneNode(false);           // same grid class, empty
            pbody.appendChild(grid);
            grid.appendChild(it);
          });
        }
      });
    });
    // newPage appends to the track, so continuation slides land at the end while
    // the reading order lives in `out`. The track is a translateX strip driven by
    // DOM order, so re-append in `out` order or navigation jumps around.
    out.forEach(function(sl,i){
      sl.setAttribute('data-i', i);
      track.appendChild(sl);
    });
    slides=out; N=out.length;
    if(ctot) ctot.textContent=('0'+N).slice(-2);
  }

  function newPage(src){
    var sl=document.createElement('section');
    sl.className='slide';
    var m=src.querySelector('.media');
    var head=src.querySelector('.sechead');
    // Same data-media index on purpose: a continuation keeps the background of
    // the section it continues, so one section reads as one place.
    sl.innerHTML='<div class="media"'
      + (m ? ' data-media="'+m.getAttribute('data-media')+'" data-role="'+m.getAttribute('data-role')+'"' : '')
      + '></div><div class="glass reveal-root">'
      + (head ? '<div class="sechead r">'+head.innerHTML+'</div>' : '')
      + '<div class="secbody r"></div></div>';
    var h2=sl.querySelector('.sechead h2');
    if(h2) h2.innerHTML=h2.innerHTML+' <span class="cont">cont.</span>';
    track.appendChild(sl);
    return sl;
  }

  // Background asset resolution, most-specific first, gradient if none exist:
  //   1. per-case  media/<slug>/<i>.(mp4|jpg)        e.g. media/morbi-.../2.jpg
  //   2. common    media/common/<role>.(mp4|jpg)     reused across all cases
  //   3. mesh gradient already painted in CSS (do nothing)
  var SLUG='%%SLUG%%';
  function tryAsset(m, cands){
    if(!cands.length) return;
    var url=cands.shift();
    if(/\.mp4$/.test(url)){
      var v=document.createElement('video');
      v.muted=true;v.loop=true;v.playsInline=true;v.autoplay=true;v.preload='auto';
      v.onloadeddata=function(){ m.classList.add('has-asset'); m.appendChild(v); v.play&&v.play(); };
      v.onerror=function(){ tryAsset(m,cands); };
      v.src=url;
    } else {
      var img=new Image();
      img.onload=function(){ m.classList.add('has-asset'); m.appendChild(img); };
      img.onerror=function(){ tryAsset(m,cands); };
      img.src=url;
    }
  }
  // The build-time packer (est_height in proto_deck.py) is authoritative: it
  // splits sections into CONT slides that already fit the panel. This browser
  // pass stays as a safety net for the rare block whose real font metrics beat
  // the model by a few px. `?nopag` disables the net so the model can be proven
  // on its own during calibration; production keeps the net on.
  var NOPAG=/[?&]nopag\b/.test(location.search);
  function layout(){
  try{ if(!NOPAG) paginate(); }catch(err){ /* never let layout maths kill the deck */ }

  slides.forEach(function(sl){
    var m=sl.querySelector('.media'); if(!m) return;
    var i=m.getAttribute('data-media'), role=m.getAttribute('data-role');
    tryAsset(m, [
      'media/'+SLUG+'/'+i+'.mp4', 'media/'+SLUG+'/'+i+'.gif', 'media/'+SLUG+'/'+i+'.jpg',
      'media/common/'+role+'.mp4', 'media/common/'+role+'.gif', 'media/common/'+role+'.jpg',
      '../assets/video/gridwork.mp4'
    ]);
  });

  // dots
  slides.forEach(function(_,i){
    var d=document.createElement('div'); d.className='dot'+(i?'':' on');
    d.addEventListener('click',function(){ go(i); });
    dotsWrap.appendChild(d);
  });
  dots=[].slice.call(dotsWrap.children);
  paint();
  }
  // Measure only once the webfont is in: against the fallback face the line
  // count is wrong and the deck breaks pages in the wrong places.
  if(document.fonts&&document.fonts.ready){ document.fonts.ready.then(layout); }
  else { layout(); }

  function paint(){
    if(!dots) return;
    if(!mobile()) track.style.transform='translateX(-'+(cur*100)+'%)';
    dots.forEach(function(d,i){ d.classList.toggle('on', i===cur); });
    cnum.textContent=('0'+(cur+1)).slice(-2);
    prev.toggleAttribute('disabled', cur===0);
    next.toggleAttribute('disabled', cur===N-1);
    // The suggested next move breathes: forward while a next slide exists, back
    // only at the very end. Enabled arrows also carry a static glow so which way
    // to go is legible without the wheel.
    next.classList.toggle('nudge', cur!==N-1);
    prev.classList.toggle('nudge', cur===N-1 && cur!==0);
    slides.forEach(function(s,i){ s.classList.toggle('active', i===cur); });
    reveal(slides[cur]);
  }
  function go(i){ cur=Math.max(0,Math.min(N-1,i)); paint(); }
  function step(d){ go(cur+d); }

  prev.addEventListener('click',function(){ step(-1); });
  next.addEventListener('click',function(){ step(1); });
  addEventListener('keydown',function(ev){
    if(ev.key==='ArrowRight'||ev.key==='PageDown'){ step(1); }
    else if(ev.key==='ArrowLeft'||ev.key==='PageUp'){ step(-1); }
    else if(ev.key==='Home'){ go(0); } else if(ev.key==='End'){ go(N-1); }
  });
  // Wheel no longer advances slides: paging is by the on-screen arrows and the
  // keyboard only, so scrolling the window never jumps the deck. A panel that
  // still overflows (a single card taller than the viewport) scrolls natively
  // under the wheel, because nothing here intercepts it.
  // touch swipe
  var sx=0,sy=0;
  addEventListener('touchstart',function(e){ sx=e.touches[0].clientX; sy=e.touches[0].clientY; },{passive:true});
  addEventListener('touchend',function(e){
    if(mobile()) return;
    var dx=e.changedTouches[0].clientX-sx, dy=e.changedTouches[0].clientY-sy;
    if(Math.abs(dx)>60 && Math.abs(dx)>Math.abs(dy)) step(dx<0?1:-1);
  },{passive:true});

  // content reveal per active slide (rAF-gated; content never left hidden)
  var g=window.gsap, armed=root.classList.contains('anim'), alive=false, ready=false;
  if(g&&armed){ g.ticker.lagSmoothing(0); requestAnimationFrame(function(){alive=true;});
    setTimeout(function(){ if(!alive){ root.classList.remove('anim'); } ready=true; paint(); }, 260); }
  else { root.classList.remove('anim'); ready=true; paint(); }
  function reveal(slide){
    if(!ready||!alive||!g||!armed||mobile()) return;
    var els=slide.querySelectorAll('.r');
    g.killTweensOf(els);
    g.fromTo(els,{opacity:0,y:24},{opacity:1,y:0,duration:.6,stagger:.08,ease:'power3.out'});
  }
  // first paint happens after the probe above; if gsap absent it already ran
})();
</script>
</body>
</html>
"""


def load_content(slug):
    """Read scripts/deck_content/<slug>.json. A missing file is a hard error that
    names the slug, so a mistyped or not-yet-authored deck fails loudly."""
    path = os.path.join(CONTENT_DIR, slug + ".json")
    if not os.path.exists(path):
        raise SystemExit("proto_deck: no content JSON for slug '" + slug
                         + "' (expected " + path + ")")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def render(m, content=None):
    if content is None:
        content = load_content(m["slug"])
    slides = slides_html(content, m)
    t1, t2 = tint_for(m)
    title = content.get("title") or m.get("title", "")
    html = (TMPL
            .replace("%%TITLE%%", e(title))
            .replace("%%TINT1%%", t1).replace("%%TINT2%%", t2)
            .replace("%%COUNT%%", "%02d" % len(slides))
            .replace("%%SLUG%%", m["slug"])
            .replace("%%SPRITE%%", ICON_SPRITE)
            .replace("%%SLIDES%%", "\n".join(slides)))
    return html, len(slides), content


# ---------------------------------------------------------------- integrity engine
# `--check` renders every deck whose JSON exists and asserts the invariants the
# audit's presentation_issues turned into rules. Any finding fails the run.
# Terminal words that signal a rejoin failure (a wrapped label cut mid-phrase).
# "in" and "with" are omitted from the terminal test because this verbatim corpus
# legitimately closes phrasal verbs with them ("effluent treatment built in",
# "one community group to work with"); a string ending in real sentence
# punctuation or a colon (a list-introducing header) is also treated as complete.
_DANGLE = {"of", "and", "the", "for", "to", "vs", "among"}
_COMPLETE_END = (".", "!", "?", ":", ")")


def block_strings(b):
    """Every human-readable string a block carries (for role/icon inference and
    for the integrity scans). Kept exhaustive so no field escapes the checks."""
    t = b.get("type")
    out = []
    if t == "p":
        out = [b.get("text", "")]
    elif t == "callout":
        out = [b.get("label", ""), b.get("text", "")]
    elif t == "quote":
        out = [b.get("text", ""), b.get("attribution", "")]
    elif t == "stats":
        for it in b.get("items", []):
            out += [it.get("value", ""), it.get("label", ""), it.get("qualifier", "")]
        out.append(b.get("footnote", ""))
    elif t in ("cards", "steps"):
        for it in b.get("items", []):
            out += [it.get("title", ""), it.get("body", "")]
    elif t == "list":
        out = [b.get("title", "")] + list(b.get("items", []))
    elif t == "chips":
        out = list(b.get("items", []))
    elif t == "pairs":
        for it in b.get("items", []):
            out += [it.get("term", ""), it.get("desc", "")]
    elif t == "flow":
        for s in b.get("stages", []):
            out += [s.get("name", ""), s.get("desc", "")]
        out.append(b.get("closing", ""))
    elif t == "phases":
        for g in b.get("groups", []):
            out += [g.get("label", ""), g.get("name", ""), g.get("period", "")]
            out += list(g.get("tasks", []))
    elif t == "timeline":
        for it in b.get("items", []):
            out += [it.get("period", ""), it.get("title", ""), it.get("desc", "")]
    elif t == "table":
        out += [str(c) for c in b.get("cols", [])]
        for row in b.get("rows", []):
            out += [str(c) for c in row]
        out.append(b.get("footnote", ""))
    elif t == "compare":
        for c in b.get("cols", []):
            out.append(c.get("title", ""))
            out += list(c.get("items", []))
    elif t == "groups":
        for g in b.get("groups", []):
            out.append(g.get("name", ""))
            for x in g.get("items", []):
                out += [x.get("term", ""), x.get("desc", "")] if isinstance(x, dict) else [x]
    elif t == "series":
        out = [b.get("unit", "")] + [p.get("label", "") for p in b.get("points", [])]
    elif t == "swot":
        for k in ("s", "w", "o", "t"):
            out += list(b.get(k, []))
    elif t == "hierarchy":
        for tier in b.get("tiers", []):
            out += [tier.get("level", ""), tier.get("name", ""), tier.get("desc", "")]
        out.append(b.get("closing", ""))
    elif t == "fanout":
        out.append(b.get("input", ""))
        for br in b.get("branches", []):
            out.append(br.get("component", ""))
            out += list(br.get("products", []))
    return [x for x in out if x]


def _last_word(s):
    trimmed = re.sub(r"[^0-9A-Za-z]+$", "", s.strip())
    parts = trimmed.split()
    return parts[-1].lower() if parts else ""


def check_deck(slug, content, html, findings):
    def add(msg):
        findings.append(slug + ": " + msg)

    for i, sec in enumerate(content.get("sections", []), start=1):
        if not (sec.get("title") or sec.get("kicker")):
            add("section %d has neither title nor kicker" % i)
        for b in sec.get("blocks", []):
            t = b.get("type")
            if t == "stats":
                for j, it in enumerate(b.get("items", []), start=1):
                    if not str(it.get("value", "")).strip():
                        add("stats item %d has empty value" % j)
                    if not str(it.get("label", "")).strip():
                        add("stats item %d has empty label" % j)
            elif t == "chips":
                for x in b.get("items", []):
                    if len(x) > 60:
                        add("chip over 60 chars: " + x[:50] + "...")
            elif t == "table":
                nc = len(b.get("cols", []))
                for r, row in enumerate(b.get("rows", []), start=1):
                    if len(row) != nc:
                        add("table row %d has %d cells, header has %d" % (r, len(row), nc))
            for s in block_strings(b):
                if s.rstrip().endswith(_COMPLETE_END):
                    continue
                if len(s.split()) >= 3 and _last_word(s) in _DANGLE:
                    add("string ends on dangling '%s': %s" % (_last_word(s), s[:64]))

    # rendered-HTML scans: no em dash survives to the page, no '›' token
    if "—" in html:
        add("em dash present in rendered HTML")
    if "›" in html:
        add("'›' present in rendered HTML")


def run_check():
    findings, checked = [], 0
    for m in B.META:
        slug = m["slug"]
        path = os.path.join(CONTENT_DIR, slug + ".json")
        if not os.path.exists(path):
            continue
        try:
            content = json.load(open(path, encoding="utf-8"))
        except (ValueError, OSError) as ex:
            findings.append(slug + ": invalid JSON (" + str(ex) + ")")
            continue
        try:
            html, _, _ = render(m, content)
        except Exception as ex:
            findings.append(slug + ": render error (" + str(ex) + ")")
            continue
        check_deck(slug, content, html, findings)
        checked += 1
    print("checked %d deck(s)" % checked)
    if findings:
        print("\nINTEGRITY FAILURES (%d):" % len(findings))
        for f in findings:
            print("  - " + f)
        return 1
    print("all integrity assertions passed")
    return 0


# ---------------------------------------------------------------- fixture / smoke
def _meta_for(slug):
    for m in B.META:
        if m.get("slug") == slug:
            return m
    return None


def _write_deck(m, content):
    html, n, _ = render(m, content)
    out = os.path.join(ROOT, "landing", "cases", m["slug"] + ".html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    secs = content.get("sections", [])
    roles = ",".join(sorted({role_for(sec_heading(s), sec_text(s)) for s in secs}))
    print("  %-30s %2d slides  [%s]" % (m["slug"], n, roles))
    return n


def build_fixture():
    """Render scripts/deck_content/_fixture.json (every block type) to the scratch
    dir, never to landing/cases, and sanity-check the HTML. Excluded from normal
    runs and --check because it is not in B.META."""
    fx = os.path.join(CONTENT_DIR, "_fixture.json")
    content = json.load(open(fx, encoding="utf-8"))
    m = {"slug": "_fixture", "title": content.get("title", "Fixture"),
         "eyebrow": content.get("eyebrow", ""), "summary": content.get("subtitle", ""),
         "place": "Fixture", "group": "model",
         "theme": content.get("_theme", "Manufacturing cluster"),
         "source": content.get("source_note")}
    html, n, _ = render(m, content)
    out = os.path.join(tempfile.gettempdir(), "proto_deck_fixture.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    findings = []
    check_deck("_fixture", content, html, findings)
    types = sorted({b.get("type") for sec in content["sections"] for b in sec.get("blocks", [])})
    print("fixture: %d slides, %d block types [%s]" % (n, len(types), ",".join(types)))
    print("fixture HTML -> " + out)
    if findings:
        print("FIXTURE INTEGRITY FAILURES (%d):" % len(findings))
        for f in findings:
            print("  - " + f)
        return 1
    print("fixture integrity assertions passed")
    return 0


def main():
    argv = sys.argv[1:]
    flags = [a for a in argv if a.startswith("-")]
    args = [a for a in argv if not a.startswith("-")]

    if "--check" in flags:
        sys.exit(run_check())
    if "--fixture" in flags:
        sys.exit(build_fixture())

    if args:                                   # one named deck (slug or filename)
        key = args[0]
        m = _meta_for(key) or next((x for x in B.META if x.get("file") == key), None)
        if not m:
            raise SystemExit("proto_deck: no META entry for '" + key + "'")
        _write_deck(m, load_content(m["slug"]))   # missing JSON is a hard error
        return

    # plain run: write a page for every slug whose JSON exists; skip an invalid
    # or mid-write file (real decks are authored concurrently) with a note. This
    # doubles as the smoke test over whatever valid decks are present.
    total = 0
    for m in B.META:
        slug = m["slug"]
        path = os.path.join(CONTENT_DIR, slug + ".json")
        if not os.path.exists(path):
            continue
        try:
            content = json.load(open(path, encoding="utf-8"))
        except (ValueError, OSError) as ex:
            print("  skip %-30s (invalid/mid-write JSON: %s)" % (slug, ex))
            continue
        try:
            _write_deck(m, content)
            total += 1
        except Exception as ex:
            print("  skip %-30s (render error: %s)" % (slug, ex))
    print("\nwrote %d deck page(s) -> landing/cases/" % total)


if __name__ == "__main__":
    main()
