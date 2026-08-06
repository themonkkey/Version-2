#!/usr/bin/env python3
"""Turn the Figma scene exports into inline, animatable SVG.

The scenes are authored in Figma (file WH4TFZto8rBqY0IqJJ6cqn) and exported to
landing/assets/scenes/*.svg. Figma writes each layer name out as an `id`, which
is enough to hang CSS on — but only if the SVG is inline in the page, and only
after we strip Figma's export chrome.

This script:
  1. drops the #E5E5E5 export backing rect and the per-scene solid background
     (the page already provides the dark ground)
  2. converts the id naming Figma emits into the classes the stylesheet targets
  3. rewrites the outer <svg> to be responsive
  4. writes landing/assets/scenes/scenes.inc.html for pasting into index.html

Re-run after any edit in Figma:
    python3 scripts/build_scenes.py
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "landing" / "assets" / "scenes"
OUT = SRC / "scenes.inc.html"

# id prefix -> class(es) the stylesheet drives off data-step
CLASS_MAP = [
    (re.compile(r"^state-total$"),        "sc blob"),
    (re.compile(r"^district-pick$"),      "sc dist pick"),
    (re.compile(r"^district-\d+$"),       "sc dist"),
    (re.compile(r"^bar-g(\d)-\d+$"),      "sc bar g{0}"),
    (re.compile(r"^baseline$"),           "sc base"),
    (re.compile(r"^node-state$"),         "sc node top"),
    (re.compile(r"^node-district-\d+$"),  "sc node bot"),
    (re.compile(r"^flow-([01])$"),        "sc flow down"),
    (re.compile(r"^flow-([234])$"),       "sc flow up"),
    (re.compile(r"^term-(t\d)$"),         "sc term {0}"),
    (re.compile(r"^chain-dot-\d+$"),      "sc dot"),
    # on-canvas labels — reuse the same class as the element they annotate,
    # so they fade in/highlight in sync rather than sitting static
    (re.compile(r"^lbl-pick$"),           "dist pick"),
    (re.compile(r"^(val|lbl)-(t\d)$"),    "term {1}"),
    (re.compile(r"^lbl-(?:state|primary|secondary|tertiary|topstate|districts)$"), None),
]

SCENES = {
    "sc1.svg": "sc1",
    "sc2.svg": "sc2",
    "sc3.svg": "sc3",
    "sc4.svg": "sc4",
}


def classes_for(node_id):
    for pat, tpl in CLASS_MAP:
        m = pat.match(node_id)
        if m:
            return tpl.format(*m.groups()) if m.groups() else tpl
    return None


def convert(svg_text, root_id):
    # 1. drop Figma's grey export backing and the scene's own solid bg
    svg_text = re.sub(r'<rect width="460" height="340" fill="#E5E5E5"\s*/>\s*', "", svg_text)
    svg_text = re.sub(r'<rect width="460" height="340" fill="#0E4A3C"\s*/>\s*', "", svg_text)

    # 2. id -> class, keeping the id off the markup so nothing collides
    #    with the four copies of similar layer names across scenes
    def repl(m):
        node_id = m.group(1)
        cls = classes_for(node_id)
        return f'class="{cls}"' if cls else ""

    svg_text = re.sub(r'id="([a-z0-9\-]+)"', repl, svg_text)

    # 3. responsive root, carrying the scene id the CSS scopes on
    svg_text = re.sub(
        r"<svg[^>]*>",
        f'<svg id="{root_id}" viewBox="0 0 460 340" fill="none" '
        f'xmlns="http://www.w3.org/2000/svg" aria-hidden="true">',
        svg_text,
        count=1,
    )
    # the scene wrapper <g> lost its id in step 2; harmless, keep it
    return svg_text.strip()


def main():
    missing = [f for f in SCENES if not (SRC / f).exists()]
    if missing:
        raise SystemExit(f"missing export(s): {', '.join(missing)}\n"
                         f"re-export from Figma into {SRC}")

    parts = []
    for fname, root_id in SCENES.items():
        text = (SRC / fname).read_text()
        out = convert(text, root_id)
        parts.append(f"<!-- {root_id} — from Figma, do not hand-edit -->\n{out}")
        print(f"  {fname:9s} -> {root_id}  ({len(out)} bytes)")

    OUT.write_text("\n\n".join(parts) + "\n")
    print(f"\nwrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
