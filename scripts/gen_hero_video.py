#!/usr/bin/env python3
"""Generate the landing-page ambient hero loop.

Eight visual directions, each written as a full Veo prompt. Pick one with
--style; see them all with --list.

Two-stage by default, because Veo will not hold a specific art direction from
prose alone — it drifts toward generic photoreal. Gemini Image pins the look in
a still first, then Veo animates that exact frame, so the image locks the style:

    stage 1  Gemini 3.1 Flash Image -> style frame (assets/video/hero-frame.png)
    stage 2  Veo 3.1                -> 8s loop     (assets/video/hero-loop.mp4)

Photoreal styles (aerial, ledger, refraction, ink, handloom, longexposure) can
skip stage 1 with --no-frame; Veo handles those unaided. The two illustrated
styles (vector, isometric) should always use the frame.

Requires billing on the Google Cloud project behind GEMINI_API_KEY. On the free
tier both stages return 429 RESOURCE_EXHAUSTED — quota is zero, not low.

    python3 scripts/gen_hero_video.py --list
    python3 scripts/gen_hero_video.py --style aerial --frame     # cheap look test
    python3 scripts/gen_hero_video.py --style aerial             # full loop
"""
import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "landing" / "assets" / "video"

# Applies to every style. Veo obeys negatives far better when they are explicit
# and repeated, and any text in frame will fight the headline sitting over it.
COMMON = (
    "Locked-off camera, no camera shake, no zoom, no whip pans, no cuts, "
    "single continuous shot. Seamless loop: the last frame matches the first. "
    "Very slow, calm, unhurried motion throughout. "
    "The centre of frame stays visually quiet and low-contrast so overlaid "
    "white headline text remains readable; detail and interest live toward the "
    "edges and corners. "
    "Absolutely no text, no letters, no numbers, no captions, no subtitles, "
    "no watermarks, no logos, no UI overlays, no人 faces looking at camera."
).replace("no人", "no ")

STYLES = {
    # ---------------------------------------------------------------- 1
    "aerial": {
        "name": "Aerial delta — Andhra from above",
        "why": "The AP economy literally is the delta, the ports and the "
               "aquaculture belt. Shows the subject rather than decorating it.",
        "scrim": "rgba(11,46,32,.74) → .66 → .82, plus a green radial at 78% 8%",
        "frame_needed": False,
        "look": (
            "Cinematic aerial drone shot, high altitude, looking straight down "
            "at the Krishna–Godavari delta in coastal Andhra Pradesh, India. A "
            "mosaic of paddy fields in a dozen shades of green, rectangular "
            "aquaculture ponds catching the sky, thin irrigation channels "
            "threading between them, a wide river braiding toward the coast. "
            "Soft early-morning light, long low sun, faint haze. Muted and "
            "desaturated, greens and teals dominant, no vivid saturation. "
            "Shot on a full-frame sensor, natural colour grade, filmic."
        ),
        "motion": (
            "The drone drifts forward almost imperceptibly at constant altitude. "
            "Water surfaces shimmer faintly. Thin cloud shadows travel slowly "
            "across the fields. Nothing else moves."
        ),
    },
    # ---------------------------------------------------------------- 2
    "refraction": {
        "name": "Light through frosted glass",
        "why": "Purpose-built for the glassmorphism. The panels blur real "
               "refraction instead of a flat colour — the effect finally has "
               "something worth blurring.",
        "scrim": "rgba(11,46,32,.60) → .52 → .74 — lighter, let caustics through",
        "frame_needed": False,
        "look": (
            "Extreme macro abstract. Soft daylight passing through several "
            "overlapping sheets of thick frosted and ribbed glass, throwing "
            "caustic patterns and soft-edged light pools onto a dark surface "
            "behind. Deep teal-green and near-black, with occasional pale "
            "lime-green highlights where the light concentrates. Heavy bokeh, "
            "very shallow depth of field, most of the frame out of focus. "
            "No objects are identifiable — pure light, colour and blur."
        ),
        "motion": (
            "The glass sheets drift past each other with extreme slowness, so "
            "the caustic pools stretch, merge and separate. Focus breathes "
            "gently in and out. No hard edges ever resolve."
        ),
    },
    # ---------------------------------------------------------------- 3
    "ink": {
        "name": "Ink diffusing in water",
        "why": "The safest bet for a clean generation — Veo handles fluid "
               "extremely well, and it loops almost invisibly. Abstract, so "
               "nothing can look factually wrong.",
        "scrim": "rgba(11,46,32,.68) → .60 → .80",
        "frame_needed": False,
        "look": (
            "Macro shot of deep green and teal ink dispersing through still "
            "clear water, lit from behind so the plumes glow at their thin "
            "edges. Dark near-black background. Delicate tendrils and soft "
            "billowing clouds of pigment, occasional pale lime filaments. "
            "Studio macro lens, high detail in the pigment, shallow depth of "
            "field. Elegant and slow, not chaotic or explosive."
        ),
        "motion": (
            "The ink unfurls and spreads with great slowness, tendrils curling "
            "outward and thinning. Water is otherwise perfectly still. No "
            "splashes, no drops entering frame, no turbulence."
        ),
    },
    # ---------------------------------------------------------------- 4
    "handloom": {
        "name": "Handloom weave, macro",
        "why": "Rooted in Andhra — Mangalagiri and Venkatagiri weaving. Warm "
               "and human where the other options are cool and technical, and "
               "the thread grid echoes the district grid in the diagrams.",
        "scrim": "rgba(11,46,32,.72) → .64 → .84",
        "frame_needed": False,
        "look": (
            "Extreme macro of handloom cotton fabric being woven on a wooden "
            "pit loom. Fine warp threads in undyed cream running the length of "
            "frame, weft threads in deep green and teal crossing them. Visible "
            "fibre texture, soft raking side light picking out every thread, "
            "warm dark background falling away out of focus. Shallow depth of "
            "field. Handmade, tactile, quiet. No hands or faces in frame."
        ),
        "motion": (
            "A single weft thread advances across the warp with slow steady "
            "regularity. The fabric shifts a fraction under tension. Fine "
            "fibres catch the light as they move. Nothing else changes."
        ),
    },
    # ---------------------------------------------------------------- 5
    "ledger": {
        "name": "Ledger and paper, macro",
        "why": "Institutional and sober. Signals official statistics without "
               "any illustration risk. The most conservative pick.",
        "scrim": "rgba(11,46,32,.78) → .70 → .86 — paper is bright, push it back",
        "frame_needed": False,
        "look": (
            "Extreme macro across an old official statistical ledger lying "
            "open on a dark wooden desk. Faint printed grid rules, aged paper "
            "fibre visible, a fountain pen resting across one page, a folded "
            "map edge just entering the corner of frame. Single soft window "
            "light from the left, deep shadow to the right. Muted, "
            "desaturated, greens and warm greys. Very shallow depth of field, "
            "most of the frame softly out of focus."
        ),
        "motion": (
            "The camera holds still while a slow shadow shifts across the page, "
            "as though a cloud is passing the window. One page corner lifts and "
            "settles very slightly in a draught. Dust motes drift through the "
            "light beam."
        ),
    },
    # ---------------------------------------------------------------- 6
    "longexposure": {
        "name": "Night light trails — ports and highways",
        "why": "Reads as economic activity and movement. The strongest choice "
               "if you want the hero to feel like momentum rather than calm.",
        "scrim": "rgba(11,46,32,.70) → .62 → .82",
        "frame_needed": False,
        "look": (
            "Long-exposure night aerial over an Indian industrial port and the "
            "highway network behind it. Vehicle headlights and taillights drawn "
            "into continuous ribbons of light, gantry cranes lit in cool white, "
            "container stacks in shadow. Deep teal-black sky, no stars. "
            "Restrained palette: dark green-black with white and faint lime "
            "light trails. Cinematic, high contrast at the edges, dark centre."
        ),
        "motion": (
            "The light ribbons flow steadily along their paths. A crane arm "
            "tracks slowly. The camera holds completely still. No flashing, no "
            "strobing, no sudden brightness changes."
        ),
    },
    # ---------------------------------------------------------------- 7
    "vector": {
        "name": "Flat vector illustration",
        "why": "Matches the Figma diagrams on the Methodology page. Hardest to "
               "generate — always use the style frame, and expect several "
               "attempts.",
        "scrim": "rgba(11,46,32,.66) → .58 → .78",
        "frame_needed": True,
        "look": (
            "Flat 2D vector illustration, modern editorial infographic style. "
            "Bold clean outlines, solid fills, absolutely no gradients, no "
            "shading, no drop shadows, no 3D, no photorealism, no texture. "
            "Strict palette: deep teal-green background, mid teal, soft sage, "
            "off-white, one lime accent, one warm ochre accent used sparingly. "
            "Scene: five simplified human figures at desks arranged around the "
            "edges of frame, each inside a rounded rectangle panel, working "
            "with laptops and documents. Thin connecting lines run between the "
            "panels through open space. A potted plant, a sleeping cat on one "
            "panel edge. Centre of frame deliberately empty."
        ),
        "motion": (
            "Small dots travel slowly along the lines connecting the panels. "
            "The figures make tiny idle gestures — typing, nodding. Plant "
            "leaves sway a little. Everything else is perfectly still."
        ),
    },
    # ---------------------------------------------------------------- 8
    "isometric": {
        "name": "Isometric miniature district",
        "why": "Charming and legible, and it can carry real content — port, "
               "fields, solar, rail. Riskier than photoreal but easier than "
               "flat vector.",
        "scrim": "rgba(11,46,32,.68) → .60 → .80",
        "frame_needed": True,
        "look": (
            "Isometric 3D miniature diorama of a stylised coastal Indian "
            "district, tilt-shift, clean low-poly forms with soft matte "
            "surfaces. Paddy terraces, a small port with two cranes, a solar "
            "array, a rail line, a cluster of low buildings. Deep teal-green "
            "base, sage and off-white structures, a single lime accent on the "
            "cranes. Soft even studio lighting, gentle ambient shadows, no "
            "harsh speculars. Sits on a dark background with space around it."
        ),
        "motion": (
            "The cranes rotate very slowly. A tiny train crosses the rail line "
            "at a crawl. Water at the port edge ripples faintly. The diorama "
            "itself does not rotate and the camera does not move."
        ),
    },
}


def load_env():
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k, v)


def show_list():
    print("\n  Ambient hero styles — pick with --style <id>\n")
    for k, s in STYLES.items():
        frame = "frame required" if s["frame_needed"] else "frame optional"
        print(f"  {k:<13} {s['name']}")
        print(f"  {'':<13} {s['why']}")
        print(f"  {'':<13} [{frame}]  scrim: {s['scrim']}\n")


def die(stage, err):
    s = str(err)
    print(f"\n  {stage} failed: {type(err).__name__}")
    if "RESOURCE_EXHAUSTED" in s or "429" in s:
        print("  Quota is zero for this model on the current key.")
        print("  Veo and Gemini image generation are not on the free tier —")
        print("  enable billing on the Google Cloud project, then re-run.")
    elif "NOT_FOUND" in s:
        print("  Model unavailable to this key. imagen-4.0-* is closed to new")
        print("  users; the Gemini image models are the open path.")
    else:
        print(f"  {s[:400]}")
    sys.exit(1)


def make_frame(client, style, path):
    prompt = (
        f"Generate a 16:9 image.\n\n{style['look']}\n\n"
        "No text, letters, numbers, watermarks or logos anywhere in the image. "
        "Keep the centre of the composition quiet and low-contrast."
    )
    print(f"  Gemini 3.1 Flash Image -> {path.name}")
    try:
        r = client.models.generate_content(
            model="gemini-3.1-flash-image", contents=prompt
        )
    except Exception as e:
        die("image generation", e)
    for part in r.candidates[0].content.parts:
        if getattr(part, "inline_data", None):
            path.write_bytes(part.inline_data.data)
            print(f"  saved {path} ({path.stat().st_size // 1024} KB)")
            return True
    print("  model returned text only, no image — reword or retry")
    return False


def make_video(client, style, frame_path, out_path, use_frame):
    from google.genai import types
    prompt = f"{style['look']}\n\n{style['motion']}\n\n{COMMON}"
    print(f"  Veo 3.1 -> {out_path.name}  (1-3 min)")
    kwargs = dict(
        model="veo-3.1-generate-preview",
        prompt=prompt,
        config=types.GenerateVideosConfig(aspect_ratio="16:9"),
    )
    if use_frame and frame_path.exists():
        kwargs["image"] = types.Image.from_file(location=str(frame_path))
        print("  (animating the style frame — look stays locked)")
    try:
        op = client.models.generate_videos(**kwargs)
        while not op.done:
            time.sleep(10)
            print("    ...rendering")
            op = client.operations.get(op)
    except Exception as e:
        die("Veo", e)
    vid = op.response.generated_videos[0]
    client.files.download(file=vid.video)
    vid.video.save(str(out_path))
    print(f"  saved {out_path} ({out_path.stat().st_size // 1024} KB)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--style", default="aerial", choices=sorted(STYLES))
    ap.add_argument("--list", action="store_true", help="show all styles")
    ap.add_argument("--frame", action="store_true", help="style frame only")
    ap.add_argument("--no-frame", action="store_true",
                    help="skip the style frame, prompt Veo directly")
    ap.add_argument("--print-prompt", action="store_true",
                    help="print the full prompt without calling the API")
    args = ap.parse_args()

    if args.list:
        show_list()
        return

    style = STYLES[args.style]

    if args.print_prompt:
        print(f"\n=== {args.style} — {style['name']} ===\n")
        print(f"{style['look']}\n\n{style['motion']}\n\n{COMMON}\n")
        print(f"--- suggested .amb-scrim: {style['scrim']}\n")
        return

    load_env()
    if not os.environ.get("GEMINI_API_KEY"):
        sys.exit("GEMINI_API_KEY not set (looked in .env)")

    from google import genai
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    OUT.mkdir(parents=True, exist_ok=True)

    print(f"\n{args.style} — {style['name']}\n")
    frame = OUT / "hero-frame.png"
    use_frame = style["frame_needed"] and not args.no_frame

    if use_frame or args.frame:
        ok = make_frame(client, style, frame)
        if args.frame:
            print("\nStyle frame done. Review, then re-run without --frame.\n")
            return
        if not ok:
            use_frame = False

    make_video(client, style, frame, OUT / "hero-loop.mp4", use_frame)
    print(f"\nDone. Set .amb-scrim to: {style['scrim']}")
    print("Compress before shipping:")
    print("  ffmpeg -i landing/assets/video/hero-loop.mp4 -vf scale=1600:-2 \\")
    print("    -c:v libx264 -crf 30 -preset slow -an -movflags +faststart \\")
    print("    landing/assets/video/hero-loop.web.mp4\n")


if __name__ == "__main__":
    main()
