#!/usr/bin/env python3
"""Generate fallback poster stills for the methodology deck's video backgrounds.

Each of the twelve slides carries a `data-bg` name. When a video exists it plays;
before it loads - or when no video has been supplied yet - the slide shows one of
these posters as its base layer. Each poster is a static, self-contained SVG that
matches the FIRST FRAME of that slide's video brief: same dark forest-green base,
same lime/teal glow, same motif, and the same baked-in scrim so white headings
stay legible. No raster dependency, deterministic, a couple of KB each.

The deck's CSS paints one of these under every slide via `--poster`. The video,
when present, overlays on top (`.md-vid`, z above the poster, below the panel).

Palette (locked to the site, NOT the template decks):
  base   #06140e -> #0a1f16   deep forest green-black
  teal   #0e3a2c              mid
  lime   #7bed9f  mint #a3f7bf  cyan-teal #2fd6a6   (glow accents only)

Usage:
  python3 scripts/build_methodology_posters.py           # (re)write the posters
  python3 scripts/build_methodology_posters.py --check    # guard: fail if stale
"""
from __future__ import annotations
import math
import sys
from pathlib import Path

W, H = 1280, 720
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "landing" / "assets" / "methodology" / "bg" / "posters"

# ---- palette -------------------------------------------------------------
INK0 = "#06140e"
INK1 = "#0a1f16"
TEAL = "#0e3a2c"
LIME = "#7bed9f"
MINT = "#a3f7bf"
CYAN = "#2fd6a6"

# The twelve slide names, in deck order.
NAMES = ["title", "why", "gva", "routes", "levels", "split",
         "approach", "chain", "vintage", "district", "mandal", "takeaways"]


# ---- tiny svg helpers ----------------------------------------------------
def _f(x: float) -> str:
    return f"{x:.2f}".rstrip("0").rstrip(".")


def line(x1, y1, x2, y2, stroke, w=2.0, op=1.0, cap="round"):
    return (f'<line x1="{_f(x1)}" y1="{_f(y1)}" x2="{_f(x2)}" y2="{_f(y2)}" '
            f'stroke="{stroke}" stroke-width="{_f(w)}" stroke-linecap="{cap}" '
            f'opacity="{_f(op)}"/>')


def circle(cx, cy, r, fill="none", stroke="none", w=1.0, op=1.0):
    s = (f'<circle cx="{_f(cx)}" cy="{_f(cy)}" r="{_f(r)}" fill="{fill}" '
         f'opacity="{_f(op)}"')
    if stroke != "none":
        s += f' stroke="{stroke}" stroke-width="{_f(w)}"'
    return s + "/>"


def rrect(x, y, w, h, r, fill="none", stroke="none", sw=1.0, op=1.0):
    s = (f'<rect x="{_f(x)}" y="{_f(y)}" width="{_f(w)}" height="{_f(h)}" '
         f'rx="{_f(r)}" fill="{fill}" opacity="{_f(op)}"')
    if stroke != "none":
        s += f' stroke="{stroke}" stroke-width="{_f(sw)}"'
    return s + "/>"


def path(d, stroke=LIME, w=2.0, op=1.0, fill="none"):
    return (f'<path d="{d}" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="{_f(w)}" stroke-linecap="round" '
            f'stroke-linejoin="round" opacity="{_f(op)}"/>')


def poly_d(pts):
    return "M" + " L".join(f"{_f(x)} {_f(y)}" for x, y in pts)


# ---- shared frame: defs, base wash, vignette, and the legibility scrim ----
def _defs():
    return (
        '<defs>'
        # base radial - center a touch lighter, corners fall to ink
        f'<radialGradient id="base" cx="50%" cy="46%" r="75%">'
        f'<stop offset="0%" stop-color="{INK1}"/>'
        f'<stop offset="100%" stop-color="{INK0}"/></radialGradient>'
        # soft blur for glows
        '<filter id="soft" x="-40%" y="-40%" width="180%" height="180%">'
        '<feGaussianBlur stdDeviation="9"/></filter>'
        '<filter id="soft2" x="-60%" y="-60%" width="220%" height="220%">'
        '<feGaussianBlur stdDeviation="22"/></filter>'
        # the baked scrim: darkens center vertically so white text reads
        '<linearGradient id="scrim" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#06140e" stop-opacity="0.52"/>'
        '<stop offset="55%" stop-color="#06140e" stop-opacity="0.60"/>'
        '<stop offset="100%" stop-color="#06140e" stop-opacity="0.72"/>'
        '</linearGradient>'
        # corner vignette
        '<radialGradient id="vig" cx="50%" cy="50%" r="72%">'
        '<stop offset="60%" stop-color="#000" stop-opacity="0"/>'
        '<stop offset="100%" stop-color="#000" stop-opacity="0.45"/>'
        '</radialGradient>'
        '</defs>'
    )


def _open():
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
            f'width="{W}" height="{H}" preserveAspectRatio="xMidYMid slice">'
            + _defs()
            + f'<rect width="{W}" height="{H}" fill="url(#base)"/>')


def _close(body):
    # motif body, then scrim, then vignette on top
    return (body
            + f'<rect width="{W}" height="{H}" fill="url(#scrim)"/>'
            + f'<rect width="{W}" height="{H}" fill="url(#vig)"/>'
            + '</svg>')


# ---- coastline motif shared by slide 1 and slide 12 ----------------------
def _coastline(y0=470, amp=120, op=0.9):
    """A stylised AP-coast contour set, low and wide. Not a real map - a motif."""
    out = []
    for k in range(5):
        pts = []
        base = y0 + k * 26
        for i in range(0, 61):
            t = i / 60.0
            x = 120 + t * (W - 240)
            y = (base
                 - amp * math.exp(-((t - 0.55) ** 2) / 0.06)      # bay
                 + 34 * math.sin(t * 7.2 + k * 0.6)
                 - 46 * math.exp(-((t - 0.2) ** 2) / 0.02))       # headland
            pts.append((x, y))
        out.append(path(poly_d(pts), stroke=LIME, w=1.6,
                        op=op * (0.30 + 0.14 * (4 - k))))
    return "".join(out)


# ==========================================================================
# one function per slide - draws the FIRST FRAME motif
# ==========================================================================
def art_title():
    b = [f'<g filter="url(#soft2)">']
    # faint dust
    for i in range(60):
        x = (i * 97 + 40) % W
        y = (i * 53 + 30) % (H - 120)
        b.append(circle(x, y, 1.4, fill=MINT, op=0.10 + 0.05 * ((i * 7) % 3)))
    b.append('</g>')
    b.append(_coastline(y0=430, amp=130, op=1.0))
    return "".join(b)


def art_why():
    """Colonnade of pillars in silhouette, lime rim-light, receding right."""
    b = []
    n = 7
    for k in range(n):
        t = k / (n - 1)
        x = 130 + t * (W - 200)
        pw = 74 - t * 34
        top = 120 + t * 60
        bot = H - 90 + t * 20
        # column body dark, rim on left edge
        b.append(rrect(x - pw / 2, top, pw, bot - top, 8,
                       fill=TEAL, op=0.55 - t * 0.2))
        b.append(line(x - pw / 2, top, x - pw / 2, bot, LIME, 2.2,
                      op=0.55 - t * 0.28))
        # capital + base
        b.append(rrect(x - pw / 2 - 8, top - 14, pw + 16, 16, 4,
                       fill=TEAL, op=0.5 - t * 0.2))
    # volumetric shaft between two columns (kept off-centre, right)
    b.append(f'<g filter="url(#soft2)">'
             + '<polygon points="820,120 900,120 1010,640 700,640" '
               f'fill="{MINT}" opacity="0.05"/></g>')
    return "".join(b)


def art_gva():
    """Two horizontal light ribbons with a glowing gap between."""
    b = []
    yU, yL = 250, 470
    for x0, col, y in ((0, MINT, yU), (0, CYAN, yL)):
        pts = [(x, y + 26 * math.sin(x / 150.0 + (0 if y == yU else 1.4)))
               for x in range(0, W + 1, 12)]
        b.append(f'<g filter="url(#soft)">'
                 + path(poly_d(pts), stroke=col, w=6,
                        op=0.55 if y == yU else 0.32) + '</g>')
    # the value-added band - soft fill between, brightest toward left
    band = ([(x, yU + 26 * math.sin(x / 150.0)) for x in range(0, W + 1, 20)]
            + [(x, yL + 26 * math.sin(x / 150.0 + 1.4))
               for x in range(W, -1, -20)])
    b.append(f'<g filter="url(#soft2)"><path d="{poly_d(band)} Z" '
             f'fill="{LIME}" opacity="0.06"/></g>')
    return "".join(b)


def art_routes():
    """Three ribbons entering from the left, converging low-centre."""
    b = []
    pool = (W * 0.5, H * 0.66)
    starts = [(0, 150, MINT), (0, 360, LIME), (0, 560, CYAN)]
    for sx, sy, col in starts:
        cx = (sx + pool[0]) / 2
        d = (f'M{_f(sx)} {_f(sy)} Q{_f(cx)} {_f(sy)} '
             f'{_f(pool[0])} {_f(pool[1])}')
        b.append(f'<g filter="url(#soft)">' + path(d, stroke=col, w=4, op=0.5)
                 + '</g>')
    # one ribbon out to the right
    b.append(f'<g filter="url(#soft)">'
             + path(f'M{_f(pool[0])} {_f(pool[1])} Q{_f(W*0.78)} {_f(pool[1])} '
                    f'{_f(W)} {_f(H*0.5)}', stroke=MINT, w=4, op=0.45) + '</g>')
    b.append(f'<g filter="url(#soft2)">'
             + circle(pool[0], pool[1], 60, fill=LIME, op=0.14) + '</g>')
    b.append(circle(pool[0], pool[1], 22, fill=MINT, op=0.35))
    return "".join(b)


def art_levels():
    """Nested concentric ring-tiers, an inverted stepped funnel."""
    b = []
    cx, cy = W / 2, H * 0.42
    for k in range(4):
        rx = 360 - k * 78
        ry = 120 - k * 24
        yy = cy + k * 66
        b.append(f'<ellipse cx="{_f(cx)}" cy="{_f(yy)}" rx="{_f(rx)}" '
                 f'ry="{_f(ry)}" fill="none" stroke="{LIME}" '
                 f'stroke-width="2" opacity="{_f(0.5 - k*0.07)}"/>')
    # falling particles at the sides
    for i in range(18):
        x = cx + (-1 if i % 2 else 1) * (150 + (i * 37) % 260)
        y = cy - 40 + (i * 43) % 380
        b.append(circle(x, y, 2, fill=MINT, op=0.18))
    return "".join(b)


def art_split():
    """Calm grid of tiles in three clusters. Table slide - lowest contrast."""
    b = []
    groups = [(4, 150), (4, 470), (8, 790)]  # (count, x-start) loose clusters
    cols = 4
    ty, th, tw, gap = 250, 78, 96, 22
    idx = 0
    for count, x0 in groups:
        for j in range(count):
            r, c = divmod(j, cols)
            x = x0 + c * (tw + gap)
            y = ty + r * (th + gap)
            op = 0.10 + 0.06 * ((idx * 5) % 4)
            b.append(rrect(x, y, tw, th, 12, fill=LIME, op=op))
            b.append(rrect(x, y, tw, th, 12, stroke=CYAN, sw=1, op=0.12))
            idx += 1
    return "".join(b)


def art_approach():
    """Opposing particle streams: down from top, up from bottom, meet mid."""
    b = []
    for i in range(70):
        x = (i * 89 + 20) % W
        # top stream (upper third)
        yt = (i * 31) % 210
        b.append(circle(x, yt, 2.2, fill=LIME, op=0.22 - yt / 1400.0))
        # bottom stream (lower third)
        yb = H - (i * 37) % 210
        b.append(circle((x + 55) % W, yb, 2.2, fill=MINT,
                        op=0.22 - (H - yb) / 1400.0))
    # diffuse meeting band
    b.append(f'<g filter="url(#soft2)">'
             + rrect(0, H / 2 - 30, W, 60, 0, fill=CYAN, op=0.05) + '</g>')
    return "".join(b)


def art_chain():
    """One ribbon through four nodes, low in frame, ending in a warm orb."""
    b = []
    y = H * 0.66
    xs = [180, 460, 740, 1020, 1180]
    d = f'M{_f(xs[0])} {_f(y)}'
    for x in xs[1:]:
        d += f' L{_f(x)} {_f(y)}'
    b.append(f'<g filter="url(#soft)">' + path(d, stroke=LIME, w=4, op=0.4)
             + '</g>')
    for k, x in enumerate(xs[:4]):
        b.append(f'<g filter="url(#soft)">'
                 + circle(x, y, 26, fill=LIME, op=0.16) + '</g>')
        b.append(circle(x, y, 10, fill=MINT, op=0.4))
    # final human-scale orb (last, slightly warmer -> mint)
    b.append(f'<g filter="url(#soft2)">'
             + circle(xs[4], y, 40, fill=MINT, op=0.22) + '</g>')
    b.append(circle(xs[4], y, 14, fill=MINT, op=0.5))
    return "".join(b)


def art_vintage():
    """Five waveforms, left trembling -> right steady. Table slide."""
    b = []
    baseY = 300
    for k in range(5):
        amp = 46 * math.exp(-0.5 * k)      # calms toward the front
        freq = 2.4 + k * 0.3
        y = baseY + k * 20
        pts = [(x, y + amp * math.sin(x / 90.0 * freq) *
                math.exp(-x / 2600.0))
               for x in range(0, W + 1, 8)]
        b.append(f'<g filter="url(#soft)">'
                 + path(poly_d(pts), stroke=(MINT if k == 4 else LIME),
                        w=2.4, op=0.18 + k * 0.06) + '</g>')
    return "".join(b)


def art_district():
    """Aerial patchwork of parcels, some lit, some fogged. No real map."""
    b = []
    # irregular cells on a jittered grid
    cols, rows = 7, 5
    cw, ch = W / cols, H / rows
    for r in range(rows):
        for c in range(cols):
            jx = ((r * 7 + c * 13) % 40) - 20
            jy = ((r * 11 + c * 5) % 30) - 15
            x = c * cw + 14 + jx * 0.4
            y = r * ch + 14 + jy * 0.4
            w = cw - 30
            h = ch - 30
            lit = (r * cols + c) % 3
            op = (0.30 if lit == 0 else 0.13 if lit == 1 else 0.05)
            b.append(rrect(x, y, w, h, 8, stroke=LIME, sw=1.6, op=op))
    # drifting fog bands (soft)
    b.append(f'<g filter="url(#soft2)">'
             + rrect(-40, H * 0.6, W + 80, 130, 0, fill=INK1, op=0.5) + '</g>')
    return "".join(b)


def art_mandal():
    """One source cell up top subdividing down into many. Table slide."""
    b = []
    top = (W / 2, 120)
    b.append(f'<g filter="url(#soft)">'
             + circle(top[0], top[1], 30, fill=LIME, op=0.16) + '</g>')
    b.append(circle(top[0], top[1], 13, fill=MINT, op=0.4))
    # two tiers of branching to a fine bottom row
    tier1 = [(W * 0.32, 300), (W * 0.68, 300)]
    for p in tier1:
        b.append(path(f'M{_f(top[0])} {_f(top[1]+30)} '
                      f'L{_f(p[0])} {_f(p[1])}', stroke=LIME, w=1.6, op=0.28))
        b.append(circle(p[0], p[1], 8, fill=MINT, op=0.3))
    bottomN = 10
    for i in range(bottomN):
        bx = 140 + i * (W - 280) / (bottomN - 1)
        by = 470
        src = tier1[0] if bx < W / 2 else tier1[1]
        b.append(path(f'M{_f(src[0])} {_f(src[1])} L{_f(bx)} {_f(by)}',
                      stroke=LIME, w=1.2, op=0.16))
        b.append(rrect(bx - 22, by, 44, 44, 8, fill=LIME,
                       op=0.06 + 0.05 * (i % 3)))
    return "".join(b)


def art_takeaways():
    """Coastline callback + particles gathering to an upper-centre glow."""
    b = [_coastline(y0=520, amp=90, op=0.55)]
    glow = (W / 2, H * 0.34)
    b.append(f'<g filter="url(#soft2)">'
             + circle(glow[0], glow[1], 70, fill=MINT, op=0.16) + '</g>')
    b.append(circle(glow[0], glow[1], 20, fill=MINT, op=0.32))
    # rising particles beneath the glow
    for i in range(34):
        x = glow[0] + (-1 if i % 2 else 1) * ((i * 41) % 300)
        y = glow[1] + 60 + (i * 47) % 300
        b.append(circle(x, y, 2, fill=LIME, op=0.20 - (y - glow[1]) / 3000.0))
    return "".join(b)


BUILDERS = {
    "title": art_title, "why": art_why, "gva": art_gva, "routes": art_routes,
    "levels": art_levels, "split": art_split, "approach": art_approach,
    "chain": art_chain, "vintage": art_vintage, "district": art_district,
    "mandal": art_mandal, "takeaways": art_takeaways,
}


def render(name: str) -> str:
    return _close(_open() + BUILDERS[name]())


def main() -> int:
    check = "--check" in sys.argv
    OUT.mkdir(parents=True, exist_ok=True)
    stale = []
    for name in NAMES:
        svg = render(name)
        f = OUT / f"{name}.svg"
        if check:
            if not f.exists() or f.read_text() != svg:
                stale.append(name)
        else:
            f.write_text(svg)
    if check:
        if stale:
            print("STALE methodology posters (run build_methodology_posters.py): "
                  + ", ".join(stale))
            return 1
        print(f"OK: {len(NAMES)} methodology posters current")
        return 0
    print(f"Wrote {len(NAMES)} posters to {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
