# Sector panel loops — master prompt

Three looping videos, one behind each panel of the **Improving GVA** accordion.

```
landing/assets/sectors/
├── agriculture.mp4     ← panel 01  (hue #6FA817 green)
├── industry.mp4        ← panel 02  (hue #2B93BF blue)
└── services.mp4        ← panel 03  (hue #BF8A2B amber)
```

Drop a file in with the exact name and it appears — **no code change**. If a file
isn't there the `<video>` removes itself on 404 and the tinted gradient stays, so
the page is never broken by a missing or half-made clip. Same for a still: name it
`.mp4` or don't ship it; there is no image fallback path.

---

## 1. The hard constraint — read this before generating anything

Each panel is cropped to **three very different shapes** as the accordion moves,
using `object-fit: cover` centred. Measured on the live page:

| State | Box | Aspect |
|---|---|---|
| **At rest** (3 equal panels) | 393 × 440 | **0.89** — near square |
| **Collapsed strip** (another panel open) | 78 × 440 | **0.18** — extremely tall |
| Open panel | 1022 × 440 | 2.32 — but the scrim goes to 86% opacity here, so the footage barely reads. Don't compose for it. |

**Generate 9:16 vertical, 1080 × 1920.** With that source:
- at rest you see the **full width, centre 63% of height**
- as a strip you see the **centre 32% of width, full height**

So the only region visible in *every* state is the **centre 32% of width × centre
63% of height**. Everything that matters goes there. Anything in the outer thirds
is decoration that will be cropped away half the time — texture, not subject.

A 16:9 source would leave only a ~10% slice visible in the strip. Don't use one.

---

## 2. Universal style block — paste at the end of every prompt

> Flat editorial illustration, screen-print / risograph feel — layered flat shapes,
> depth from value not from detail, fine paper grain, subtle halftone in the large
> areas. Limited palette, near-monochrome, very low saturation, dark and low-key
> throughout. Calm uncluttered centre column. No text, no logos, no readable faces,
> no signage. Vertical 9:16 composition.

**Why low-key and desaturated:** a coloured scrim in that panel's own hue sits on
top at 62–80% opacity, and white title text sits on top of that. Anything bright,
busy or saturated at source turns muddy under the tint and eats the text's
contrast. Grade it flatter and darker than feels right — the interface supplies
all the colour.

**Palette** — build each from the site's ink plus that panel's hue only:

| Panel | Ink base | Hue | Use |
|---|---|---|---|
| Agriculture | `#08221A` `#0E2E22` `#16382A` | `#6FA817` | one or two accents only |
| Industry | `#0A1E28` `#102A36` `#183744` | `#2B93BF` | one or two accents only |
| Services | `#241B0E` `#2E2413` `#3A2E19` | `#BF8A2B` | one or two accents only |

---

## 3. Motion spec — applies to all three

Seamless **10-second loop**, and the emphasis is on *seamless*: last frame must
equal first. **The camera is locked** — no pan, no zoom, no drift, no parallax
push, no shake. Only one or two small things move, and they move slowly:
a ripple, a plume, a rotation, a light. Everything else is perfectly still.

These sit behind text a reader is trying to read. Motion that pulls the eye is a
bug. If you're unsure whether it's too much, it's too much.

**Export:** H.264 .mp4, 1080 × 1920, 24 or 25 fps, **under 3 MB each** (they ship
in a static site alongside 2 MB of other assets). Muted — they autoplay silently.

---

## 4. Panel 01 — AGRICULTURE  → `agriculture.mp4`

Covers **Crops · Livestock & Fisheries · Forestry & Logging**. This is the delta
economy: paddy, horticulture, and the aquaculture belt that makes Andhra the
country's biggest fish and shrimp producer.

**STEP 1 — the still:**

> Vertical illustrated landscape of a river delta seen from a low hill at dusk.
> Foreground: flooded paddy fields as flat stepped shapes, their water catching a
> thin sheet of pale light. Midground: a grid of rectangular aquaculture ponds
> receding into haze, each a slightly different dark tone. Background: a line of
> coconut palms in silhouette and low hills fading out. Flat editorial
> illustration, screen-print / risograph feel, layered flat shapes, depth from
> value not detail, fine paper grain, subtle halftone. Near-monochrome deep green
> palette #08221A #0E2E22 #16382A with a single muted green accent #6FA817 on the
> water only. Dark, low-key, calm uncluttered centre column, generous negative
> space. No text, no logos, no faces. Vertical 9:16.

**STEP 2 — animate it (image-to-video):**

> Animate as a seamless 10-second loop. ONLY the sheet of light on the paddy water
> shifts, very slowly, as if a cloud were passing — and one distant bird crosses
> the upper third once. Everything else perfectly still. Camera completely locked:
> no pan, no zoom, no drift. Extremely subtle and calm. No cuts, no flicker.

---

## 5. Panel 02 — INDUSTRY  → `industry.mp4`

Covers **Mining & Quarrying · Manufacturing · Electricity, Gas & Water ·
Construction**. Note mining belongs here, not with agriculture — Andhra reports on
the state classification.

**STEP 1 — the still:**

> Vertical illustrated industrial landscape at blue hour, stacked in three bands.
> Bottom: the stepped benches of a stone quarry as flat geometric terraces.
> Middle: the long low roofline of a factory shed with two slim chimneys, a thin
> pale plume rising from one. Top: a row of electricity transmission pylons and a
> single tower crane in silhouette against an empty sky. Flat editorial
> illustration, screen-print / risograph feel, layered flat shapes, depth from
> value not detail, fine paper grain, subtle halftone. Near-monochrome deep slate
> blue palette #0A1E28 #102A36 #183744 with a single muted blue accent #2B93BF on
> the sky gradient only. Dark, low-key, calm uncluttered centre column. No text,
> no logos, no faces. Vertical 9:16.

**STEP 2 — animate it (image-to-video):**

> Animate as a seamless 10-second loop. ONLY the thin plume from the chimney
> drifts slowly upward and dissipates, and one small red aircraft-warning light on
> the tallest pylon blinks twice across the loop. Everything else perfectly still —
> the crane does not move. Camera completely locked: no pan, no zoom, no drift.
> Extremely subtle and calm. No cuts, no flicker.

---

## 6. Panel 03 — SERVICES  → `services.mp4`

Covers **Trade, Hotels & Tourism · Transport, Storage & Communication · Financial ·
Real Estate · Public Administration · Education & Health**. Six sub-sectors, so
this one is deliberately the most layered — a port city at night.

**STEP 1 — the still:**

> Vertical illustrated port city at night, stacked in three bands. Bottom: rows of
> stacked shipping containers as flat rectangles and the legs of two gantry cranes.
> Middle: a dense low skyline of shophouses and a covered market arcade, small warm
> windows scattered through it. Top: the tiered silhouette of a temple gopuram
> beside a plain modern civic tower, with a slim telecom mast, against an empty
> sky. Flat editorial illustration, screen-print / risograph feel, layered flat
> shapes, depth from value not detail, fine paper grain, subtle halftone.
> Near-monochrome deep warm brown palette #241B0E #2E2413 #3A2E19 with a single
> muted amber accent #BF8A2B on the windows only. Dark, low-key, calm uncluttered
> centre column. No text, no logos, no faces, no signage. Vertical 9:16.

**STEP 2 — animate it (image-to-video):**

> Animate as a seamless 10-second loop. ONLY a slow horizontal creep of one gantry
> crane trolley across the bottom band, and a few of the small warm windows fading
> up and down at different times. Everything else perfectly still. Camera
> completely locked: no pan, no zoom, no drift. Extremely subtle and calm. No cuts,
> no flicker.

---

## 7. Checking a result before you ship it

1. **Crop test first.** Before anything else, view the clip masked to a
   **78 × 440** centre strip. If the subject disappears or turns to mush, the
   composition is wrong — regenerate, don't fix it in CSS.
2. **Text test.** Put white 27px bold text over the top-left and a white pill
   bottom-left. Both must stay comfortably readable with the tint on.
3. **Loop test.** Play it ten times. If you can see the seam, it isn't done.
4. **Weight test.** Over 3 MB, re-encode: `ffmpeg -i in.mp4 -c:v libx264 -crf 30
   -preset slow -an -vf scale=1080:1920 out.mp4`
5. **Motion test.** Look away and read the panel title. If the movement pulls your
   eye back, cut the motion further.

---

## 8. If you want stills instead

The panes only load `.mp4`. To use a still, either export a 10-second static clip,
or ask for the `--img` route to be re-enabled — each pane already carries a
`--img` custom property that takes a `url(...)`, it just isn't populated. One line
of CSS per sector.
