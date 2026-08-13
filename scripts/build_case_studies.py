#!/usr/bin/env python3
"""Turn the capacity-building case-study text files into a browsable library.

Source: corpus_files/case_studies/*.txt — each is a training deck (originally an
HTML slide deck) flattened to text. They start with a "# index.html" line, carry
an eyebrow / title / summary header block, then numbered sections, and repeat a
"Capacity building programme | Government of Andhra Pradesh" footer plus bare
slide-number lines on every slide.

Two outputs, mirroring how the Documents tab is fed:
  landing/assets/case_studies.json   — the card manifest the Case studies tab renders
  landing/cases/<slug>.html          — one standalone, self-contained reader page
                                       per study, opened in a new tab

CARD METADATA IS CURATED, NOT SCRAPED. The eyebrow/title/summary/theme/group for
each of the 13 is written by hand in META below and verified against the file,
because the card face is government-facing and the flattened decks are too
inconsistent to parse a clean title from reliably. The BODY is cleaned
automatically (boilerplate and slide numbers dropped, backslash-escapes undone,
headings detected) — faithful to what's in the file, just legible.

    python3 scripts/build_case_studies.py
"""
import html
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "corpus_files", "case_studies")
MANIFEST = os.path.join(ROOT, "landing", "assets", "case_studies.json")
PAGES_DIR = os.path.join(ROOT, "landing", "cases")

# group 'ap'    — a case-for-action for a named Andhra Pradesh district
# group 'model' — a replicable model / reference from elsewhere
# district — the dashboard_index.json key, so a card can deep-link the map later.
META = [
    {
        "file": "East_Godavari_Coconut_Coir.txt", "slug": "east-godavari-coconut-coir",
        "group": "ap", "district": "East_Godavari", "place": "East Godavari",
        "theme": "Agri value chain",
        "eyebrow": "Value-chain strategy",
        "title": "Unlocking East Godavari's Coconut & Coir Potential",
        "summary": "From a coconut-growing district to a diversified processing hub — coir, "
                   "activated carbon and beyond.",
    },
    {
        "file": "Nellore_Shrimp_Processing.txt", "slug": "nellore-shrimp-processing",
        "group": "ap", "district": "Sps_Nellore", "place": "SPSR Nellore",
        "theme": "Aquaculture",
        "eyebrow": "Value-chain strategy",
        "title": "Unlocking Nellore's Shrimp Processing Potential",
        "summary": "From aquaculture capital to value-addition hub — why the district must "
                   "move up the shrimp chain.",
    },
    {
        "file": "Nellore_Ethanol_Potential.txt", "slug": "nellore-ethanol-potential",
        "group": "ap", "district": "Sps_Nellore", "place": "SPSR Nellore",
        "theme": "Ethanol / investment",
        "eyebrow": "Investment potential",
        "title": "Unlocking Nellore's Ethanol Opportunity",
        "summary": "Feedstock, infrastructure and the road to E20 — what the National Ethanol "
                   "Blending Programme means for the district.",
    },
    {
        "file": "Srikakulam_Blue_Economy.txt", "slug": "srikakulam-blue-economy",
        "group": "ap", "district": "Srikakulam", "place": "Srikakulam",
        "theme": "Blue economy",
        "eyebrow": "Blue economy strategy",
        "title": "Unlocking Srikakulam's Blue Economy Potential",
        "summary": "From a coastal aquaculture belt to a diversified seafood processing hub — "
                   "shrimp, fish and marine value-added products.",
    },
    {
        "file": "Shenzhen_Port_Led_Manufacturing.txt", "slug": "shenzhen-growth-model",
        "group": "model", "district": None, "place": "Shenzhen, China",
        "theme": "Port-led manufacturing",
        "eyebrow": "District administration training",
        "title": "Shenzhen's Economic Miracle",
        "summary": "A strategic framework for district-level economic planning, drawn from "
                   "Shenzhen's port-led industrial rise.",
        "source": "Based on: Liu (2025), Development Model of Coastal Cities — A Case Study of "
                  "Shenzhen, MMET 2025.",
    },
    {
        "file": "Morbi_Ceramics_Industry.txt", "slug": "morbi-ceramic-cluster",
        "group": "model", "district": None, "place": "Morbi, Gujarat",
        "theme": "Manufacturing cluster",
        "eyebrow": "Industrial cluster",
        "title": "The Morbi Ceramic Cluster",
        "summary": "How a traditional craft town became the world's #2 ceramic tile producer — "
                   "and what a cluster's collective reinvention takes.",
    },
    {
        "file": "Tiruppur_Case_Study_Updated.txt", "slug": "tiruppur-textiles",
        "group": "model", "district": None, "place": "Tiruppur, Tamil Nadu",
        "theme": "Textiles cluster",
        "eyebrow": "Industrial cluster",
        "title": "Tiruppur: Innovation in Textiles & Garments",
        "summary": "The rise of South India's “Banian City” — a knitwear cluster that "
                   "moved from job-work to a global export base.",
    },
    {
        "file": "Kumarakom_Responsible_Tourism_Case_Study.txt", "slug": "kumarakom-tourism",
        "group": "model", "district": None, "place": "Kumarakom, Kerala",
        "theme": "Responsible tourism",
        "eyebrow": "Responsible tourism",
        "title": "The Kumarakom Responsible Tourism Model",
        "summary": "How a destination-level partnership linked tourism demand with local "
                   "livelihoods, culture and conservation.",
    },
    {
        "file": "Sahyadri_Replication_Playbook.txt", "slug": "sahyadri-farms-fpc",
        "group": "model", "district": None, "place": "Nashik, Maharashtra",
        "theme": "FPC / supply chain",
        "eyebrow": "Replication playbook",
        "title": "Sahyadri Farms: Smallholders in an Integrated Supply Chain",
        "summary": "What the Sahyadri Farms (FPC) model means for our mandals and districts.",
    },
    {
        "file": "Chetna_FPO_Lessons.txt", "slug": "chetna-organics-fpo",
        "group": "model", "district": None, "place": "Central India",
        "theme": "FPO strengthening",
        "eyebrow": "Farmer producer organisations",
        "title": "Chetna Organics: Building a Farmer-Owned Supply Chain",
        "summary": "What mandal officers can learn from an organic-cotton FPO to strengthen "
                   "their own producer organisations.",
    },
    {
        "file": "Biofloc_Tilapia_CaseStudy.txt", "slug": "biofloc-tilapia",
        "group": "model", "district": None, "place": "CMFRI, Kerala",
        "theme": "Aquaculture livelihoods",
        "eyebrow": "Rural livelihoods training",
        "title": "Biofloc Tilapia Farming",
        "summary": "A replicable model for mandal-level income generation, based on CMFRI's "
                   "Scheduled Caste Sub-Plan initiative.",
    },
    {
        "file": "Paddy_Fish_Integrated_Farming_Case_Study_AP.txt", "slug": "paddy-fish-farming",
        "group": "model", "district": None, "place": "India & China models",
        "theme": "Integrated farming",
        "eyebrow": "Models & roadmap",
        "title": "Paddy + Fish Integrated Farming",
        "summary": "Successful models from India and China, and a practical roadmap for "
                   "paddy-growing districts of Andhra Pradesh.",
    },
    {
        "file": "Banana_Processing_Case_Study.txt", "slug": "banana-processing",
        "group": "model", "district": None, "place": "Kanyakumari & Jalgaon",
        "theme": "Agro-processing",
        "eyebrow": "Two replicable cases",
        "title": "Banana Processing & Waste-to-Wealth Models",
        "summary": "Two replicable cases — KVK Kanyakumari value-added foods and the Jalgaon "
                   "pseudo-stem processing cluster.",
    },
]

BOILERPLATE = re.compile(
    # the "# index.html" flatten marker, and the per-slide running footer in all
    # its forms — bare, or prefixed with the deck name and a bullet, e.g.
    # "Nellore Ethanol Opportunity • Capacity building programme | Government…"
    r"^(#\s*index\.html\s*"
    r"|.*Capacity building programme \| Government of Andhra Pradesh)\s*$",
    re.IGNORECASE,
)


def unescape(s):
    # the decks came through a markdown step that escaped these
    return (s.replace("\\#", "#").replace("\\~", "~").replace("\\-", "-")
             .replace("\\*", "*").replace("\\&", "&").replace("\\.", "."))


def is_heading(line):
    """A short, title-ish line with no terminal sentence punctuation."""
    if len(line) > 72 or line.endswith((".", ",", ":", ";")):
        return False
    words = line.split()
    if not words:
        return False
    if line.isupper():
        return True
    # Title Case: most words start uppercase (allow small joining words)
    small = {"a", "an", "the", "of", "for", "to", "and", "or", "in", "on", "at",
             "vs", "vs.", "&", "—", "–", "-"}
    caps = sum(1 for w in words if w[0].isupper() or not w[0].isalpha())
    lead = [w for w in words if w.lower() not in small]
    return bool(lead) and caps >= max(1, int(len(words) * 0.6))


def is_prose(text):
    """A real paragraph: long, or ends like a sentence."""
    return len(text) > 72 or text.endswith((".", "!", "?"))


def is_section_title(line):
    """A deck's big section header — an ALL-CAPS multi-word banner line.

    'EVOLUTION OF THE INDUSTRY', 'GLOBAL STANDING', 'THE GLOBAL & POLICY CONTEXT'.
    Kept strict (all upper, >=2 words, not a stat) so ordinary Title-Case
    sub-headings stay h3 and stat values like '45M+' never promote.
    """
    if len(line) > 60 or not line.isupper():
        return False
    words = [w for w in line.split() if any(c.isalpha() for c in w)]
    return len(words) >= 2


def is_value(line):
    """A stat's headline value: '#2', '80–90%', 'Rs 46,000 Cr', '4th', '45M+'.

    Short, and leads with a number or a currency/rank marker. This is what lets a
    flattened deck tell a stat card from a sub-heading — the thing the old
    ' · '-joined keyline hack could not do.
    """
    if len(line) > 22:
        return False
    if re.match(r"^[#~<>≈]?\s*[\d]", line):          # #2, ~100 yrs, 80–90%, 20,000
        return True
    if re.match(r"^(rs\.?|₹|\$|€)\s*[\d]", line, re.IGNORECASE):  # Rs 46,000 Cr
        return True
    if re.match(r"^\d+\s*(st|nd|rd|th)\b", line, re.IGNORECASE):  # 4th
        return True
    return False


def short_label(line):
    return 0 < len(line) <= 46 and not is_prose(line) and not is_section_title(line)


def heading_like(line):
    """A short line that reads as a heading by POSITION, not capitalisation.

    is_heading() demands title-case, so it misses sentence-case section heads the
    decks use freely ('The raw-nut & loose-husk trap'). This is the looser,
    structural test the classifier uses to place h2/h3: short, not a paragraph,
    not a stat value, has letters, and doesn't trail off with sentence/list
    punctuation.
    """
    if not line or len(line) > 72 or line.endswith((".", ",", ":", ";", "!", "?")):
        return False
    return not is_prose(line) and not is_value(line) and any(c.isalpha() for c in line)


def take_stat(kept, i):
    """Consume a value line + up to two short label lines starting at i.

    Returns (value, label, j) where j is the index past what was consumed. Used
    for both the hero band and in-body stat runs.
    """
    labels = []
    j = i + 1
    while (j < len(kept) and len(labels) < 2 and short_label(kept[j])
           and not is_value(kept[j])):
        labels.append(kept[j])
        j += 1
    return kept[i], " ".join(labels), j


def clean_lines(raw):
    out = []
    for ln in raw:
        s = unescape(ln).strip()
        if not s or BOILERPLATE.match(s) or re.fullmatch(r"\d{1,2}", s):
            continue
        out.append(s)
    return out


def parse_deck(path):
    """Parse the deck into structured blocks that a real template can render.

    The decks are HTML slide decks flattened to text, so their structure survives
    as line rhythm rather than markup. Reconstructed conservatively — anything not
    confidently a stat/entry/heading falls back to prose, so the worst case ties
    the old flat render, never invents structure that is not in the file.

    Returns (hero_stats, blocks):
      hero_stats — [(value, label)] pulled from the cover slide, e.g.
                   ('#2', 'Global Producer'). These were thrown away before.
      blocks — ordered, each one of:
        ('h2', title)                  section banner (ALL-CAPS deck header)
        ('h3', title)                  sub-heading (Title-Case + following prose)
        ('stat', value, label)         a big-number card (grouped into a grid at render)
        ('entry', term, heading, body) a timeline / definition row: period + head + prose
        ('p', text)                    paragraph
        ('k', text)                    leftover short line (rare; emphasis)
    """
    with open(path, encoding="utf-8") as f:
        raw = [ln.rstrip() for ln in f]

    # the cover slide ends at the first bare '1'. Its stats were dropped before;
    # keep them for the hero band. The title/eyebrow/summary stay curated.
    cut = len(raw)
    for i, ln in enumerate(raw):
        if re.fullmatch(r"\s*1\s*", ln):
            cut = i
            break

    cover = clean_lines(raw[:cut])
    hero = []
    i = 0
    while i < len(cover):
        if is_value(cover[i]):
            v, lab, j = take_stat(cover, i)
            hero.append((v, lab))
            i = j
        else:
            i += 1

    kept = clean_lines(raw[cut + 1:])
    blocks = []
    i = 0
    while i < len(kept):
        s = kept[i]
        nxt = kept[i + 1] if i + 1 < len(kept) else ""
        if is_section_title(s):
            blocks.append(("h2", s))
            i += 1
        elif is_value(s):
            v, lab, j = take_stat(kept, i)
            after = kept[j] if j < len(kept) else ""
            if lab and is_prose(after):
                # value + short head + prose = a timeline / definition entry,
                # e.g. '1980s–90s' / 'First Major Shift' / 'Transition from…'
                blocks.append(("entry", v, lab, after))
                i = j + 1
            else:
                blocks.append(("stat", v, lab))
                i = j
        elif heading_like(s):
            nxt2 = kept[i + 2] if i + 2 < len(kept) else ""
            if len(s) <= 16 and heading_like(nxt) and is_prose(nxt2):
                # a tight period/label + heading + prose is a timeline row, even
                # when the label isn't numeric ('Pre-1980s' / 'Traditional Craft
                # Origins' / prose) — keeps a timeline visually uniform.
                blocks.append(("entry", s, nxt, nxt2))
                i += 3
            elif is_prose(nxt):
                # heading immediately followed by its paragraph = a sub-heading
                blocks.append(("h3", s))
                i += 1
            elif is_heading(s) and heading_like(nxt) and is_prose(nxt2):
                # a deliberate TITLE-CASE line that introduces a sub-heading+prose
                # is a SECTION head, e.g. 'The Problem We Are Trying to Solve' →
                # 'The raw-nut & loose-husk trap' → prose. Gated on is_heading (not
                # the looser heading_like) so dense 'short / short / prose' lists
                # don't each mint a false banner.
                blocks.append(("h2", s))
                i += 1
            else:
                blocks.append(("k", s))
                i += 1
        elif is_prose(s):
            blocks.append(("p", s))
            i += 1
        else:
            blocks.append(("k", s))
            i += 1

    # drop adjacent exact dupes (repeated banners across slides)
    out = []
    for b in blocks:
        if out and out[-1] == b:
            continue
        out.append(b)
    return hero, out


PAGE_TMPL = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — Swarna Andhra case study</title>
<script>
/* Arm entrance animations before first paint so hidden-then-reveal never flashes.
   Only when motion is welcome AND IntersectionObserver exists; otherwise the page
   stays fully visible and the GSAP layer below is skipped. */
(function(){{
  try{{
    var ok = !matchMedia('(prefers-reduced-motion: reduce)').matches
             && 'IntersectionObserver' in window;
    if(ok) document.documentElement.className += ' anim';
  }}catch(e){{}}
}})();
</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Bodoni+Moda:opsz,wght@6..96,500;6..96,600&family=Public+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{{--ink:#0B2E20;--ink2:#09281B;--panel:rgba(255,255,255,.05);--line:rgba(255,255,255,.14);
  --fg:#EAF2EC;--mut:rgba(234,242,236,.72);--mut2:rgba(234,242,236,.5);--lime:#C6EC8F;--lime2:#8FC93A;}}
*{{box-sizing:border-box;}}
body{{margin:0;background:var(--ink);color:var(--fg);
  font-family:'Public Sans',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  line-height:1.6;-webkit-font-smoothing:antialiased;}}
a{{color:var(--lime);}}
.wrap{{max-width:760px;margin:0 auto;padding:clamp(20px,5vw,44px) clamp(18px,5vw,28px) 80px;}}
.back{{display:inline-flex;align-items:center;gap:7px;font-size:13.5px;font-weight:600;
  color:var(--mut);text-decoration:none;margin-bottom:clamp(22px,4vw,34px);}}
.back:hover{{color:var(--lime);}}
.eyebrow{{font-size:12px;font-weight:700;letter-spacing:.09em;text-transform:uppercase;
  color:var(--lime2);margin:0 0 14px;}}
h1{{font-family:'Bodoni Moda',Georgia,serif;font-weight:600;font-size:clamp(28px,5.5vw,46px);
  line-height:1.08;letter-spacing:-.01em;margin:0 0 16px;}}
.summary{{font-size:clamp(16px,2vw,19px);color:var(--mut);margin:0 0 22px;max-width:60ch;}}
.meta{{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 8px;}}
.tag{{font-size:12px;font-weight:600;letter-spacing:.01em;padding:5px 11px;border-radius:999px;
  background:var(--panel);border:1px solid var(--line);color:var(--mut);}}
.tag.place{{color:var(--fg);}}
.src{{font-size:12.5px;color:var(--mut2);margin:14px 0 0;}}
hr{{border:none;border-top:1px solid var(--line);margin:clamp(26px,4vw,38px) 0;}}
/* hero stat band — the cover-slide numbers, restored */
.hero{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;
  margin:26px 0 4px;}}
.hero .cell{{background:linear-gradient(180deg,rgba(198,236,143,.10),rgba(198,236,143,.03));
  border:1px solid rgba(198,236,143,.22);border-radius:14px;padding:16px 16px 14px;}}
.hero .v{{font-family:'Bodoni Moda',Georgia,serif;font-weight:600;font-size:clamp(26px,4vw,34px);
  line-height:1;color:var(--lime);letter-spacing:-.01em;}}
.hero .l{{margin-top:8px;font-size:12.5px;font-weight:600;line-height:1.35;color:var(--mut);}}
.body h2{{font-family:'Bodoni Moda',Georgia,serif;font-weight:600;font-size:clamp(21px,3vw,27px);
  letter-spacing:-.01em;color:#fff;margin:40px 0 14px;padding-bottom:11px;
  border-bottom:1px solid var(--line);}}
.body h2:first-child{{margin-top:4px;}}
.body h3{{font-family:'Public Sans',sans-serif;font-weight:700;font-size:clamp(17px,2.2vw,21px);
  letter-spacing:-.008em;color:#fff;margin:30px 0 6px;}}
.body h3:first-child{{margin-top:0;}}
.body p{{margin:0 0 14px;color:var(--mut);}}
.body .k{{margin:18px 0 4px;font-weight:700;font-size:14px;letter-spacing:.005em;
  color:var(--lime2);}}
.body .k + h3{{margin-top:2px;}}
/* in-body stat grid */
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;
  margin:16px 0 22px;}}
.grid .cell{{background:var(--panel);border:1px solid var(--line);border-radius:13px;
  padding:15px 15px 13px;}}
.grid .v{{font-family:'Bodoni Moda',Georgia,serif;font-weight:600;font-size:clamp(23px,3.4vw,30px);
  line-height:1;color:var(--lime);}}
.grid .l{{margin-top:7px;font-size:12.5px;line-height:1.4;color:var(--mut);}}
/* timeline / definition entry */
.entry{{display:grid;grid-template-columns:minmax(94px,132px) 1fr;gap:16px;
  padding:15px 0;border-top:1px solid var(--line);}}
.entry:first-of-type{{border-top:none;}}
.entry .term{{font-weight:700;font-size:13.5px;color:var(--lime2);line-height:1.4;}}
.entry .eh{{font-weight:700;font-size:15.5px;color:#fff;margin:0 0 5px;}}
.entry .eb{{margin:0;font-size:14.5px;color:var(--mut);line-height:1.55;}}
@media(max-width:520px){{.entry{{grid-template-columns:1fr;gap:4px;}}}}
footer{{margin-top:52px;padding-top:20px;border-top:1px solid var(--line);
  font-size:12.5px;color:var(--mut2);}}
footer b{{color:var(--mut);font-weight:600;}}
/* ---- motion + interaction polish ---- */
/* initial hidden states, applied only while .anim is armed (see head script) */
.anim .eyebrow,.anim h1,.anim .summary,.anim .meta .tag,
.anim .hero .cell,.anim .body>*{{opacity:0;}}
.reading{{position:fixed;top:0;left:0;height:3px;width:0;z-index:20;
  background:linear-gradient(90deg,var(--lime2),var(--lime));
  box-shadow:0 0 12px rgba(198,236,143,.5);transition:width .12s linear;}}
.hero .cell,.grid .cell{{transition:transform .28s cubic-bezier(.2,.7,.2,1),
  border-color .28s ease,box-shadow .28s ease;will-change:transform;}}
.hero .cell:hover{{transform:translateY(-3px);border-color:rgba(198,236,143,.5);
  box-shadow:0 10px 30px -14px rgba(0,0,0,.6);}}
.grid .cell:hover{{transform:translateY(-3px);border-color:rgba(198,236,143,.38);
  box-shadow:0 10px 26px -16px rgba(0,0,0,.6);}}
.back{{transition:color .2s ease,gap .2s ease;}}
.back:hover{{gap:11px;}}
@media (prefers-reduced-motion: reduce){{
  *{{animation:none!important;transition:none!important;}}
  .anim .eyebrow,.anim h1,.anim .summary,.anim .meta .tag,
  .anim .hero .cell,.anim .body>*{{opacity:1;}}
}}
</style>
</head>
<body>
<div class="wrap">
  <a class="back" href="../index.html#districts">← Back to the case study library</a>
  <p class="eyebrow">{eyebrow}</p>
  <h1>{title}</h1>
  <p class="summary">{summary}</p>
  <div class="meta">{tags}</div>
  {source}
  {hero}
  <hr>
  <div class="body">
{body}
  </div>
  <footer>
    <b>Pahlé India Foundation</b> · Swarna Andhra @2047 capacity-building case study.
    Prepared for district &amp; mandal officers.
  </footer>
</div>
<div class="reading" aria-hidden="true"></div>
<script src="../assets/dash/gsap.js"></script>
<script>
(function(){{
  var root = document.documentElement;
  var armed = root.classList.contains('anim');
  var g = window.gsap;

  // Reading-progress bar runs regardless of the entrance-animation gate.
  var bar = document.querySelector('.reading');
  function onScroll(){{
    var max = root.scrollHeight - root.clientHeight;
    bar.style.width = (max > 0 ? (root.scrollTop / max) * 100 : 0) + '%';
  }}
  addEventListener('scroll', onScroll, {{passive:true}});
  onScroll();

  // If motion wasn't armed, or GSAP failed to load, reveal everything and stop —
  // the .anim class is what hides content, so removing it is the safe fallback.
  if(!armed || !g){{ root.classList.remove('anim'); return; }}

  g.ticker.lagSmoothing(0);         // don't let a throttled frame loop stall tweens
  g.config({{nullTargetWarn:false}});

  // rAF-health gate: entrance animations are driven by requestAnimationFrame. In a
  // backgrounded tab or some embedded preview panes the frame loop is paused, which
  // would leave .anim content hidden forever. Probe one frame; if it never ticks,
  // drop .anim (reveal all, no animation) rather than risk invisible content.
  var alive = false;
  requestAnimationFrame(function(){{ alive = true; }});
  setTimeout(function(){{
    if(!alive){{ root.classList.remove('anim'); return; }}

    g.timeline({{defaults:{{ease:'power3.out'}}}})
      .fromTo('.eyebrow',{{opacity:0,y:12}},{{opacity:1,y:0,duration:.5}})
      .fromTo('h1',{{opacity:0,y:24}},{{opacity:1,y:0,duration:.7}},'-=.28')
      .fromTo('.summary',{{opacity:0,y:16}},{{opacity:1,y:0,duration:.6}},'-=.46')
      .fromTo('.meta .tag',{{opacity:0,y:10}},{{opacity:1,y:0,duration:.4,stagger:.06}},'-=.34')
      .fromTo('.hero .cell',{{opacity:0,y:22}},{{opacity:1,y:0,duration:.55,stagger:.08}},'-=.24');

    // scroll-reveal each body block as it enters; stat grids stagger their cards
    var io = new IntersectionObserver(function(items){{
      items.forEach(function(en){{
        if(!en.isIntersecting) return;
        var el = en.target; io.unobserve(el);
        if(el.classList.contains('grid')){{
          g.set(el,{{opacity:1}});
          g.fromTo(el.children,{{opacity:0,y:18}},
            {{opacity:1,y:0,duration:.5,stagger:.06,ease:'power2.out'}});
        }} else {{
          g.fromTo(el,{{opacity:0,y:22}},{{opacity:1,y:0,duration:.6,ease:'power2.out'}});
        }}
      }});
    }},{{rootMargin:'0px 0px -8% 0px',threshold:.12}});
    document.querySelectorAll('.body > *').forEach(function(el){{ io.observe(el); }});
  }}, 260);
}})();
</script>
</body>
</html>
"""


def e(s):
    return html.escape(s, quote=True)


def render_hero(hero_stats):
    if not hero_stats:
        return ""
    cells = "".join(
        '<div class="cell"><div class="v">{v}</div><div class="l">{l}</div></div>'.format(
            v=e(v), l=e(l))
        for v, l in hero_stats)
    return '<div class="hero">' + cells + "</div>"


def render_body(blocks):
    """Emit HTML, grouping consecutive ('stat',…) blocks into one card grid."""
    out = []
    i = 0
    while i < len(blocks):
        b = blocks[i]
        if b[0] == "stat":
            run = []
            while i < len(blocks) and blocks[i][0] == "stat":
                run.append(blocks[i])
                i += 1
            cells = "".join(
                '<div class="cell"><div class="v">{v}</div><div class="l">{l}</div></div>'.format(
                    v=e(v), l=e(l))
                for _, v, l in run)
            out.append('    <div class="grid">' + cells + "</div>")
            continue
        if b[0] == "entry":
            _, term, head, body = b
            out.append(
                '    <div class="entry"><div class="term">{t}</div>'
                '<div><p class="eh">{h}</p><p class="eb">{b}</p></div></div>'.format(
                    t=e(term), h=e(head), b=e(body)))
        elif b[0] == "k":
            out.append('    <p class="k">' + e(b[1]) + "</p>")
        else:  # h2, h3, p
            out.append("    <{k}>{t}</{k}>".format(k=b[0], t=e(b[1])))
        i += 1
    return "\n".join(out)


def render_page(m, hero_stats, body_blocks):
    tags = ['<span class="tag place">' + e(m["place"]) + "</span>"] if m.get("place") else []
    if m.get("theme"):
        tags.append('<span class="tag">' + e(m["theme"]) + "</span>")
    tags.append('<span class="tag">'
                + ("Andhra Pradesh district" if m["group"] == "ap" else "Replicable model")
                + "</span>")
    src = '<p class="src">' + e(m["source"]) + "</p>" if m.get("source") else ""
    return PAGE_TMPL.format(
        title=e(m["title"]), eyebrow=e(m["eyebrow"]), summary=e(m["summary"]),
        tags="".join(tags), source=src, hero=render_hero(hero_stats),
        body=render_body(body_blocks),
    )


def main():
    os.makedirs(PAGES_DIR, exist_ok=True)
    manifest = {"ap": [], "model": []}
    written = 0

    for m in META:
        if m.get("_skip"):
            continue
        path = os.path.join(SRC, m["file"])
        if not os.path.exists(path):
            print("MISSING:", m["file"])
            continue
        hero, body = parse_deck(path)
        page = render_page(m, hero, body)
        with open(os.path.join(PAGES_DIR, m["slug"] + ".html"), "w", encoding="utf-8") as f:
            f.write(page)
        # If this case has a deck cover image, the library card reuses it as its
        # own background. Detected rather than declared, so any case that later
        # gains a 0.jpg picks it up on the next build with no edit here.
        cover_rel = os.path.join("cases", "media", m["slug"], "0.jpg")
        has_cover = os.path.exists(os.path.join(ROOT, "landing", cover_rel))
        manifest[m["group"]].append({
            "slug": m["slug"], "title": m["title"], "eyebrow": m["eyebrow"],
            "summary": m["summary"], "theme": m["theme"], "place": m["place"],
            "district": m.get("district"),
            "sections": sum(1 for b in body if b[0] == "h2"),
            "cover": cover_rel if has_cover else None,
        })
        written += 1
        stats = sum(1 for b in body if b[0] == "stat")
        entries = sum(1 for b in body if b[0] == "entry")
        print(f"  {m['slug']:28s} {len(body):3d} blk  "
              f"hero:{len(hero)} stat:{stats} entry:{entries} -> cases/{m['slug']}.html")

    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1, ensure_ascii=False)
    print(f"\nwrote {written} pages + {os.path.relpath(MANIFEST, ROOT)} "
          f"({len(manifest['ap'])} AP, {len(manifest['model'])} models)")


if __name__ == "__main__":
    main()
