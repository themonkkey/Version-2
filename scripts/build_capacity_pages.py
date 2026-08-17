#!/usr/bin/env python3
"""Render the two capacity-building detail pages.

  landing/capacity/feedback.html    — the session feedback instrument
  landing/capacity/assessment.html  — the baseline / endline knowledge papers

Both read landing/assets/capacity_assessment.json (built by build_assessment.py)
and landing/assets/capacity.json (build_capacity.py), and both are standalone
pages in the same dark-stage idiom as the case-study readers: self-contained CSS,
no framework, no build step.

What they must NOT do is imply a result. The instruments have been administered
but the completed sheets are not digitised, so every page states that plainly
instead of showing an empty chart that reads as "no improvement".

Usage:  python3 scripts/build_capacity_pages.py
"""

import html
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = os.path.join(ROOT, "landing", "capacity")
A_JSON = os.path.join(ROOT, "landing", "assets", "capacity_assessment.json")
C_JSON = os.path.join(ROOT, "landing", "assets", "capacity.json")

LEVEL_NAME = {
    "district": "District level",
    "constituency": "Constituency &amp; mandal",
    "master": "Master trainers",
}
LEVEL_ORDER = ["district", "constituency", "master"]


def e(s):
    return html.escape(str(s if s is not None else ""), quote=True)


CSS = """
*{box-sizing:border-box;margin:0;padding:0;}
:root{
  --ink:#0E4A3C; --ink-2:#0B2E20; --lime:#C6FF6A; --lime-2:#C6EC8F;
  /* Tracks the viewport instead of pinning to a fixed width. A flat 960px left
     ~240px of dead margin either side on a normal desktop and squeezed the
     two-up baseline/endline panels for no reason; a flat 1280 would just move
     that problem to a different screen size. 94vw keeps a thin gutter at every
     width, and the 1680px ceiling stops the panels sprawling on an ultrawide,
     where a very long row becomes hard to read across. */
  --r:18px; --r-lg:24px; --maxw:min(1680px, 94vw);
}
html{scroll-behavior:smooth;}
body{
  font-family:'Public Sans',-apple-system,BlinkMacSystemFont,"Helvetica Neue",Helvetica,Arial,sans-serif;
  color:#fff;-webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale;
  background:#072117;
  background-image:
    radial-gradient(60% 50% at 12% 8%, rgba(18,124,103,.30) 0%, rgba(18,124,103,0) 62%),
    radial-gradient(52% 44% at 88% 0%, rgba(198,255,106,.13) 0%, rgba(198,255,106,0) 60%),
    radial-gradient(70% 60% at 50% 108%, rgba(11,46,32,.85) 0%, rgba(11,46,32,0) 70%);
  background-attachment:fixed;
  line-height:1.55;
}
/* Side padding was clamp(20px,5vw,44px) — the 5vw term grew the gutter as the
   screen got wider, so the content narrowed exactly when there was most room
   for it. Now it holds a small fixed gutter instead. */
.wrap{max-width:var(--maxw);margin:0 auto;padding:0 clamp(16px,2.2vw,28px);}
.top{padding:clamp(26px,4vw,44px) 0 clamp(18px,2.4vw,26px);}
.back{display:inline-flex;align-items:center;gap:7px;text-decoration:none;font-size:12.5px;
  font-weight:650;letter-spacing:.03em;color:rgba(198,236,143,.9);margin-bottom:clamp(16px,2.4vw,24px);}
.back:hover{color:var(--lime);}
.eyebrow{font-size:11px;font-weight:750;letter-spacing:.14em;text-transform:uppercase;
  color:rgba(198,236,143,.8);margin-bottom:9px;}
h1{font-size:clamp(26px,4.4vw,42px);font-weight:750;letter-spacing:-.025em;line-height:1.12;
  margin-bottom:12px;}
.lede{font-size:clamp(14.5px,1.7vw,16.5px);line-height:1.6;color:rgba(255,255,255,.76);
  max-width:70ch;}
.panel{border-radius:var(--r-lg);padding:clamp(18px,2.3vw,26px) clamp(18px,2.5vw,30px);
  background:rgba(9,40,27,.72);border:1px solid rgba(255,255,255,.18);
  backdrop-filter:blur(16px) saturate(150%);-webkit-backdrop-filter:blur(16px) saturate(150%);
  box-shadow:0 12px 34px rgba(0,0,0,.22);margin-bottom:clamp(16px,2.2vw,22px);}
.panel h2{font-size:clamp(17px,2.1vw,21px);font-weight:700;margin-bottom:6px;letter-spacing:-.015em;}
.panel h2 + .sub{font-size:13.4px;color:rgba(255,255,255,.66);margin-bottom:16px;}
.kicker{font-size:11px;font-weight:750;letter-spacing:.12em;text-transform:uppercase;
  color:var(--lime);margin-bottom:7px;}
.flag{display:flex;gap:12px;align-items:flex-start;border-radius:var(--r);
  padding:14px 17px;margin-bottom:clamp(18px,2.4vw,26px);
  background:rgba(255,214,102,.09);border:1px solid rgba(255,214,102,.30);}
.flag .dot{flex:0 0 auto;width:8px;height:8px;border-radius:50%;background:#FFD666;margin-top:7px;}
.flag p{font-size:13.2px;line-height:1.58;color:rgba(255,255,255,.82);}
.flag b{color:#FFE9AD;font-weight:650;}
.strip{display:grid;grid-template-columns:repeat(auto-fit,minmax(124px,1fr));
  gap:clamp(10px,1.4vw,14px);margin-bottom:clamp(18px,2.4vw,26px);}
.stat{border-radius:var(--r);padding:14px 16px;background:rgba(9,40,27,.7);
  border:1px solid rgba(255,255,255,.17);}
.stat .v{font-size:clamp(19px,2.5vw,26px);font-weight:750;letter-spacing:-.02em;line-height:1.05;
  font-variant-numeric:tabular-nums;}
.stat .k{font-size:10.8px;font-weight:600;letter-spacing:.09em;text-transform:uppercase;
  color:rgba(198,236,143,.85);margin-top:5px;}
.scale{display:flex;gap:7px;flex-wrap:wrap;margin-bottom:16px;}
.scale span{font-size:11px;font-weight:600;letter-spacing:.03em;padding:5px 10px;border-radius:999px;
  background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.15);
  color:rgba(255,255,255,.78);}
.scale span:first-child{border-color:rgba(255,138,138,.35);color:#FFC9C9;}
.scale span:last-child{border-color:rgba(198,236,143,.4);color:var(--lime-2);}
ol.items,ul.items{list-style:none;display:grid;gap:9px;}
ol.items li,ul.items li{display:flex;gap:12px;align-items:flex-start;
  font-size:13.8px;line-height:1.55;color:rgba(255,255,255,.87);
  padding:11px 14px;border-radius:13px;background:rgba(255,255,255,.05);
  border:1px solid rgba(255,255,255,.10);}
ol.items li .n,ul.items li .n{flex:0 0 auto;width:23px;height:23px;border-radius:50%;
  display:grid;place-items:center;background:rgba(198,236,143,.18);color:#DCF0A8;
  font-size:11.5px;font-weight:750;margin-top:1px;font-variant-numeric:tabular-nums;}
.mcq{padding:13px 15px;border-radius:13px;background:rgba(255,255,255,.05);
  border:1px solid rgba(255,255,255,.10);margin-bottom:9px;}
.mcq .q{font-size:13.8px;line-height:1.55;font-weight:600;color:#fff;margin-bottom:9px;
  display:flex;gap:11px;align-items:flex-start;}
.mcq .q .n{flex:0 0 auto;width:23px;height:23px;border-radius:50%;display:grid;place-items:center;
  background:rgba(198,236,143,.18);color:#DCF0A8;font-size:11.5px;font-weight:750;margin-top:1px;}
.mcq ul{list-style:none;display:grid;gap:5px;padding-left:34px;}
.mcq ul li{font-size:12.8px;line-height:1.5;color:rgba(255,255,255,.72);
  padding-left:16px;position:relative;}
.mcq ul li::before{content:"";position:absolute;left:0;top:6px;width:8px;height:8px;
  border-radius:50%;border:1px solid rgba(255,255,255,.35);}
.papers{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));
  gap:clamp(12px,1.6vw,16px);margin-bottom:clamp(18px,2.4vw,26px);}
.paper{border-radius:var(--r);padding:15px 17px;background:rgba(255,255,255,.055);
  border:1px solid rgba(255,255,255,.13);}
.paper .lvl{font-size:11px;font-weight:750;letter-spacing:.1em;text-transform:uppercase;
  color:var(--lime-2);margin-bottom:6px;}
.paper .aud{font-size:13.4px;font-weight:650;color:#fff;margin-bottom:9px;}
.paper .row{display:flex;justify-content:space-between;font-size:12.4px;
  color:rgba(255,255,255,.65);padding:4px 0;border-top:1px solid rgba(255,255,255,.09);}
.paper .row:first-of-type{border-top:0;}
.paper .row b{color:#fff;font-weight:650;font-variant-numeric:tabular-nums;}
.foot{padding:clamp(24px,4vw,48px) 0 clamp(30px,5vw,60px);font-size:12.2px;
  color:rgba(255,255,255,.5);line-height:1.6;}
.foot a{color:rgba(198,236,143,.8);}
@media(max-width:640px){ .mcq ul{padding-left:0;} }
"""


def head(title, desc):
    return (
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        '<title>%s · Swarna Andhra @2047</title>\n'
        '<meta name="description" content="%s">\n'
        '<link rel="icon" href="../favicon.ico">\n'
        '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
        '<link href="https://fonts.googleapis.com/css2?family=Public+Sans:wght@400;600;700;750&display=swap" rel="stylesheet">\n'
        '<style>%s</style>\n' % (e(title), e(desc), CSS)
    )


def stat(v, k):
    return '<div class="stat"><div class="v">%s</div><div class="k">%s</div></div>' % (v, k)


def render_feedback(a, c):
    fb = a.get("feedback") or {"statements": [], "scale": []}
    papers = [p for p in a["papers"] if p["stage"] == "endline"]
    t = c["totals"]

    scale = "".join('<span>%s</span>' % e(s) for s in (fb.get("scale") or []))
    items = "".join(
        '<li><span class="n">%d</span><span>%s</span></li>' % (i + 1, e(s))
        for i, s in enumerate(fb["statements"]))

    by_level = ""
    for p in sorted(papers, key=lambda x: LEVEL_ORDER.index(x["level"])):
        rows = (
            '<div class="row"><span>Feedback statements</span><b>%d</b></div>'
            '<div class="row"><span>Knowledge items</span><b>%d</b></div>'
            % (len(p["feedback_statements"]), p["questions"]))
        by_level += (
            '<div class="paper"><div class="lvl">%s</div>'
            '<div class="aud">%s</div>%s</div>'
            % (LEVEL_NAME.get(p["level"], p["level"]), e(p["audience"]), rows))

    # Feedback is collected on the endline paper, so the sessions that could have
    # carried one are the delivered sessions — stated as scope, not as a response rate.
    body = (
        '<div class="top"><div class="wrap">'
        '<a class="back" href="../index.html#districts">&larr; Capacity building</a>'
        '<div class="eyebrow">Pahlé India Foundation · Capacity building</div>'
        '<h1>Training feedback</h1>'
        '<p class="lede">Every endline paper closes with a feedback block: the same '
        'nine statements, rated on a five-point agreement scale, asking officers what '
        'the session actually did for them rather than what it covered.</p>'
        '</div></div>'
        '<div class="wrap">'
        '<div class="strip">%s%s%s%s</div>'
        '<div class="flag"><span class="dot"></span><p>'
        '<b>No scores are reported on this page.</b> The feedback block was administered '
        'in the field, but the completed sheets have not been digitised. Showing an empty '
        'chart here would read as a result; this page shows the instrument instead.'
        '</p></div>'
        '<div class="panel">'
        '<div class="kicker">The instrument</div>'
        '<h2>What officers were asked to rate</h2>'
        '<p class="sub">Section C of the district endline; the same block appears on the '
        'constituency and master-trainer papers.</p>'
        '<div class="scale">%s</div>'
        '<ol class="items">%s</ol>'
        '</div>'
        '<div class="panel">'
        '<div class="kicker">Coverage</div>'
        '<h2>Where the feedback block was carried</h2>'
        '<p class="sub">One endline paper per level, each closing with the feedback section.</p>'
        '<div class="papers">%s</div>'
        '</div>'
        '<div class="foot">Built from the endline assessment papers in '
        '<code>corpus_files/training/</code>. '
        '<a href="../index.html#districts">Back to the dashboard</a></div>'
        '</div>'
        % (stat(len(fb["statements"]), "Statements"),
           stat("1–5", "Agreement scale"),
           stat(len(papers), "Endline papers"),
           stat(t["sessions_delivered"], "Sessions in scope"),
           scale, items, by_level))
    return head("Training feedback",
                "The nine-statement session feedback block used across the Swarna Andhra "
                "@2047 capacity building programme.") + body


def render_assessment(a, c):
    papers = a["papers"]
    t = c["totals"]

    cards = ""
    for lvl in LEVEL_ORDER:
        pre = next((p for p in papers if p["level"] == lvl and p["stage"] == "baseline"), None)
        post = next((p for p in papers if p["level"] == lvl and p["stage"] == "endline"), None)
        if not pre and not post:
            continue
        aud = (pre or post)["audience"]
        rows = (
            '<div class="row"><span>Baseline items</span><b>%s</b></div>'
            '<div class="row"><span>Endline items</span><b>%s</b></div>'
            '<div class="row"><span>Feedback block</span><b>%s</b></div>'
            % (pre["questions"] if pre else "—",
               post["questions"] if post else "—",
               "yes" if (post and post["has_feedback"]) else "—"))
        cards += ('<div class="paper"><div class="lvl">%s</div><div class="aud">%s</div>%s</div>'
                  % (LEVEL_NAME.get(lvl, lvl), e(aud), rows))

    sections = ""
    for p in sorted(papers, key=lambda x: (LEVEL_ORDER.index(x["level"]), x["stage"] != "baseline")):
        if not p["sections"]:
            continue
        blocks = ""
        for sec in p["sections"]:
            if sec["kind"] == "mcq":
                inner = "".join(
                    '<div class="mcq"><div class="q"><span class="n">%d</span><span>%s</span></div>'
                    '<ul>%s</ul></div>'
                    % (it.get("n", i + 1), e(it["text"]),
                       "".join("<li>%s</li>" % e(o) for o in it.get("options", [])))
                    for i, it in enumerate(sec["items"]))
            else:
                inner = ('<ul class="items">%s</ul>' % "".join(
                    '<li><span class="n">%d</span><span>%s</span></li>' % (i + 1, e(it["text"]))
                    for i, it in enumerate(sec["items"])))
            scale = ""
            if sec.get("scale"):
                scale = '<div class="scale">%s</div>' % "".join(
                    '<span>%s</span>' % e(s) for s in sec["scale"])
            blocks += ('<div class="kicker">Section %s · %s</div>'
                       '<h2 style="font-size:15.5px;margin-bottom:12px">%s</h2>%s%s'
                       % (e(sec["letter"]),
                          "self-rating" if sec["kind"] == "rating" else "multiple choice",
                          e(sec["title"]), scale, inner))
        sections += (
            '<div class="panel">'
            '<div class="kicker">%s · %s</div>'
            '<h2>%s</h2><p class="sub">%s — %d item%s across %d section%s.</p>%s</div>'
            % (LEVEL_NAME.get(p["level"], p["level"]), e(p["stage"]),
               e(p["title"]), e(p["audience"]), p["questions"],
               "" if p["questions"] == 1 else "s",
               len(p["sections"]), "" if len(p["sections"]) == 1 else "s", blocks))

    body = (
        '<div class="top"><div class="wrap">'
        '<a class="back" href="../index.html#districts">&larr; Capacity building</a>'
        '<div class="eyebrow">Pahlé India Foundation · Capacity building</div>'
        '<h1>Baseline &amp; endline</h1>'
        '<p class="lede">The same officers sit a knowledge paper before training and '
        'again after it. The baseline establishes what is already understood about '
        'Swarna Andhra, the KPI framework and the national-accounts concepts; the '
        'endline re-asks it, so the change is attributable to the session rather than '
        'to the cohort.</p>'
        '</div></div>'
        '<div class="wrap">'
        '<div class="strip">%s%s%s%s</div>'
        '<div class="flag"><span class="dot"></span><p>'
        '<b>No scores are reported on this page.</b> Both papers were administered in '
        'the field, but the completed sheets have not been digitised, so there is no '
        'baseline-to-endline movement to show yet. What follows is the instrument as '
        'administered.</p></div>'
        '<div class="panel">'
        '<div class="kicker">Design</div>'
        '<h2>Three levels, two sittings each</h2>'
        '<p class="sub">The paper is pitched to the level: district officers get the '
        'policy and KPI framing, constituency and mandal officers get the levers they '
        'actually control, master trainers get the estimation methodology they will '
        'teach on.</p>'
        '<div class="papers">%s</div>'
        '</div>'
        '%s'
        '<div class="foot">Built from the six assessment papers in '
        '<code>corpus_files/training/</code>. '
        '<a href="../index.html#districts">Back to the dashboard</a></div>'
        '</div>'
        % (stat(len([p for p in papers if p["stage"] == "baseline"]), "Baseline papers"),
           stat(len([p for p in papers if p["stage"] == "endline"]), "Endline papers"),
           stat(a["totals"]["questions"], "Total items"),
           stat(t["districts"], "Districts covered"),
           cards, sections))
    return head("Baseline & endline assessment",
                "The knowledge assessment administered before and after training across "
                "the Swarna Andhra @2047 capacity building programme.") + body


def main():
    a = json.load(open(A_JSON, encoding="utf-8"))
    c = json.load(open(C_JSON, encoding="utf-8"))
    os.makedirs(OUTDIR, exist_ok=True)
    for name, fn in (("feedback.html", render_feedback), ("assessment.html", render_assessment)):
        path = os.path.join(OUTDIR, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(fn(a, c))
        print("→ %s  (%.1f KB)" % (os.path.relpath(path, ROOT),
                                   os.path.getsize(path) / 1024.0))


if __name__ == "__main__":
    main()
