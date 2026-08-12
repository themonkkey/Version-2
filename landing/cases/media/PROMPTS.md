# Case-study backgrounds — media folder + master generation prompts

These images/videos sit **behind a frosted-glass panel** on each case-study slide.
The deck already works without them (a tinted mesh gradient shows). Drop a file in
the right place and it appears automatically — no code change.

---

## 1. How the folder works

```
landing/cases/media/
├── common/                 ← shared, reused across ALL 13 case studies
│   ├── context.jpg   (or .mp4)
│   ├── action.jpg
│   ├── solution.jpg
│   ├── key-factors.jpg
│   ├── policy.jpg
│   ├── challenges.jpg
│   └── takeaways.jpg
└── <case-slug>/            ← optional, overrides common for THAT case only
    ├── 0.jpg               ← cover slide
    ├── 1.jpg               ← section 1, 2.jpg = section 2, …
    └── …
```

**Resolution order per slide (first that exists wins):**
1. `media/<slug>/<n>.mp4` → `media/<slug>/<n>.jpg`  (case-specific, by slide number)
2. `media/common/<role>.mp4` → `media/common/<role>.jpg`  (shared, by role)
3. tinted mesh gradient (built in, always there)

So: make the **7 common role files once** and every case is covered. Add a
per-case `0.jpg` cover (and any section override) only where you want something
literal for that place.

**Case slugs:** `east-godavari-coconut-coir`, `nellore-shrimp-processing`,
`nellore-ethanol-potential`, `srikakulam-blue-economy`, `shenzhen-growth-model`,
`morbi-ceramic-cluster`, `tiruppur-textiles`, `kumarakom-tourism`,
`sahyadri-farms-fpc`, `chetna-organics-fpo`, `biofloc-tilapia`,
`paddy-fish-farming`, `banana-processing`.

**Which role does each slide get?** By its section title: problem/why → `action`;
answer/strategy/opportunity → `solution`; pillars/drivers/initiatives/model →
`key-factors`; government/scheme/support → `policy`; global/context/evolution →
`context`; risks/barriers → `challenges`; lessons/roadmap/way-forward →
`takeaways`.

---

## 2. File specs (read before generating)

- **Aspect 16:9**, min **1920×1080** (2560×1440 better). Covers can be portrait-safe but export 16:9.
- **Dark and low-key.** White text sits on top — the image must stay dim, especially mid-frame. Think "lights off, one soft source."
- **Desaturated / muted.** The UI adds the colour accent; a loud photo fights it.
- **Calm centre, texture at the edges.** The glass panel covers the middle third.
- **No text, no logos, no watermarks, no recognisable faces.**
- **Video:** 6–12 s **seamless loop**, slow/subtle motion, H.264 .mp4, keep under ~6 MB (these ship in a static site). Muted (autoplays silently).
- Export images as **.jpg** (~80% quality) to keep the page light.

---

## 3. Universal style suffix — paste at the END of every prompt below

Style is **pixel art**, not photography — dark and limited-palette so white text
still reads over it. Swap `[PALETTE]` per prompt (see §4/§5).

> detailed 16-bit pixel art, limited cohesive [PALETTE] palette, soft dithering
> and gentle gradients, dark low-key atmospheric mood, calm dim uncluttered
> centre, generous negative space, no text, no logos, no readable faces, 16:9 —
> kept dark enough that white text overlays it cleanly

For Midjourney add: `pixel art --ar 16:9 --stylize 120` (or use a pixel model —
Retro Diffusion, PixelLab.ai).
For **animated** pixel (recommended for water/fire/fog): add "seamless looping
pixel animation, subtle ambient motion only (drifting fog / shimmering water /
flickering embers), retro game loop". Export as a small **.gif** or **.mp4** —
either auto-wins over the .jpg. Keep loops short and under ~4 MB.

---

## 4. COMMON role prompts (make these 7 first — theme-neutral on purpose)

These are abstract/conceptual so they read well under any case's colour tint.
Keep them tonal, not literally green/blue/amber.

**`context.jpg` — the wider picture / landscape / evolution**
> A vast dark topographic landscape from above at dusk, faint contour lines and
> a distant hazy horizon, a single thread of warm light tracing a river or road
> through deep shadow, sense of scale and time. [+ universal suffix]

**`action.jpg` — the problem / case for action / tension**
> Raw unprocessed material resting in shadow — rough stone, unmilled grain, coiled
> rope — a single hard shaft of light cutting across it, heavy stillness, a moment
> of held tension before work begins. [+ universal suffix]

**`solution.jpg` — the answer / strategy / building the ecosystem**
> Pre-dawn light breaking over the frame of something being built — scaffolding,
> a structure taking shape, converging lines and momentum, dark foreground lifting
> toward a brightening edge, quiet optimism. [+ universal suffix]

**`key-factors.jpg` — pillars / drivers / what worked / the model**
> Extreme close-up of precision craft in low light — the teeth of a machine, hands
> at a lathe, ordered rows of components — sharp focused detail dissolving into
> darkness, a study in things done exactly right. [+ universal suffix]

**`policy.jpg` — government support / schemes / institutions**
> The dark geometry of civic architecture — a colonnade or a grand stair in
> shadow, strong parallel lines, one soft pool of light, weighty and institutional
> without any signage. [+ universal suffix]

**`challenges.jpg` — risks / barriers / bottlenecks**
> A narrow path through obstruction in gloom — mist between dark rock, a bottleneck
> of tangled forms, weather closing in, friction and resistance rendered as
> texture, no clear way through yet. [+ universal suffix]

**`takeaways.jpg` — lessons / roadmap / the way forward**
> An empty road or jetty leading out of deep shadow toward a low warm sunrise,
> clean receding perspective, calm and resolved, the frame opening up ahead. [+ universal suffix]

*(Optional `.mp4` versions: same scene, "slow subtle drift, seamless 8-second loop".)*

---

## 5. PER-CASE cover prompts (`media/<slug>/0.jpg`)

Literal, place-specific, but still dark/cinematic so the title reads over them.

**east-godavari-coconut-coir/0.jpg**
> A dense Andhra coconut grove before sunrise, silhouetted palms against a dim
> pearl sky, stacks of coir husk in deep shadow foreground, mist low over red soil. [+ suffix]

**nellore-shrimp-processing/0.jpg**
> Coastal Andhra aquaculture ponds at blue-hour, still dark water in a grid to the
> horizon, faint aerator ripples catching the last light, silhouetted embankments. [+ suffix]

**nellore-ethanol-potential/0.jpg**
> A dark industrial distillery skyline at dusk, storage tanks and pipework in
> silhouette, warm sodium glow low on the horizon, fields of feedstock fading into
> shadow foreground. [+ suffix]

**srikakulam-blue-economy/0.jpg**
> A quiet fishing harbour on the Andhra coast at first light, dark moored boats,
> wet nets, calm slate sea meeting a dim sky, working coastline in low key. [+ suffix]

**shenzhen-growth-model/0.jpg**
> A vast container port at night seen from distance, dark stacked containers and
> gantry cranes in silhouette, sparse cool lights, the scale of a port-led economy
> under a starless sky. [+ suffix]

**morbi-ceramic-cluster/0.jpg**
> The dark interior of a ceramic tile factory, the deep-orange glow of a kiln the
> only light source, rows of tiles receding into shadow, heat haze, industrial
> craft. [+ suffix]

**tiruppur-textiles/0.jpg**
> A dim knitwear mill, rows of circular knitting machines in low light, threads
> catching a single lamp, bolts of fabric stacked in shadow, the texture of a
> textile cluster. [+ suffix]

**kumarakom-tourism/0.jpg**
> Kerala backwaters before dawn, a dark houseboat silhouette on glassy still water,
> palms and mist, one warm lantern reflection, serene and low-key. [+ suffix]

**sahyadri-farms-fpc/0.jpg**
> Terraced grape and vegetable farms in the Sahyadri hills at dusk, dark rolling
> ridgelines, mist in the valleys, orderly rows fading into shadow, cooperative
> scale. [+ suffix]

**chetna-organics-fpo/0.jpg**
> Close, low-light study of hands cupping raw organic cotton bolls, deep shadow
> around, one soft window light, dignity of the smallholder farmer, no face. [+ suffix]

**biofloc-tilapia/0.jpg**
> Rows of dark circular biofloc tanks under a dim shed roof, still water surfaces
> catching faint light, quiet aquaculture technology at rest, low key. [+ suffix]

**paddy-fish-farming/0.jpg**
> A flooded paddy field at blue-hour reflecting a dim sky, dark bunds forming a
> grid, the faint ripple of fish beneath rice, integrated farming, serene. [+ suffix]

**banana-processing/0.jpg**
> A dark banana plantation with heavy leaves in shadow, stacked green bunches in a
> shaded shed, a single shaft of light, agro-processing about to begin. [+ suffix]

---

## 6. Fastest path

1. Generate the **7 common role images** (§4) → drop in `media/common/`. Every
   slide of every case now has a real background.
2. Generate **13 covers** (§5) → drop each at `media/<slug>/0.jpg`.
3. That's it. Add per-section overrides later only where a specific shot beats the
   shared one. Videos are optional — a `.mp4` with the same name auto-wins over `.jpg`.
