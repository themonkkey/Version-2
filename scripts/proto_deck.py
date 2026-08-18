#!/usr/bin/env python3
"""PROTOTYPE — hybrid horizontal 'deck' reader for one case study.

Renders a single case (default: Morbi) to landing/cases/_proto-<slug>.html so the
new design can be judged before it touches the 13 live pages. Reuses the parser in
build_case_studies.py; only the presentation is new.

Design: each section is a full-viewport slide laid out horizontally. Left/right
arrows + keyboard + swipe move between slides (CSS-transform track, so it works
even where requestAnimationFrame is throttled). Content sits in a real
glassmorphism panel over a full-bleed background. Background is a theme-tinted
animated mesh gradient by default and auto-upgrades to a photo/video the moment
one is dropped at landing/cases/media/<slug>/coverN.(jpg|mp4). If a slide's
content is taller than the panel, the panel scrolls internally — never trapped.
On narrow screens the whole thing degrades to a vertical stack.

    python3 scripts/proto_deck.py [Morbi_Ceramics_Industry.txt]
"""
import re
import os
import sys

import build_case_studies as B

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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
        body = " ".join(str(x) for b in blocks for x in b[1:]).lower()
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
    "factory": '<path d="M3 21V10l6 4V10l6 4V7l6 3v11z"/><path d="M7 21v-3M13 21v-3M18 21v-3"/>',
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
                 "industr", "machin", "capacity build")),
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
    return ('<span class="' + cls + '" aria-hidden="true"><svg viewBox="0 0 24 24">'
            '<use href="#i-' + icon_for(text) + '"/></svg></span>')


ICON_SPRITE = ('<svg class="sprite" aria-hidden="true"><defs>'
               + "".join('<g id="i-' + k + '">' + v + '</g>' for k, v in ICONS.items())
               + '</defs></svg>')


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


e = B.e


def block_html(b):
    if b[0] == "entry":
        _, term, head, body = b
        # the term column collapses when empty: series_run borrows a trailing
        # period out of an entry and would otherwise leave a blank indent
        return ('<div class="entry' + ('' if term else ' noterm') + '">'
                '<div class="term">' + e(term) + '</div>'
                '<div><p class="eh">' + e(head) + '</p><p class="eb">' + e(body) + '</p></div></div>')
    if b[0] == "h3":
        return '<h3>' + e(b[1]) + '</h3>'
    if b[0] == "k":
        return '<p class="k">' + e(b[1]) + '</p>'
    return '<p>' + e(b[1]) + '</p>'


def grid_html(cells):
    inner = "".join('<div class="cell"><div class="v">' + e(v) + '</div>'
                    '<div class="l">' + e(l) + '</div></div>' for v, l in cells)
    return '<div class="grid">' + inner + '</div>'


def card_run(blocks, i):
    """Collect a run of consecutive 'h3 + its prose' units starting at i.

    Returns (units, next_i) where each unit is (heading, [paragraphs]). A unit
    ends at the next h3 or at anything that is not prose, so a stat grid or a
    timeline entry still breaks the run and renders in its own right.
    """
    units, j = [], i
    while j < len(blocks) and blocks[j][0] == "h3":
        head, j = blocks[j][1], j + 1
        paras = []
        while j < len(blocks) and blocks[j][0] == "p":
            paras.append(blocks[j][1])
            j += 1
        units.append((head, paras))
    return units, j


def cards_html(units):
    """A run of sub-headings becomes a card grid, not a vertical list.

    WHY: the decks carry these as peer items - four success factors, three
    constraints - and stacking them as h3/p/h3/p reads as one long column that
    hides the fact they are parallel. The grid is the SWOT/objectives layout from
    the PIF deck template, restyled in the case-study palette. Runs of one are
    left alone: a lone sub-heading is a section lead-in, not a card.
    """
    cells = []
    for head, paras in units:
        body = "".join('<p>' + e(t) + '</p>' for t in paras)
        cells.append('<div class="card">'
                     + icon_html(head if icon_for(head) != "spark"
                                 else head + " " + " ".join(paras))
                     + '<h3>' + e(head) + '</h3>' + body + '</div>')
    return '<div class="cards">' + "".join(cells) + '</div>'


def chips_html(items):
    """Runs of the parser's leftover short lines, laid out as equal chips.

    These arrive as orphan emphasis lines. They often LOOK like label/value pairs
    but the run length is not reliably even, so nothing is paired up here - that
    would be inventing structure the source does not carry.
    """
    return ('<div class="chips">'
            + "".join('<div class="chip">' + icon_html(t, "ic sm") + '<span>'
                      + e(t) + '</span></div>' for t in items)
            + '</div>')


def step_run(blocks, i):
    """Collect label-less stats that are each explained by the prose after them.

    parse_deck emits a bare ('stat', '2005', '') for a year or milestone figure,
    then the sentence about it as a separate paragraph. Rendered literally that is
    a full-width number card with an orphan line underneath - the single ugliest
    thing in these decks. Pairing them back up is what lets the timeline layout
    below exist at all.
    """
    units, j = [], i
    while j < len(blocks) and blocks[j][0] == "stat" and not blocks[j][2]:
        val, j = blocks[j][1], j + 1
        body = []
        while j < len(blocks) and blocks[j][0] in ("p", "k"):
            body.append(blocks[j][1])
            j += 1
        if not body:
            return units, j - 1 if units else i   # a bare figure: leave it to the grid
        units.append((val, body))
    return units, j


def steps_html(units):
    """Horizontal timeline, after the deck template's milestone-band layout.

    A run of dated milestones reads as a sequence, so it is laid out as one - the
    figures on a shared rail, each with its own text beneath. One unit is not a
    sequence, so it renders as a single figure beside its text instead of a lone
    band across the slide.
    """
    if len(units) == 1:
        val, body = units[0]
        return ('<div class="statnote"><div class="statnote-v">' + e(val) + '</div>'
                '<div class="statnote-b">'
                + "".join('<p>' + e(t) + '</p>' for t in body)
                + '</div></div>')
    cells = []
    for val, body in units:
        cells.append('<div class="step"><div class="step-v">' + e(val) + '</div>'
                     '<div class="step-b">'
                     + "".join('<p>' + e(t) + '</p>' for t in body)
                     + '</div></div>')
    return '<div class="steps">' + "".join(cells) + '</div>'


PERIOD = re.compile(r"^(?:FY\s*)?\d{4}\s*[-\u2013/]\s*\d{2,4}$")


def _num(v):
    """Parse a stat value to a float, or None if it is not a plain number."""
    t = (v or "").replace(",", "").strip()
    try:
        return float(t)
    except ValueError:
        return None


def series_run(blocks, i):
    """Recover a chart that the source flattened into a column of figures.

    The deck text prints a table as every VALUE in order, then every PERIOD in
    order, so the parser sees ~16 unrelated stats and lays them out as a grid of
    tiles - values and years jumbled together with no way to tell which belongs
    to which. Reading them back as one series is the only way that slide makes
    sense.

    The pairing is positional, which is exactly how the source printed them, and
    it only fires when the two runs are the same length. The one allowance is a
    trailing period that parse_deck swallowed into an 'entry' (its heading looked
    like a term), which is why the final year can come from the block after the
    run.

    Returns (labels, values, unit, next_i) or None.
    """
    j, vals, unit = i, [], ""
    while j < len(blocks) and blocks[j][0] == "stat" and _num(blocks[j][1]) is not None \
            and not PERIOD.match(blocks[j][1]):
        vals.append(_num(blocks[j][1]))
        if blocks[j][2]:
            unit = blocks[j][2]
        j += 1
    periods = []
    while j < len(blocks) and blocks[j][0] == "stat" and PERIOD.match(blocks[j][1]):
        periods.append(blocks[j][1])
        j += 1
    if len(vals) < 3 or not periods:
        return None
    if len(vals) == len(periods) + 1 and j < len(blocks) and blocks[j][0] == "entry" \
            and PERIOD.match(blocks[j][1]):
        periods.append(blocks[j][1])
        # the entry's prose is real content: leave the block in place, take only
        # its term, and rewrite it so the term is not printed twice
        blocks[j] = ("entry", "", blocks[j][2], blocks[j][3])
    if len(vals) != len(periods):
        return None
    return periods, vals, unit, j


def chart_html(periods, vals, unit):
    """Column chart, drawn from the recovered series. Bars are scaled to the
    largest value; every bar still prints its own figure, so nothing depends on
    reading the height."""
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


def render_blocks(blocks):
    out, i = [], 0
    while i < len(blocks):
        kind = blocks[i][0]

        if kind == "stat":
            ser = series_run(blocks, i)
            if ser:
                periods, vals, unit, j = ser
                out.append(chart_html(periods, vals, unit))
                i = j
                continue

            units, j = step_run(blocks, i)
            if units:
                out.append(steps_html(units))
                i = j
                continue
            run = []
            while i < len(blocks) and blocks[i][0] == "stat":
                run.append((blocks[i][1], blocks[i][2]))
                i += 1
            out.append(grid_html(run))
            continue

        if kind == "h3":
            units, j = card_run(blocks, i)
            if len(units) >= 2:
                out.append(cards_html(units))
                i = j
                continue

        if kind == "k":
            run = []
            while i < len(blocks) and blocks[i][0] == "k":
                run.append(blocks[i][1])
                i += 1
            out.append(chips_html(run) if len(run) >= 2 else '<p class="k">' + e(run[0]) + '</p>')
            continue

        out.append(block_html(blocks[i]))
        i += 1
    return "\n".join(out)


def slides_html(m, hero, secs):
    slides = []

    # cover slide
    tags = ['<span class="tag place">' + e(m["place"]) + "</span>"] if m.get("place") else []
    if m.get("theme"):
        tags.append('<span class="tag">' + e(m["theme"]) + "</span>")
    tags.append('<span class="tag">'
                + ("Andhra Pradesh district" if m["group"] == "ap" else "Replicable model")
                + "</span>")
    herohtml = ""
    if hero:
        cells = "".join('<div class="scell"><div class="v">' + e(v) + '</div>'
                        '<div class="l">' + e(l) + '</div></div>' for v, l in hero)
        herohtml = '<div class="hero">' + cells + '</div>'
    cover = (
        '<section class="slide cover" data-i="0">'
        '<div class="media" data-media="0" data-role="cover"></div>'
        '<div class="glass cover-glass reveal-root">'
        '<div class="cover-l">'
        '<p class="eyebrow r">' + e(m["eyebrow"]) + '</p>'
        '<h1 class="r">' + e(m["title"]) + '</h1>'
        '<p class="summary r">' + e(m["summary"]) + '</p>'
        '<div class="meta r">' + "".join(tags) + '</div>'
        '</div>'
        '<div class="cover-r r">' + herohtml + '</div>'
        '<p class="hint r">Use ← → or the arrows to move through the story</p>'
        '</div></section>')
    slides.append(cover)

    for idx, s in enumerate(secs, start=1):
        body = render_blocks(s["blocks"])
        slides.append(
            '<section class="slide" data-i="' + str(idx) + '">'
            '<div class="media" data-media="' + str(idx) + '" data-role="'
            + role_for(s["title"], s["blocks"]) + '"></div>'
            '<div class="glass reveal-root">'
            '<div class="sechead r"><span class="secnum">' + f"{idx:02d}" + '</span>'
            + icon_html(s["title"] or "", "ic lg")
            + '<h2>' + e(s["title"] or "Overview") + '</h2></div>'
            '<div class="secbody r">' + body + '</div>'
            '</div></section>')
    return slides


TMPL = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%%TITLE%% — Swarna Andhra case study</title>
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
     is #6FA817 — a yellow-green — so the whole stage read olive rather than the
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
  .cover-glass{display:grid;grid-template-columns:1.35fr .85fr;
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

.sechead{display:flex;align-items:baseline;gap:14px;margin:0 0 20px;
  padding-bottom:14px;border-bottom:1px solid var(--line);}
.sechead h2 .cont{font-size:.5em;font-weight:600;letter-spacing:.08em;
  text-transform:uppercase;color:var(--mut2);vertical-align:middle;margin-left:6px;}
.secnum{font-family:'Trebuchet MS','Verdana Pro',Verdana,sans-serif;font-weight:600;font-size:16px;color:var(--t2);
  letter-spacing:.04em;}
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
.scell .l,.cell .l{margin-top:7px;font-size:12.5px;line-height:1.4;color:var(--mut);font-weight:600;}

/* icons: inline sprite, tinted by the slide accent, in a soft disc so they read
   against both the mesh gradient and a photo background */
.sprite{display:none;}
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
.card p{margin:0 0 8px;font-size:14px;line-height:1.55;max-width:none;}
.card p:last-child{margin-bottom:0;}

/* chips - the parser's leftover emphasis lines, laid out as peers not a column */
.chips{display:grid;gap:10px;margin:14px 0 18px;
  grid-template-columns:repeat(auto-fit,minmax(220px,1fr));}
.chip{background:var(--glass2);border:1px solid var(--line);border-left:3px solid var(--t2);
  border-radius:10px;padding:11px 14px;font-size:13.5px;font-weight:600;
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
.step-b p{margin:0 0 7px;font-size:13.5px;line-height:1.55;color:var(--mut);max-width:none;}
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
.entry .eb{margin:0;font-size:14px;color:var(--mut);line-height:1.55;}

/* ---------- chrome: arrows, dots, progress, back ---------- */
.nav{position:fixed;top:50%;transform:translateY(-50%);z-index:30;
  width:52px;height:52px;border-radius:50%;display:grid;place-items:center;cursor:pointer;
  background:var(--glass);border:1px solid var(--line);color:var(--fg);
  -webkit-backdrop-filter:blur(14px);backdrop-filter:blur(14px);
  transition:transform .2s ease,background .2s ease,opacity .2s ease;user-select:none;}
.nav:hover{background:color-mix(in srgb,var(--t1) 30%,var(--glass));transform:translateY(-50%) scale(1.07);}
.nav.prev{left:clamp(12px,2.5vw,30px);}
.nav.next{right:clamp(12px,2.5vw,30px);}
.nav[disabled]{opacity:.3;pointer-events:none;}
.nav svg{width:20px;height:20px;}
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
<div class="nav prev" id="prev" aria-label="Previous"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg></div>
<div class="nav next" id="next" aria-label="Next"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18l6-6-6-6"/></svg></div>
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
      kids.forEach(function(k){
        pbody.appendChild(k);
        var g=page.querySelector('.glass');
        if(g.scrollHeight<=g.clientHeight+2) return;
        // A single block taller than the panel cannot be broken further. Leave it
        // where it is and let that one page scroll, rather than loop forever.
        if(pbody.children.length===1) return;
        pbody.removeChild(k);
        page=newPage(sl);
        out.push(page);
        pbody=page.querySelector('.secbody');
        pbody.appendChild(k);
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
  function layout(){
  try{ paginate(); }catch(err){ /* never let layout maths kill the deck */ }

  slides.forEach(function(sl){
    var m=sl.querySelector('.media'); if(!m) return;
    var i=m.getAttribute('data-media'), role=m.getAttribute('data-role');
    tryAsset(m, [
      'media/'+SLUG+'/'+i+'.mp4', 'media/'+SLUG+'/'+i+'.gif', 'media/'+SLUG+'/'+i+'.jpg',
      'media/common/'+role+'.mp4', 'media/common/'+role+'.gif', 'media/common/'+role+'.jpg'
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
  // Wheel: horizontal intent, or vertical when the panel isn't scrollable.
  // A trackpad swipe is not one event — macOS momentum fires dozens over ~1s. A
  // plain time lock still let 2-3 of them through per swipe, so instead the
  // gesture must fully SETTLE (no wheel events for 240ms) before another advance
  // is armed. One physical swipe therefore moves exactly one slide.
  var wheelArmed=true, wheelTimer=null;
  addEventListener('wheel',function(ev){
    if(mobile()) return;
    var g=slides[cur].querySelector('.glass');
    var canScroll=g && g.scrollHeight>g.clientHeight+2;
    var dom=Math.abs(ev.deltaX)>Math.abs(ev.deltaY)?ev.deltaX:ev.deltaY;
    if(canScroll && Math.abs(ev.deltaY)>Math.abs(ev.deltaX)){
      var atTop=g.scrollTop<=0, atBot=g.scrollTop+g.clientHeight>=g.scrollHeight-1;
      if(!(atTop&&dom<0)&&!(atBot&&dom>0)) return; // let the panel scroll
    }
    clearTimeout(wheelTimer);
    wheelTimer=setTimeout(function(){ wheelArmed=true; }, 240);
    if(!wheelArmed || Math.abs(dom)<28) return;
    wheelArmed=false;
    step(dom>0?1:-1);
  },{passive:true});
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


def render(m):
    hero, blocks = B.parse_deck(os.path.join(B.SRC, m["file"]))
    secs = sections_of(blocks)
    slides = slides_html(m, hero, secs)
    t1, t2 = tint_for(m)
    src = ('<p class="src">' + e(m["source"]) + "</p>") if m.get("source") else ""
    html = (TMPL
            .replace("%%TITLE%%", e(m["title"]))
            .replace("%%TINT1%%", t1).replace("%%TINT2%%", t2)
            .replace("%%COUNT%%", f"{len(slides):02d}")
            .replace("%%SLUG%%", m["slug"])
            .replace("%%SPRITE%%", ICON_SPRITE)
            .replace("%%SOURCE%%", src)
            .replace("%%SLIDES%%", "\n".join(slides)))
    return html, len(slides), secs


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    proto = "--proto" in sys.argv

    if args:                                   # one named deck
        targets = [next(x for x in B.META if x["file"] == args[0])]
    else:                                      # all 13
        targets = list(B.META)

    total = 0
    for m in targets:
        html, n, secs = render(m)
        name = ("_proto-" + m["slug"] if proto else m["slug"]) + ".html"
        out = os.path.join(ROOT, "landing", "cases", name)
        with open(out, "w", encoding="utf-8") as f:
            f.write(html)
        roles = ",".join(sorted({role_for(s["title"], s["blocks"]) for s in secs}))
        print(f"  {m['slug']:30s} {n:2d} slides  [{roles}]")
        total += 1
    print(f"\nwrote {total} deck page(s) -> landing/cases/")


if __name__ == "__main__":
    main()
