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
        "eyebrow": "Case for action • Value-chain strategy",
        "title": "Unlocking East Godavari's Coconut & Coir Potential",
        "summary": "From a coconut-growing district to a diversified processing hub — coir, "
                   "activated carbon and beyond.",
    },
    {
        "file": "Nellore_Shrimp_Processing.txt", "slug": "nellore-shrimp-processing",
        "group": "ap", "district": "Sps_Nellore", "place": "SPSR Nellore",
        "theme": "Aquaculture",
        "eyebrow": "Case for action • Value-chain strategy",
        "title": "Unlocking Nellore's Shrimp Processing Potential",
        "summary": "From aquaculture capital to value-addition hub — why the district must "
                   "move up the shrimp chain.",
    },
    {
        "file": "Nellore_Ethanol_Potential.txt", "slug": "nellore-ethanol-potential",
        "group": "ap", "district": "Sps_Nellore", "place": "SPSR Nellore",
        "theme": "Ethanol / investment",
        "eyebrow": "Sector brief • Investment potential",
        "title": "Unlocking Nellore's Ethanol Opportunity",
        "summary": "Feedstock, infrastructure and the road to E20 — what the National Ethanol "
                   "Blending Programme means for the district.",
    },
    {
        "file": "Srikakulam_Blue_Economy.txt", "slug": "srikakulam-blue-economy",
        "group": "ap", "district": "Srikakulam", "place": "Srikakulam",
        "theme": "Blue economy",
        "eyebrow": "Case for action • Blue economy strategy",
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
        "eyebrow": "Industrial cluster case study",
        "title": "The Morbi Ceramic Cluster",
        "summary": "How a traditional craft town became the world's #2 ceramic tile producer — "
                   "and what a cluster's collective reinvention takes.",
    },
    {
        "file": "Tiruppur_Case_Study_Updated.txt", "slug": "tiruppur-textiles",
        "group": "model", "district": None, "place": "Tiruppur, Tamil Nadu",
        "theme": "Textiles cluster",
        "eyebrow": "Industrial cluster case study",
        "title": "Tiruppur: Innovation in Textiles & Garments",
        "summary": "The rise of South India's “Banian City” — a knitwear cluster that "
                   "moved from job-work to a global export base.",
    },
    {
        "file": "Kumarakom_Responsible_Tourism_Case_Study.txt", "slug": "kumarakom-tourism",
        "group": "model", "district": None, "place": "Kumarakom, Kerala",
        "theme": "Responsible tourism",
        "eyebrow": "Case study • Responsible tourism",
        "title": "The Kumarakom Responsible Tourism Model",
        "summary": "How a destination-level partnership linked tourism demand with local "
                   "livelihoods, culture and conservation.",
    },
    {
        "file": "Sahyadri_Replication_Playbook.txt", "slug": "sahyadri-farms-fpc",
        "group": "model", "district": None, "place": "Nashik, Maharashtra",
        "theme": "FPC / supply chain",
        "eyebrow": "Case study • Replication playbook",
        "title": "Sahyadri Farms: Smallholders in an Integrated Supply Chain",
        "summary": "What the Sahyadri Farms (FPC) model means for our mandals and districts.",
    },
    {
        "file": "Chetna_FPO_Lessons.txt", "slug": "chetna-organics-fpo",
        "group": "model", "district": None, "place": "Central India",
        "theme": "FPO strengthening",
        "eyebrow": "Case study • Farmer producer organisations",
        "title": "Chetna Organics: Building a Farmer-Owned Supply Chain",
        "summary": "What mandal officers can learn from an organic-cotton FPO to strengthen "
                   "their own producer organisations.",
    },
    {
        "file": "Biofloc_Tilapia_CaseStudy.txt", "slug": "biofloc-tilapia",
        "group": "model", "district": None, "place": "CMFRI, Kerala",
        "theme": "Aquaculture livelihoods",
        "eyebrow": "Case study • Rural livelihoods training",
        "title": "Biofloc Tilapia Farming",
        "summary": "A replicable model for mandal-level income generation, based on CMFRI's "
                   "Scheduled Caste Sub-Plan initiative.",
    },
    {
        "file": "Paddy_Fish_Integrated_Farming_Case_Study_AP.txt", "slug": "paddy-fish-farming",
        "group": "model", "district": None, "place": "India & China models",
        "theme": "Integrated farming",
        "eyebrow": "Case study deck",
        "title": "Paddy + Fish Integrated Farming",
        "summary": "Successful models from India and China, and a practical roadmap for "
                   "paddy-growing districts of Andhra Pradesh.",
    },
    {
        "file": "Banana_Processing_Case_Study.txt", "slug": "banana-processing",
        "group": "model", "district": None, "place": "Kanyakumari & Jalgaon",
        "theme": "Agro-processing",
        "eyebrow": "Capacity building case study",
        "title": "Banana Processing & Waste-to-Wealth Models",
        "summary": "Two replicable cases — KVK Kanyakumari value-added foods and the Jalgaon "
                   "pseudo-stem processing cluster.",
    },
]

BOILERPLATE = re.compile(
    r"^(#\s*index\.html|Capacity building programme \| Government of Andhra Pradesh)\s*$",
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


def parse_body(path):
    """Clean the deck text into ('h3'|'k'|'p', text) blocks.

    The cover slide (title / eyebrow / summary / hero stats) is dropped — every
    deck marks the end of it with a bare '1' section line, and the curated header
    already carries that content. After that:
      h3  — a section heading: a short title-ish line FOLLOWED BY prose.
      k   — a keyline: a short title-ish line followed by more short lines. These
            are the deck's stat values and timeline labels; flattened text can't
            tell a "stat card" from a "sub-heading", so they render as emphasis,
            not as section titles, and adjacent short ones are joined with ' · '
            so a stat reads "42% · of AP output" rather than stacking.
      p   — everything else.
    """
    with open(path, encoding="utf-8") as f:
        raw = [ln.rstrip() for ln in f]

    # body starts after the first bare '1' — the cover-slide boundary
    start = 0
    for i, ln in enumerate(raw):
        if re.fullmatch(r"\s*1\s*", ln):
            start = i + 1
            break

    kept = []
    for ln in raw[start:]:
        s = unescape(ln).strip()
        if not s or BOILERPLATE.match(s) or re.fullmatch(r"\d{1,2}", s):
            continue
        kept.append(s)

    # classify with one-line lookahead
    blocks = []
    for i, s in enumerate(kept):
        nxt = kept[i + 1] if i + 1 < len(kept) else ""
        if is_prose(s):
            blocks.append(["p", s])
        elif is_heading(s) and nxt and is_prose(nxt):
            blocks.append(["h3", s])
        else:
            blocks.append(["k", s])

    # join runs of adjacent short keylines into one, and drop exact dupes
    out = []
    for kind, text in blocks:
        if kind == "k" and out and out[-1][0] == "k" and len(out[-1][1]) < 90:
            if text not in out[-1][1].split(" · "):
                out[-1][1] += " · " + text
            continue
        if out and out[-1][0] == kind and out[-1][1] == text:
            continue
        out.append([kind, text])
    return [(k, t) for k, t in out]


PAGE_TMPL = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — Swarna Andhra case study</title>
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
.body h3{{font-family:'Public Sans',sans-serif;font-weight:700;font-size:clamp(17px,2.2vw,21px);
  letter-spacing:-.008em;color:#fff;margin:30px 0 6px;}}
.body h3:first-child{{margin-top:0;}}
.body p{{margin:0 0 14px;color:var(--mut);}}
.body .k{{margin:18px 0 4px;font-weight:700;font-size:14px;letter-spacing:.005em;
  color:var(--lime2);}}
.body .k + h3{{margin-top:2px;}}
footer{{margin-top:52px;padding-top:20px;border-top:1px solid var(--line);
  font-size:12.5px;color:var(--mut2);}}
footer b{{color:var(--mut);font-weight:600;}}
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
  <hr>
  <div class="body">
{body}
  </div>
  <footer>
    <b>Pahlé India Foundation</b> · Swarna Andhra @2047 capacity-building case study.
    Prepared for district &amp; mandal officers.
  </footer>
</div>
</body>
</html>
"""


def e(s):
    return html.escape(s, quote=True)


def render_page(m, body_blocks):
    tags = ['<span class="tag place">' + e(m["place"]) + "</span>"] if m.get("place") else []
    if m.get("theme"):
        tags.append('<span class="tag">' + e(m["theme"]) + "</span>")
    tags.append('<span class="tag">'
                + ("Andhra Pradesh district" if m["group"] == "ap" else "Replicable model")
                + "</span>")
    src = '<p class="src">' + e(m["source"]) + "</p>" if m.get("source") else ""
    def block_html(kind, text):
        if kind == "k":
            return '    <p class="k">' + e(text) + "</p>"
        return "    <{k}>{t}</{k}>".format(k=kind, t=e(text))

    body = "\n".join(block_html(k, t) for k, t in body_blocks)
    return PAGE_TMPL.format(
        title=e(m["title"]), eyebrow=e(m["eyebrow"]), summary=e(m["summary"]),
        tags="".join(tags), source=src, body=body,
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
        body = parse_body(path)
        page = render_page(m, body)
        with open(os.path.join(PAGES_DIR, m["slug"] + ".html"), "w", encoding="utf-8") as f:
            f.write(page)
        manifest[m["group"]].append({
            "slug": m["slug"], "title": m["title"], "eyebrow": m["eyebrow"],
            "summary": m["summary"], "theme": m["theme"], "place": m["place"],
            "district": m.get("district"), "sections": sum(1 for k, _ in body if k == "h3"),
        })
        written += 1
        print(f"  {m['slug']:28s} {len(body):3d} blocks -> cases/{m['slug']}.html")

    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1, ensure_ascii=False)
    print(f"\nwrote {written} pages + {os.path.relpath(MANIFEST, ROOT)} "
          f"({len(manifest['ap'])} AP, {len(manifest['model'])} models)")


if __name__ == "__main__":
    main()
