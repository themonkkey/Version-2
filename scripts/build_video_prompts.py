#!/usr/bin/env python3
"""Emit one fully-expanded video-generation prompt per case-study background.

Every prompt is assembled from a LOCKED template plus a small variable set, so all
20 share byte-identical art-direction / composition / motion / negative blocks.
That sameness is the point: it is what makes the 20 loops feel like one system.

The locked constraints are derived from the real render pipeline in
scripts/proto_deck.py, not invented:
  - the slide overlays rgba(4,12,9,.35) -> rgba(4,12,9,.68) on the video, so the
    source must be MID-dark, not black, and detail belongs high in frame
  - the glass panel is backdrop-filter: blur(30px) saturate(1.3), so fine detail
    behind it is destroyed and saturation is boosted 30% -> art must be
    large-scale and desaturated
  - that blur recomputes per frame -> motion must be slow and low-frequency
  - the tint colours (#B7D66B/#7FD4E8/#E8C46B/#7FE3D6) are TEXT colours, so the
    video must not use them at strength or headings stop reading

Output: landing/cases/media/prompts/<nn>-<name>.txt  (+ INDEX.md)

    python3 scripts/build_video_prompts.py
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "landing", "cases", "media", "prompts")

# 12-colour ramps, anchored on the page background #06140F and muted so the UI
# accent colours stay legible on top. NEUTRAL is used for the shared role loops
# because they appear under every theme.
PALETTES = {
    "neutral": "#06140F #0A1310 #121A18 #1C2422 #28322E #3A4440 #4E5854 #646E68 #7C857E #241F19 #3A3228 #564A3C",
    "green":   "#06140F #0A1D14 #10291B #17371F #22482A #305C33 #42713D #57854B #6E9A5C #2A2419 #453A26 #6B5A3C",
    "aqua":    "#06140F #081B1E #0C2830 #123A45 #184F5C #217074 #2E8B90 #46A5A8 #63BCBE #1E2A30 #33434C #4E6068",
    "amber":   "#06140F #150E08 #241610 #3A2213 #55321A #74461F #925A26 #AE7233 #C68F49 #262019 #40372B #635646",
    "teal":    "#06140F #07201B #0B3029 #114438 #185C4A #22785F #2E9375 #45AC8C #62C4A5 #1F2A28 #364440 #4F6159",
}

TMPL = """PROMPT — {label}
FILE  -> landing/cases/media/{dest}
{usage}

################################################################################
#  PASTE THIS.  Everything below the second line is reference, not input.
#  Real tools ignore long prompts — Midjourney degrades past ~40 words, and
#  image-to-video models want one short instruction. So:
################################################################################

STEP 1 — make the still (Midjourney / Retro Diffusion / PixelLab):

{short_still}

STEP 2 — animate that still (Runway / Kling / Luma, image-to-video):

{short_motion}

################################################################################
#  FULL SPEC below — the contract behind the short prompt. Use it to judge a
#  result, to brief a human pixel artist, or to hand to a long-context model.
################################################################################
"""


SHORT_STILL = ("{scene_short}. 16-bit pixel art, heavy Bayer dithering, hard pixel edges, "
               "no anti-aliasing, strict {palname} palette of 12 dark muted colours, "
               "low-key and dark, single {temp} light {direction}, dim empty low-contrast "
               "centre with all detail pushed to the edges, no text, no logos, no faces, "
               "16:9")

SHORT_MOTION = ("Animate this image as a seamless 10-second loop. ONLY {motion_short} moves. "
                "Everything else is perfectly still. Camera completely locked — no pan, no "
                "zoom, no drift, no shake. Extremely subtle, slow, calm. No cuts, no flicker.")


FULL = """
Seamless looping ambient background video for a government economic case-study
website. It sits BEHIND a frosted-glass panel of white text, so it must read as a
quiet, dignified backdrop — never as the subject.

--- SCENE ---
{scene}

--- ART DIRECTION (locked) ---
Hand-crafted 16-bit pixel art in the tradition of SNES/Amiga atmospheric
backdrops and modern Lospec palette work. Serious, editorial, architectural —
NOT cute, NOT retro-gamey, NOT chiptune-whimsical. This illustrates public
economic policy: dignified and restrained.
Native render 480x270, 1:1 square pixels, NO anti-aliasing, hard pixel edges,
upscaled x4 with nearest-neighbour to 1920x1080. Ordered Bayer/checkerboard
dithering for every gradient — sky, haze, glow falloff, water. Visible dither
texture. No smooth blends, no gaussian softness, no photographic realism.

--- PALETTE (strict) ---
{palette}
Use these twelve values and nothing else. Anchor black is #06140F (the page
background) so the frame melts into the site. Maximum 3 shades per material.
DESATURATED throughout: the interface applies a +30% saturation boost over this
footage, so anything vivid at source turns garish. Mute it at source.
The brightest pixel in the frame must not exceed ~65% luminance. No white, no
blown highlights, no neon.

--- COMPOSITION (safe zone is non-negotiable) ---
16:9. Three depth layers: hard silhouette foreground, hazy dithered midground,
faded background.
The CENTRE of the frame — the middle 65% of width and 85% of height — must stay
DIM, CALM, LOW-CONTRAST and nearly static. A glass text panel covers it. No focal
point, no bright object, no busy detail, no motion there.
Push all structure, silhouette and interest to the LEFT edge, RIGHT edge and TOP
third. Horizon on the lower third. The bottom of the frame is darkened further by
the interface, so keep meaningful detail out of the lowest 15%.
{comp}

--- LIGHT ---
One single {temp} light source, {direction}, with a long dithered falloff into
deep shadow. Everything else unlit. Low-key throughout. Gentle vignette on all
four edges. Mid-dark overall — the interface darkens this footage a further 35%
at the top and 68% at the bottom, so do NOT deliver it already black; deliver it
readable and let the interface crush it.

--- MOTION (the hard constraint) ---
Seamless, perfectly tileable loop. 10 seconds, 12 fps, 120 frames. The last frame
must flow into the first with no jump, no fade, no cut.
AMBIENT MOTION ONLY: {motion}. Amplitude tiny — a few pixels of travel across the
whole loop. Slow, large-scale, low-frequency. Everything else in the frame is
PERFECTLY STILL: {still}.
NO camera movement of any kind: no pan, no zoom, no dolly, no parallax drift, no
handheld shake, no rotation. The camera is locked on a tripod and never moves.
NO cuts, no scene changes, no transitions, no flashing, no strobing, no rapid
flicker. Nothing that pulses faster than roughly once per two seconds.
This plays silently on loop behind text for minutes at a time — it must be
calming and almost subliminal. If a viewer notices the motion, it is too much.

--- ABSOLUTELY NOT ---
No text, letters, numbers, glyphs, signage, logos, watermarks, UI or HUD.
No recognisable human faces, no identifiable individuals, no crowds.
No brand marks, no flags, no religious or political symbols.
No photorealism, no 3D render look, no cinematic lens flare, no bokeh.
No bright washed-out regions, no high-contrast centre, no fast motion.

--- DELIVERY ---
1920x1080, H.264 .mp4, no audio, <=6 MB, exactly 10 s, loop-safe.

================================================================================
STILL VERSION: for a .jpg instead, use everything above except the MOTION block,
and render a single frame. Same file name with .jpg — the deck falls back to it.

METHOD: most video models ignore long negatives. Generate the STILL first
(Retro Diffusion / PixelLab / Midjourney), then animate that exact frame
image-to-video (Runway / Kling / Luma) feeding ONLY the MOTION block as the
instruction. Far more reliable, and the palette and safe zone survive.
"""

COVER_COMP = ("This is the opening title frame and carries the largest text panel of the "
              "deck, so protect the centre even more strictly than usual.")
ROLE_COMP = ("This background is reused across many case studies, so keep the scene "
             "generic and symbolic rather than tied to one place or industry.")

# (order, filename-stem, label, dest, usage, palette, scene, comp, temp, direction, motion, still)
COMMON = [
    ("context", "Shared role — CONTEXT (the wider picture / landscape / evolution)",
     "common/context.mp4",
     "Used by every slide about the bigger picture, global standing, background or evolution — across all 13 case studies.",
     "neutral",
     "A vast topographic landscape seen from high above at dusk — faint contour "
     "ridges stepping into the distance, a hazy far horizon, and one thin thread of "
     "warm light tracing a river as it winds through deep shadow. A sense of scale, "
     "geography and long time.",
     "cool", "low on the far horizon",
     "a slow band of low mist drifting horizontally across the far valley, travelling "
     "three or four pixels over the whole loop",
     "the ridgelines, the river, the sky and every shadow do not move at all"),

    ("action", "Shared role — ACTION (the problem / the case for action)",
     "common/action.mp4",
     "Used by every slide framing a problem, a trap, a gap or the case for action.",
     "neutral",
     "Raw unworked material resting in shadow inside a dim stone storehouse — rough "
     "uncut blocks of stone, a thick coil of rope, and stacked hessian sacks on a dark "
     "floor — with one hard shaft of pale light falling diagonally across them. The "
     "held stillness before work begins.",
     "cool", "from the upper-left, hard-edged and narrow",
     "suspended dust motes drifting slowly upward through the light shaft",
     "the stone, rope, sacks, walls and shadows do not move at all"),

    ("solution", "Shared role — SOLUTION (the answer / strategy / building the ecosystem)",
     "common/solution.mp4",
     "Used by every slide about the answer, the strategy, the opportunity or building an ecosystem.",
     "neutral",
     "The skeletal frame of something half-built at first light — scaffolding poles and "
     "converging structural beams taking shape, a dark foreground of stacked material "
     "rising toward a brightening pre-dawn edge. Quiet, ordered optimism.",
     "warm", "from the right, just above the horizon",
     "the dawn glow at the horizon breathing almost imperceptibly brighter and back "
     "again once across the loop",
     "the scaffolding, beams, material and foreground silhouettes do not move at all"),

    ("key-factors", "Shared role — KEY FACTORS (pillars / drivers / what worked / the model)",
     "common/key-factors.mp4",
     "Used by every slide about pillars, drivers, enablers, initiatives, success factors or the model itself.",
     "neutral",
     "Interlocking machinery in low light — a cluster of meshed gears, the edge of a "
     "lathe, and ordered rows of identical components laid out on a dark bench — sharp "
     "focused detail at the edges dissolving into blackness. A study in things made "
     "exactly right.",
     "warm", "from the lower-left, a single close lamp",
     "one large gear rotating very slowly, advancing a single tooth of travel across "
     "the whole loop",
     "the lathe, the bench, the components and all shadows do not move at all"),

    ("policy", "Shared role — POLICY (government support / schemes / institutions)",
     "common/policy.mp4",
     "Used by every slide about government support, schemes, incentives, policy or institutions.",
     "neutral",
     "Civic architecture in shadow — a heavy stone colonnade beside a grand flight of "
     "steps, strong parallel lines receding, and one soft pool of light resting on the "
     "stair. Weighty and institutional, with no signage of any kind.",
     "cool", "from high above, falling between the columns",
     "the pool of light on the steps shifting a pixel or two, as if cloud passes "
     "overhead",
     "the columns, the steps, the stonework and the architecture do not move at all"),

    ("challenges", "Shared role — CHALLENGES (risks / barriers / bottlenecks)",
     "common/challenges.mp4",
     "Used by every slide about challenges, risks, constraints, barriers or bottlenecks.",
     "neutral",
     "A narrow path squeezing through obstruction in gloom — mist pressed between two "
     "dark rock walls, a bottleneck of tangled fallen forms across the gap, and weather "
     "closing in from beyond. Friction and resistance rendered as texture, with no "
     "clear way through yet.",
     "cool", "diffuse, from behind the gap, silhouetting the rock",
     "fog rolling slowly through the gap, its dithered edges shifting",
     "the rock walls, the tangled forms and the ground do not move at all"),

    ("takeaways", "Shared role — TAKEAWAYS (lessons / roadmap / the way forward)",
     "common/takeaways.mp4",
     "Used by every slide about lessons, takeaways, roadmaps, recommendations or the way forward.",
     "neutral",
     "An empty road running out of deep shadow toward a low sunrise — clean receding "
     "perspective, the verges dark and simple, the frame opening up ahead into a pale "
     "dithered sky. Calm and resolved.",
     "warm", "from the vanishing point at the end of the road",
     "the sun's dithered glow at the vanishing point expanding and contracting by a "
     "few pixels",
     "the road, the verges, the horizon line and all shadows do not move at all"),
]

# (slug, palette, place-label, scene, temp, direction, motion, still)
COVERS = [
    ("east-godavari-coconut-coir", "green", "East Godavari — coconut & coir",
     "A dense coconut grove before sunrise — tall palm trunks in silhouette with their "
     "crowns fanning against a dim pearl sky, heaped stacks of coir husk piled in deep "
     "shadow along the foreground, and low mist lying over dark red soil between the "
     "rows.",
     "cool", "low from the right horizon, behind the palms",
     "mist drifting slowly between the trunks",
     "the palms, the husk stacks and the soil do not move at all"),

    ("nellore-shrimp-processing", "aqua", "Nellore — shrimp processing",
     "Coastal aquaculture ponds at blue hour — a vast rectangular grid of still dark "
     "water running to the horizon, faint ripple rings spreading from a distant "
     "aerator, and low earthen embankments with a single narrow walkway in silhouette.",
     "cool", "low on the horizon, the last light of dusk",
     "slow concentric ripple rings expanding across one distant pond",
     "the embankments, the walkway, the horizon and the sky do not move at all"),

    ("nellore-ethanol-potential", "aqua", "Nellore — ethanol potential",
     "A distillery skyline at dusk — cylindrical storage tanks and a lattice of pipework "
     "in hard silhouette, a low sodium glow along the horizon behind them, and fields of "
     "feedstock fading into shadow across the foreground.",
     "warm", "low from the left, using only the two warmest palette entries",
     "a thin plume of vapour rising slowly from one stack and dissipating",
     "the tanks, the pipework, the fields and the horizon do not move at all"),

    ("srikakulam-blue-economy", "aqua", "Srikakulam — blue economy",
     "A small fishing harbour at first light — dark wooden boats moored in a row, wet "
     "nets hanging from simple frames, a calm slate sea meeting a dim sky, and a low "
     "stone jetty running out to the right.",
     "cool", "low from the sea horizon, pre-dawn",
     "a gentle swell rocking the moored hulls by a pixel or two",
     "the jetty, the nets, the frames and the sky do not move at all"),

    ("shenzhen-growth-model", "amber", "Shenzhen — port-led manufacturing",
     "A vast container port at night seen from a distance — dark stacked container "
     "blocks forming a low city of rectangles, tall gantry cranes in hard silhouette "
     "along the skyline, and sparse dim sodium lights scattered through the yard under "
     "a starless sky.",
     "warm", "sparse dim sodium lamps scattered low in the yard",
     "one gantry crane trolley inching slowly along its rail",
     "the containers, the cranes, the yard and the sky do not move at all"),

    ("morbi-ceramic-cluster", "amber", "Morbi — ceramic cluster",
     "The dark interior of a ceramic tile factory at night — the mouth of a kiln glowing "
     "deep orange as the only light source, long rows of stacked tiles receding into "
     "blackness on the right, heavy machinery in hard silhouette, and faint heat-haze "
     "rising through the ember light.",
     "warm", "from the lower-left kiln mouth, the only source in the frame",
     "the kiln glow flickering gently and the heat-haze drifting upward",
     "the tiles, the machinery, the walls and the floor do not move at all"),

    ("tiruppur-textiles", "amber", "Tiruppur — textiles & garments",
     "A dim knitwear mill — rows of circular knitting machines receding into shadow, "
     "fine threads running up to the ceiling and catching the light of a single low "
     "lamp, and bolts of finished fabric stacked heavily along the left wall.",
     "warm", "a single low lamp hanging over the machines on the left",
     "one yarn spool rotating slowly on its spindle",
     "the machines, the fabric bolts, the threads and the walls do not move at all"),

    ("kumarakom-tourism", "teal", "Kumarakom — responsible tourism",
     "Kerala backwaters before dawn — the silhouette of a moored houseboat on glassy "
     "still water, dense palms crowding the far bank, low mist across the channel, and "
     "one small warm lantern casting a long reflection down the water.",
     "warm", "a single small lantern on the houseboat",
     "the lantern's reflection wavering gently on the water surface",
     "the houseboat, the palms, the bank and the mist do not move at all"),

    ("sahyadri-farms-fpc", "green", "Sahyadri Farms — FPC model",
     "Terraced hill farms in the Western Ghats at dusk — dark rolling ridgelines "
     "stepping back in layers, mist pooled in the valleys between them, and orderly "
     "rows of vine and vegetable terraces fading into shadow in the foreground.",
     "cool", "low behind the furthest ridgeline",
     "valley mist drifting slowly between the ridges",
     "the terraces, the ridgelines, the crop rows and the sky do not move at all"),

    ("chetna-organics-fpo", "green", "Chetna Organics — FPO",
     "A close, low-light study of raw organic cotton bolls held in cupped hands over a "
     "dark cloth — deep shadow all around, one soft shaft of window light falling "
     "across the cotton, the weave of the cloth and the fibre of the bolls sharply "
     "textured. Framed at the hands only, no face and no figure visible.",
     "cool", "one soft window shaft from the upper-left",
     "dust motes drifting slowly through the window light",
     "the hands, the cotton, the cloth and the shadows do not move at all"),

    ("biofloc-tilapia", "aqua", "Biofloc tilapia farming",
     "Rows of large circular biofloc tanks under a dim shed roof — still dark water "
     "surfaces catching faint light, simple pipework and aeration lines running between "
     "the tanks, and the roof structure receding into shadow overhead.",
     "cool", "faint daylight leaking in from the open end of the shed",
     "a faint shimmer crossing the water surface of one tank",
     "the tanks, the pipework, the roof and the floor do not move at all"),

    ("paddy-fish-farming", "green", "Paddy + fish integrated farming",
     "A flooded paddy field at blue hour — a grid of dark earthen bunds dividing sheets "
     "of still water that mirror the dim sky, young rice shoots breaking the surface in "
     "even rows, and a treeline in silhouette along the far edge.",
     "cool", "low on the horizon behind the treeline",
     "a slow ripple crossing the water of one flooded bay and settling",
     "the bunds, the rice shoots, the treeline and the sky do not move at all"),

    ("banana-processing", "green", "Banana processing & waste-to-wealth",
     "A dark banana plantation at the edge of a shaded processing shed — broad heavy "
     "leaves overlapping in deep shadow, stacked green bunches resting under the shed "
     "roof, and a single shaft of light falling across the working floor.",
     "warm", "a single shaft entering from the right side of the shed",
     "one broad leaf swaying almost imperceptibly",
     "the bunches, the shed, the floor and the other leaves do not move at all"),
]


PAL_WORDS = {"neutral": "dark slate-grey", "green": "dark muted green",
             "aqua": "dark teal-blue", "amber": "dark amber-brown",
             "teal": "dark teal"}


def condense(text, limit=190):
    """First clause of a long description — the bit a short prompt can carry."""
    t = " ".join(text.split())
    for sep in (" — ", ". "):
        if sep in t:
            t = t.split(sep)[0]
            break
    return t[:limit].rstrip(" ,.")


def write(n, stem, label, dest, usage, palette, scene, comp, temp, direction, motion, still):
    short_still = SHORT_STILL.format(
        scene_short=condense(scene), palname=PAL_WORDS[palette],
        temp=temp, direction=condense(direction, 60))
    short_motion = SHORT_MOTION.format(motion_short=condense(motion, 110))
    body = TMPL.format(
        label=label, dest=dest, usage=usage,
        short_still=short_still, short_motion=short_motion) + FULL.format(
        palette=PALETTES[palette], scene=scene,
        comp=comp, temp=temp, direction=direction, motion=motion, still=still)
    name = f"{n:02d}-{stem}.txt"
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        f.write(body)
    return name, label, dest


def main():
    os.makedirs(OUT, exist_ok=True)
    rows = []
    n = 1
    for stem, label, dest, usage, pal, scene, temp, direction, motion, still in COMMON:
        rows.append(write(n, "common-" + stem, label, dest, usage, pal, scene,
                          ROLE_COMP, temp, direction, motion, still))
        n += 1
    for slug, pal, place, scene, temp, direction, motion, still in COVERS:
        rows.append(write(
            n, "cover-" + slug, f"Cover: {place}", f"{slug}/0.mp4",
            f"The opening title slide of the {place} case study.",
            pal, scene, COVER_COMP, temp, direction, motion, still))
        n += 1

    with open(os.path.join(OUT, "INDEX.md"), "w", encoding="utf-8") as f:
        f.write("# Video prompts — one file per background\n\n"
                "Open a file, copy the whole thing, paste into your image/video tool.\n"
                "Make the 7 shared role loops first: they back every slide of all 13 "
                "case studies. The 13 covers are the opening frame of each study.\n\n"
                "| # | File | What it is | Goes to |\n|---|---|---|---|\n")
        for i, (name, label, dest) in enumerate(rows, start=1):
            f.write(f"| {i:02d} | `{name}` | {label} | `media/{dest}` |\n")

    print(f"wrote {len(rows)} prompt files + INDEX.md -> {os.path.relpath(OUT, ROOT)}")


if __name__ == "__main__":
    main()
