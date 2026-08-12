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


def role_for(title):
    t = (title or "").lower()
    for role, keys in ROLES:
        if any(k in t for k in keys):
            return role
    return "context"


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
        return ('<div class="entry"><div class="term">' + e(term) + '</div>'
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


def render_blocks(blocks):
    out, i = [], 0
    while i < len(blocks):
        if blocks[i][0] == "stat":
            run = []
            while i < len(blocks) and blocks[i][0] == "stat":
                run.append((blocks[i][1], blocks[i][2]))
                i += 1
            out.append(grid_html(run))
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
        '<p class="eyebrow r">' + e(m["eyebrow"]) + '</p>'
        '<h1 class="r">' + e(m["title"]) + '</h1>'
        '<p class="summary r">' + e(m["summary"]) + '</p>'
        '<div class="meta r">' + "".join(tags) + '</div>'
        + (herohtml and '<div class="r">' + herohtml + '</div>') +
        '<p class="hint r">Use ← → or the arrows to move through the story</p>'
        '</div></section>')
    slides.append(cover)

    for idx, s in enumerate(secs, start=1):
        body = render_blocks(s["blocks"])
        slides.append(
            '<section class="slide" data-i="' + str(idx) + '">'
            '<div class="media" data-media="' + str(idx) + '" data-role="'
            + role_for(s["title"]) + '"></div>'
            '<div class="glass reveal-root">'
            '<div class="sechead r"><span class="secnum">' + f"{idx:02d}" + '</span>'
            '<h2>' + e(s["title"] or "Overview") + '</h2></div>'
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
<link href="https://fonts.googleapis.com/css2?family=Bodoni+Moda:opsz,wght@6..96,500;6..96,600&family=Public+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
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
  display:flex;align-items:center;justify-content:center;padding:clamp(20px,5vw,64px);}

/* full-bleed background: animated mesh, tinted; photo/video overlays it if present */
.media{position:absolute;inset:0;z-index:0;
  background:
    radial-gradient(60% 70% at 18% 22%, color-mix(in srgb, var(--t1) 42%, transparent), transparent 70%),
    radial-gradient(55% 65% at 82% 78%, color-mix(in srgb, var(--t2) 34%, transparent), transparent 70%),
    radial-gradient(90% 90% at 50% 50%, #0A241A, #05100C 80%);
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
.glass{position:relative;z-index:2;width:min(760px,100%);max-height:84vh;overflow:auto;
  background:var(--glass);
  -webkit-backdrop-filter:blur(30px) saturate(1.3);backdrop-filter:blur(30px) saturate(1.3);
  border:1px solid var(--line);border-radius:24px;
  padding:clamp(24px,4vw,44px);
  box-shadow:0 30px 80px -30px rgba(0,0,0,.7), inset 0 1px 0 rgba(255,255,255,.08);
  scrollbar-width:thin;scrollbar-color:var(--t2) transparent;}
.glass::-webkit-scrollbar{width:8px;}
.glass::-webkit-scrollbar-thumb{background:color-mix(in srgb,var(--t2) 50%,transparent);border-radius:8px;}
.cover-glass{width:min(680px,100%);}

.eyebrow{font-size:12px;font-weight:700;letter-spacing:.11em;text-transform:uppercase;
  color:var(--t2);margin:0 0 16px;}
h1{font-family:'Bodoni Moda',Georgia,serif;font-weight:600;font-size:clamp(30px,5.2vw,52px);
  line-height:1.05;letter-spacing:-.01em;margin:0 0 18px;}
.summary{font-size:clamp(16px,2vw,20px);color:var(--mut);margin:0 0 22px;max-width:56ch;}
.meta{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 20px;}
.tag{font-size:12px;font-weight:600;padding:6px 12px;border-radius:999px;
  background:var(--glass2);border:1px solid var(--line);color:var(--mut);}
.tag.place{color:var(--fg);}
.hint{font-size:12.5px;color:var(--mut2);margin:22px 0 0;letter-spacing:.02em;}

.sechead{display:flex;align-items:baseline;gap:14px;margin:0 0 20px;
  padding-bottom:14px;border-bottom:1px solid var(--line);}
.secnum{font-family:'Bodoni Moda',serif;font-weight:600;font-size:16px;color:var(--t2);
  letter-spacing:.04em;}
.sechead h2{font-family:'Bodoni Moda',Georgia,serif;font-weight:600;
  font-size:clamp(22px,3.2vw,32px);letter-spacing:-.01em;color:#fff;margin:0;line-height:1.1;}
.secbody h3{font-family:'Public Sans',sans-serif;font-weight:700;font-size:clamp(16px,2vw,20px);
  color:#fff;margin:22px 0 6px;}
.secbody h3:first-child{margin-top:0;}
.secbody p{margin:0 0 13px;color:var(--mut);}
.secbody .k{margin:16px 0 4px;font-weight:700;font-size:13.5px;color:var(--t2);letter-spacing:.02em;}

/* hero + stat grids as inner glass chips */
.hero,.grid{display:grid;gap:12px;margin:18px 0 4px;
  grid-template-columns:repeat(auto-fit,minmax(140px,1fr));}
.grid{margin:14px 0 20px;}
.scell,.cell{background:var(--glass2);border:1px solid var(--line);border-radius:14px;
  padding:15px 16px 13px;transition:transform .26s cubic-bezier(.2,.7,.2,1),border-color .26s ease;}
.scell:hover,.cell:hover{transform:translateY(-3px);border-color:color-mix(in srgb,var(--t2) 50%,var(--line));}
.scell .v,.cell .v{font-family:'Bodoni Moda',Georgia,serif;font-weight:600;
  font-size:clamp(22px,3vw,30px);line-height:1;color:var(--t2);}
.scell .l,.cell .l{margin-top:7px;font-size:12.5px;line-height:1.4;color:var(--mut);font-weight:600;}

/* timeline entry */
.entry{display:grid;grid-template-columns:minmax(90px,124px) 1fr;gap:16px;
  padding:14px 0;border-top:1px solid var(--line);}
.entry:first-of-type{border-top:none;}
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
.count b{color:var(--fg);font-family:'Bodoni Moda',serif;font-size:17px;}
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
  .glass{max-height:none;overflow:visible;width:100%;}
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
<div class="count"><b id="cnum">01</b> / %%COUNT%%</div>
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
  var mobile=function(){return matchMedia('(max-width:760px)').matches;};

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
  var dots=[].slice.call(dotsWrap.children);

  function paint(){
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
        roles = ",".join(sorted({role_for(s["title"]) for s in secs}))
        print(f"  {m['slug']:30s} {n:2d} slides  [{roles}]")
        total += 1
    print(f"\nwrote {total} deck page(s) -> landing/cases/")


if __name__ == "__main__":
    main()
