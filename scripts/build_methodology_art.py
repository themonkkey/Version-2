#!/usr/bin/env python3
"""Draw the methodology deck's illustrations from equations.

WHY DRAWN, NOT CHARTED. These slides carry ideas, not datasets: what value added
IS, how four levels of government nest, why the same year gets published five
times. A bar chart of an idea is a category error. So these are illustrations,
in the dashboard's palette, the way a modern deck illustrates a concept.

WHY GENERATED FROM MATHS. Two of them are not decoration at all - the equation
IS the explanation:

  gva.svg      Value added is the AREA BETWEEN an output curve and an input
               curve. The shaded region is a literal integral, and the constants
               are tuned so that integral equals 60 against an output of 100 and
               inputs of 40. The picture cannot drift from the arithmetic it
               illustrates, because the arithmetic draws it.

  vintage.svg  A revision series is a DAMPED OSCILLATION converging on the final
               figure: 100 + 18·e^(-0.55n)·cos(1.9n). Early estimates overshoot
               and undershoot, later ones settle. That is exactly what FAE to TRE
               does, and drawing it as convergence says so without a caption.

The rest are constructed rather than plotted, but from the same primitives, so
the whole set shares one stroke weight, one corner radius and one palette. Change
a constant here and every figure moves together; hand-drawn SVG holds that
consistency for about four figures.

WHY SVG. Sharp on a projector at any zoom, a few KB, and - the reason that
actually decides it - the page can ANIMATE it. Every figure ships class hooks
(mk-draw, mk-bar, mk-tile, mk-frame) with a --i stagger index that the deck's
CSS drives when a slide becomes active. A raster can do none of that.

Output: landing/assets/methodology/*.svg

Usage:
    python3 scripts/build_methodology_art.py            # write
    python3 scripts/build_methodology_art.py --check    # verify, exit 1 on drift
"""
import os
import sys

try:
    import numpy as np
except ImportError:
    sys.exit("numpy is required: python3 -m pip install numpy")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "landing", "assets", "methodology")

# The dashboard palette. The three sector hues are the CVD-safe set the project
# settled on, used in the same order everywhere, so a colour means the same
# thing here as on a district page.
LIME = "#C6FF6A"
AGRI = "#6FA817"
INDU = "#2B93BF"
SERV = "#BF8A2B"
LINE = "rgba(255,255,255,.34)"
FILL = "rgba(255,255,255,.07)"
DIM = "rgba(255,255,255,.55)"
SW = 1.7                      # one stroke weight for the whole set
FONT = "Public Sans, Inter, system-ui, sans-serif"


# ── primitives ────────────────────────────────────────────────────────────

def svg(w, h, body):
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" '
            'fill="none" class="mk" aria-hidden="true">\n%s\n</svg>\n'
            % (w, h, body))


def rect(x, y, w, h, r=10, fill=FILL, stroke=LINE, sw=SW, cls="", i=None):
    st = ' style="--i:%d"' % i if i is not None else ""
    return ('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%g" '
            'fill="%s" stroke="%s" stroke-width="%g" class="%s"%s/>'
            % (x, y, w, h, r, fill, stroke, sw, cls, st))


def text(x, y, s, size=12, fill="#fff", weight=600, anchor="middle"):
    return ('<text x="%.1f" y="%.1f" font-size="%g" fill="%s" font-weight="%s" '
            'text-anchor="%s" font-family="%s">%s</text>'
            % (x, y, size, fill, weight, anchor, FONT, s))


def path(d, stroke=LINE, sw=SW, fill="none", cls="", i=None, extra=""):
    st = ' style="--i:%d"' % i if i is not None else ""
    return ('<path d="%s" fill="%s" stroke="%s" stroke-width="%g" '
            'stroke-linecap="round" stroke-linejoin="round" class="%s"%s%s/>'
            % (d, fill, stroke, sw, cls, st, extra))


def polyline(xs, ys):
    return "M" + " L".join("%.1f %.1f" % (x, y) for x, y in zip(xs, ys))


def arrow(x1, y1, x2, y2, stroke=LINE, cls="mk-draw", sw=SW, head=6.0):
    import math
    a = math.atan2(y2 - y1, x2 - x1)
    hx, hy = x2 - head * math.cos(a), y2 - head * math.sin(a)
    s, c = math.sin(a) * head * 0.58, math.cos(a) * head * 0.58
    return (path("M%.1f %.1f L%.1f %.1f" % (x1, y1, x2, y2), stroke, sw, "none", cls)
            + path("M%.1f %.1f L%.1f %.1f L%.1f %.1f"
                   % (hx - s, hy + c, x2, y2, hx + s, hy - c), stroke, sw, "none", cls))


# ── the figures ───────────────────────────────────────────────────────────

def art_gva():
    """Value added as the area between an output curve and an input curve.

    output(t) = 100·(1 + a·sin(2π·1.1·t))
    inputs(t) =  40·(1 + b·sin(2π·1.6·t + φ))

    The oscillation is what makes the point that neither line is flat: output
    rises and falls, inputs rise and fall on their own rhythm, and the gap
    between them is the only thing that is actually value added. The amplitudes
    are chosen so the mean gap is exactly 60 against 100 and 40 - the same
    numbers as the slide's worked example, so picture and arithmetic cannot
    disagree."""
    W, H = 560, 240
    x0, x1, ybase, yscale = 66, 512, 196, 1.28
    t = np.linspace(0, 1, 240)
    out = 100 * (1 + 0.30 * np.sin(2 * np.pi * 1.1 * t))
    inp = 40 * (1 + 0.52 * np.sin(2 * np.pi * 1.6 * t + 0.7))
    # Hold the mean gap at exactly 60 whatever the wave constants do.
    inp = inp + (np.trapezoid(out - inp, t) - 60.0)

    X = x0 + t * (x1 - x0)
    Yo = ybase - out * yscale
    Yi = ybase - inp * yscale

    b = []
    # the shaded integral, drawn first so the curves sit on top of it
    band = (polyline(X, Yo) + " L" + " L".join("%.1f %.1f" % (x, y)
            for x, y in zip(X[::-1], Yi[::-1])) + " Z")
    b.append(path(band, "none", 0, "rgba(198,255,106,.20)", "mk-fade"))
    b.append(path(polyline(X, Yi), "rgba(255,255,255,.42)", SW, "none", "mk-draw", 1))
    b.append(path(polyline(X, Yo), "#fff", SW + .3, "none", "mk-draw", 0))
    # axis
    b.append(path("M%g %g L%g %g" % (x0 - 12, ybase, x1 + 10, ybase),
                  "rgba(255,255,255,.22)", 1.2))
    # labels sit on the curves they name
    b.append(text(x1 + 8, Yo[-1] + 4, "output", 12, "#fff", 700, "start"))
    b.append(text(x1 + 8, Yi[-1] + 4, "inputs", 12, DIM, 600, "start"))
    mid = len(t) // 2
    b.append(text((X[mid]), (Yo[mid] + Yi[mid]) / 2 + 5,
                  "value added", 13.5, LIME, 750))
    b.append(text(W / 2, H - 10,
                  "Rs 100 output  &#8722;  Rs 40 inputs  =  Rs 60 value added",
                  12, DIM, 600))
    return svg(W, H, "\n".join(b))


def art_vintage():
    """A revision series as a damped oscillation converging on the final figure.

    estimate(n) = 100 + 18·e^(-0.55n)·cos(1.9n),  n = 0..5

    The first estimate overshoots because it is built on projection; each
    revision replaces projection with records and the swing narrows. The curve
    settling onto the line IS the explanation of why two figures for one year
    can differ and neither is wrong."""
    W, H = 560, 230
    x0, x1, ymid, yscale = 62, 500, 118, 2.9
    codes = ["FAE", "SAE", "PE", "FRE", "SRE", "TRE"]
    when = ["Jan 26", "Feb 26", "May 26", "Feb 27", "Feb 28", "Mar 29"]
    n = np.arange(6)
    est = 100 + 18 * np.exp(-0.55 * n) * np.cos(1.9 * n)

    # a dense version of the same equation, for the curve through the points
    nd = np.linspace(0, 5, 260)
    curve = 100 + 18 * np.exp(-0.55 * nd) * np.cos(1.9 * nd)
    Xd = x0 + nd / 5 * (x1 - x0)
    Yd = ymid - (curve - 100) * yscale

    b = []
    # the value being converged on
    b.append(path("M%g %g L%g %g" % (x0 - 10, ymid, x1 + 34, ymid),
                  LIME, 1.3, "none", "", None, ' stroke-dasharray="5 5" opacity=".65"'))
    b.append(text(x1 + 38, ymid + 4, "final", 11.5, LIME, 700, "start"))
    # the envelope, so the damping is visible as a shape
    for sgn in (1, -1):
        env = 100 + sgn * 18 * np.exp(-0.55 * nd)
        b.append(path(polyline(Xd, ymid - (env - 100) * yscale),
                      "rgba(255,255,255,.16)", 1, "none", "", None,
                      ' stroke-dasharray="3 6"'))
    b.append(path(polyline(Xd, Yd), "rgba(198,255,106,.75)", SW, "none", "mk-draw", 0))

    for i, (code, lab) in enumerate(zip(codes, when)):
        x = x0 + i / 5 * (x1 - x0)
        y = ymid - (est[i] - 100) * yscale
        final = i == 5
        b.append('<circle cx="%.1f" cy="%.1f" r="%g" fill="%s" stroke="%s" '
                 'stroke-width="%g" class="mk-pop" style="--i:%d"/>'
                 % (x, y, 6.5 if final else 5, LIME if final else "rgba(11,46,32,1)",
                    LIME, SW, i))
        b.append(text(x, 196, code, 12, LIME if final else "#fff", 750))
        b.append(text(x, 212, lab, 10, DIM, 500))
    b.append(text(x0 - 4, 30, "projection", 11, DIM, 600, "start"))
    b.append(text(x1 + 34, 30, "measurement", 11, LIME, 650, "end"))
    return svg(W, H, "\n".join(b))


def art_levels():
    """Four levels of the same economy, as a cascade.

    Concentric nesting was tried first and rejected: the frames have to inset
    about 40px a side for each label to clear the one inside it, which leaves
    the innermost frame too small to letter. Offsetting them instead keeps every
    label legible AND still reads as containment, because each card overlaps the
    one behind it."""
    W, H = 560, 268
    steps = [("GDP", "India", "MoSPI, quarterly", "rgba(255,255,255,.07)", LINE),
             ("GSDP", "Andhra Pradesh", "State DES, annual", "rgba(43,147,191,.16)", INDU),
             ("GDDP", "District", "annual, 26 districts", "rgba(111,168,23,.18)", AGRI),
             ("MDP", "Mandal", "shared out on indicators", "rgba(198,255,106,.20)", LIME)]
    b = []
    for i, (key, place, note, fill, hue) in enumerate(steps):
        x = 34 + i * 30
        y = 22 + i * 52
        w, h = 372, 62
        b.append(rect(x, y, w, h, 13, fill, hue, SW, "mk-frame", i))
        b.append(text(x + 16, y + 26, key, 14.5, hue, 750, "start"))
        b.append(text(x + 16, y + 45, place, 11.5, "#fff", 600, "start"))
        b.append(text(x + w - 16, y + 38, note, 10.5, DIM, 500, "end"))
        if i < 3:
            # the arrow says the level below is derived from the one above
            b.append(arrow(x + 18, y + h + 2, x + 30, y + h + 12, hue, "mk-draw", SW, 5))
    b.append(text(W / 2, H - 8, "each level is estimated from the one above it, "
                                "or built up from the one below", 11, DIM, 500))
    return svg(W, H, "\n".join(b))


def art_split():
    """Sixteen sub-sectors, 4 / 4 / 8, and the one that changes sides."""
    W, H = 560, 226
    b = []
    y = 30
    for gi, (name, hue, n) in enumerate([("Agriculture", AGRI, 4),
                                         ("Industry", INDU, 4),
                                         ("Services", SERV, 8)]):
        b.append(text(24, y + 17, name, 12.5, hue, 750, "start"))
        b.append(text(24, y + 33, "%d sub-sectors" % n, 10.5, DIM, 500, "start"))
        for k in range(n):
            hl = (gi == 1 and k == 0)          # mining: the tile that moves
            b.append(rect(168 + k * 46, y, 38, 34, 8,
                          "rgba(198,255,106,.20)" if hl else "rgba(255,255,255,.07)",
                          LIME if hl else hue, SW, "mk-tile", gi * 4 + k))
        y += 62
    b.append(text(W / 2, H - 8,
                  "Mining sits in Industry for Andhra Pradesh, in Primary for GoI",
                  11, LIME, 600))
    return svg(W, H, "\n".join(b))


def art_approach():
    """Top-down shares a state total out; bottom-up adds districts up."""
    W, H = 560, 200
    b = []
    for side, (title, note, hue, up) in enumerate(
            [("Top-down", "shared out on an indicator", LINE, False),
             ("Bottom-up", "measured locally, then added up", LIME, True)]):
        cx = 140 + side * 280
        b.append(text(cx, 20, title, 13, "#fff", 750))
        b.append(rect(cx - 66, 32, 132, 32, 8,
                      "rgba(198,255,106,.18)" if up else "rgba(255,255,255,.12)",
                      hue, SW))
        b.append(text(cx, 53, "State total", 11.5, LIME if up else "#fff", 600))
        for k in range(4):
            x = cx - 66 + k * 36
            if up:
                b.append(arrow(x + 13, 106, cx, 70, hue, "mk-draw"))
            else:
                b.append(arrow(cx, 68, x + 13, 104, hue, "mk-draw"))
            b.append(rect(x, 110, 26, 26, 6,
                          "rgba(198,255,106,.14)" if up else FILL, hue, SW,
                          "mk-tile", k))
        b.append(text(cx, 160, note, 11, DIM, 500))
    b.append(path("M280 24 L280 172", LINE, 1, "none", "", None,
                  ' stroke-dasharray="3 5" opacity=".45"'))
    return svg(W, H, "\n".join(b))


def art_chain():
    """Value added to rupees per person, in four moves."""
    W, H = 560, 148
    b = []
    steps = [("GVA", "at basic prices"), ("+ taxes &#8722; subsidies", "market prices"),
             ("&#8722; capital used up", "net product"), ("&#247; population", "per person")]
    for i, (top, bot) in enumerate(steps):
        x = 18 + i * 138
        last = i == 3
        b.append(rect(x, 42, 118, 58, 11,
                      "rgba(198,255,106,.18)" if last else FILL,
                      LIME if last else LINE, SW, "mk-tile", i))
        b.append(text(x + 59, 69, top, 11.5, LIME if last else "#fff", 700))
        b.append(text(x + 59, 87, bot, 10.5, DIM, 500))
        if i < 3:
            b.append(arrow(x + 122, 71, x + 134, 71, LINE, "mk-draw"))
    return svg(W, H, "\n".join(b))


def art_mandal():
    """A district's value added, shared out to mandals on an indicator.

    Each block's WIDTH is its share, so the drawing is the arithmetic."""
    W, H = 560, 212
    shares = [(.25, "A"), (.375, "B"), (.25, "C"), (.125, "D")]
    b = [rect(196, 18, 168, 40, 10, "rgba(43,147,191,.18)", INDU, SW),
         text(280, 43, "District GVA", 13, "#fff", 700)]
    x = 40
    for i, (sh, nm) in enumerate(shares):
        w = 480 * sh
        b.append(arrow(280, 62, x + w / 2, 102, LINE, "mk-draw"))
        b.append(rect(x, 106, w - 8, 46, 9, "rgba(198,255,106,.16)", LIME, SW,
                      "mk-bar", i))
        # Just the letter: at a 12.5% share the block is 52px wide and
        # "Mandal D" overflows it. The row is labelled once, underneath.
        b.append(text(x + (w - 8) / 2, 127, nm, 13, "#fff", 750))
        b.append(text(x + (w - 8) / 2, 143, "%g%%" % (sh * 100), 11, LIME, 700))
        x += w
    b.append(text(W / 2, 176, "four mandals: each share is that mandal&#39;s allocation "
                              "indicator, for example paddy produced", 11, DIM, 500))
    b.append(text(W / 2, 196, "18 sub-sectors  &#183;  110 indicators  &#183;  "
                              "each owned by a named department", 11, DIM, 500))
    return svg(W, H, "\n".join(b))


FIGURES = {
    "gva.svg": art_gva,
    "vintage.svg": art_vintage,
    "levels.svg": art_levels,
    "split.svg": art_split,
    "approach.svg": art_approach,
    "chain.svg": art_chain,
    "mandal.svg": art_mandal,
}


def main():
    check = "--check" in sys.argv
    if not check:
        os.makedirs(OUT, exist_ok=True)

    problems = []
    for name, fn in sorted(FIGURES.items()):
        p = os.path.join(OUT, name)
        drawn = fn()
        if check:
            if not os.path.exists(p):
                problems.append("missing " + name)
            else:
                with open(p, encoding="utf-8") as fh:
                    if fh.read() != drawn:
                        problems.append(name + " is stale; re-run without --check")
        else:
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(drawn)
            print("  %-13s %5d bytes" % (name, len(drawn)))

    if check:
        if problems:
            print("--check FAILED")
            for x in problems:
                print("  -", x)
            return 1
        print("--check: %d methodology illustration(s) verified" % len(FIGURES))
        return 0

    # State the two equations in the build output, so a reader of the log knows
    # the pictures are derived and not drawn by eye.
    t = np.linspace(0, 1, 240)
    out = 100 * (1 + 0.30 * np.sin(2 * np.pi * 1.1 * t))
    inp = 40 * (1 + 0.52 * np.sin(2 * np.pi * 1.6 * t + 0.7))
    inp = inp + (np.trapezoid(out - inp, t) - 60.0)
    print("wrote %d illustration(s) to landing/assets/methodology/" % len(FIGURES))
    print("  gva.svg      area between curves = %.2f  (target 60)"
          % np.trapezoid(out - inp, t))
    n = np.arange(6)
    print("  vintage.svg  series %s  ->  100"
          % np.round(100 + 18 * np.exp(-0.55 * n) * np.cos(1.9 * n), 1).tolist())
    return 0


if __name__ == "__main__":
    sys.exit(main())
