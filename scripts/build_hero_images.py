#!/usr/bin/env python3
"""Publish the home-page hero photographs from the drop folder.

The hero used to run assets/video/aerial.mp4 — generic stock-feel drone footage.
It now runs photographs of the actual Swarna Andhra capacity-building programme,
which is both truer to what the site is and cheaper to render: a cross-fade every
few seconds costs the compositor far less than a video decoding continuously
behind the frosted nav bar.

THE DROP FOLDER IS THE INTERFACE. Put a photo in homepageasset/, re-run this
script, and it appears in the rotation. Nothing else needs editing — not the
HTML, not a list somewhere. That is deliberate: more photographs are expected
over time and whoever adds them should not have to touch code.

What it does to each image:
  - caps the long edge at MAX_W so a 12-megapixel phone photo does not ship as
    an 8 MB hero,
  - re-encodes to progressive JPEG at QUALITY, which also strips EXIF (these are
    photographs of identifiable people at a government event, so the GPS and
    device tags that phones bake in have no business being published),
  - renames to a URL-safe slug — the source names are WhatsApp exports full of
    spaces and colons.

Ordering is by the timestamp in the filename when there is one, else by name, so
the sequence is stable across runs and does not reshuffle on every rebuild.

Output: landing/assets/hero/<slug>.jpg  +  landing/assets/hero/manifest.json

The manifest carries a `rev` — the max source mtime — which the page appends to
its fetch so a rebuild is picked up without a hand-edited cache stamp. The page
degrades in three steps: manifest missing -> aerial video; images fail -> the
existing .amb-fallback gradient; reduced-motion -> first frame only, no cycling.

Usage:
    python3 scripts/build_hero_images.py            # write
    python3 scripts/build_hero_images.py --check    # verify only, exit 1 on drift
"""
import json, os, re, sys

try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow is required: python3 -m pip install Pillow")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT, "homepageasset")
OUT_DIR = os.path.join(ROOT, "landing", "assets", "hero")
MANIFEST = os.path.join(OUT_DIR, "manifest.json")

EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic"}

# One catchy line per photograph, shown while that photo is on screen.
#
# Keyed by source filename. People are named ONLY where the slide behind them
# names them — those are readable in the frame, so the caption is quoting the
# event rather than my guess at who someone is. Faces I cannot verify from
# something written in the picture stay undescribed.
CAPTIONS = {
    "WhatsApp Image 2026-08-19 at 10.51.31.jpeg":
        "On the sidelines between sessions, where much of the real exchange "
        "actually happens.",
    "0W8A1306@13885089.JPG":
        "A full house of district officers, press cameras at the back, two days "
        "under way.",
    "0W8A1350.JPG":
        "Dr. Rajiv Kumar opens the method: how macroeconomic growth is actually "
        "measured.",
    "0W8A1727.JPG":
        "Ashish Kumar on Uttar Pradesh's experience compiling district domestic "
        "product for governance.",
    "0W8A2580@17520707.JPG":
        "Two days, one question: how officers read and use the numbers for their "
        "own district.",
    "0W8A3106@33840301.JPG":
        "The session on leveraging AI for economic estimation and governance data "
        "intelligence.",
    "0W8A3177@21918063.JPG":
        "Dr. Payal Seth on how administrative datasets can support faster, "
        "smarter policy design.",
    "0W8A3413@18685781.JPG":
        "The group photograph at the programme banner, Swarna Andhra @2047, "
        "July 2026.",
}
MAX_W = 1920
QUALITY = 82

# WhatsApp exports look like "WhatsApp Image 2026-08-19 at 13.45.09.jpeg".
# Pulling the stamp out gives a meaningful slug and a real sort key.
STAMP = re.compile(r"(\d{4}-\d{2}-\d{2})[^\d]+(\d{2})[.:](\d{2})[.:](\d{2})")


def slug_for(name):
    base = os.path.splitext(os.path.basename(name))[0]
    m = STAMP.search(base)
    if m:
        return "hero-{}-{}{}{}".format(m.group(1), m.group(2), m.group(3), m.group(4))
    s = re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")
    return "hero-" + (s or "image")


def sort_key(name):
    m = STAMP.search(os.path.basename(name))
    # Timestamped files first in chronological order, then everything else by
    # name. Two files can never tie, so the order is total and reproducible.
    return (0, m.group(0)) if m else (1, name.lower())


def main():
    check = "--check" in sys.argv

    if not os.path.isdir(SRC_DIR):
        sys.exit("missing drop folder: " + SRC_DIR)

    sources = [f for f in os.listdir(SRC_DIR)
               if os.path.splitext(f)[1].lower() in EXTS and not f.startswith(".")]
    if not sources:
        sys.exit("no images in " + SRC_DIR + " — the hero needs at least one")
    sources.sort(key=sort_key)

    rev = int(max(os.path.getmtime(os.path.join(SRC_DIR, f)) for f in sources))

    if not check:
        os.makedirs(OUT_DIR, exist_ok=True)

    slides, seen = [], {}
    for fn in sources:
        slug = slug_for(fn)
        if slug in seen:
            sys.exit("two sources produce the slug {!r}: {!r} and {!r}"
                     .format(slug, seen[slug], fn))
        seen[slug] = fn

        src = os.path.join(SRC_DIR, fn)
        out = os.path.join(OUT_DIR, slug + ".jpg")

        with Image.open(src) as im:
            im = im.convert("RGB")          # drops any alpha and every EXIF tag
            if im.width > MAX_W:
                im = im.resize((MAX_W, round(im.height * MAX_W / im.width)),
                               Image.LANCZOS)
            w, h = im.size
            if not check:
                im.save(out, "JPEG", quality=QUALITY, optimize=True,
                        progressive=True)

        slides.append({"src": "assets/hero/" + slug + ".jpg",
                       "w": w, "h": h, "source": fn,
                       "caption": CAPTIONS.get(fn, "")})

    data = {"rev": rev, "count": len(slides), "slides": slides}

    if check:
        if not os.path.exists(MANIFEST):
            sys.exit("--check: manifest missing, run without --check")
        with open(MANIFEST) as fh:
            have = json.load(fh)
        if have != data:
            sys.exit("--check: manifest is stale — {} slide(s) on disk vs {} "
                     "published. Re-run without --check."
                     .format(len(slides), have.get("count")))
        for s in slides:
            if not os.path.exists(os.path.join(ROOT, "landing", s["src"])):
                sys.exit("--check: published file missing: " + s["src"])
        print("--check: {} hero image(s) verified, nothing written".format(len(slides)))
        return

    # Anything previously published but no longer in the drop folder goes, or the
    # folder stops being the single source of truth.
    keep = {os.path.basename(s["src"]) for s in slides} | {"manifest.json"}
    for stale in sorted(set(os.listdir(OUT_DIR)) - keep):
        os.remove(os.path.join(OUT_DIR, stale))
        print("removed stale " + stale)

    with open(MANIFEST, "w") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")

    for s in slides:
        print("{}  {}x{}  <- {}".format(s["src"], s["w"], s["h"], s["source"]))

    # A photo with no caption still shows, it just runs without a line. Say so
    # loudly rather than failing the build, so dropping in a new picture is
    # never blocked on writing copy for it first.
    blank = [s["source"] for s in slides if not s["caption"]]
    if blank:
        print("\nNOTE: no caption for {} photo(s) — they will run without a "
              "line. Add them to CAPTIONS in this script:".format(len(blank)))
        for b in blank:
            print("    " + repr(b))
    print("wrote {} with {} slide(s), rev {}".format(
        os.path.relpath(MANIFEST, ROOT), len(slides), rev))


if __name__ == "__main__":
    main()
