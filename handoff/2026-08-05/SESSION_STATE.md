# Swarna Andhra GVA Assistant — landing page + UI session state

**Last updated: 2026-08-05.** Written so another Claude (or person) can pick this up cold.
Assumes no memory of any prior session. Read top to bottom before touching anything.
Prior handoff: `handoff/2026-07-30/SESSION_STATE.md` (chatbot/RAG backend state — still valid,
this session did not touch retrieval/answering logic).

Repo: `~/swarna-andhra-chatbot` · Remote: `github.com/themonkkey/swarna-andhra-chatbot`
(**public**) · Owner: Aryan Singh, Pahlé India Foundation (PIF).

---

## 0. What happened this session

Two workstreams, both UI/design only:

1. **`app.py` (Streamlit chatbot UI)** — glassmorphism/neumorphism redesign, sidebar
   decluttered, Claude-style landing hero.
2. **`landing/index.html`** (main focus) — full rebuild from brutalist monospace to a
   dark-glass, video-backed, editorial design. This is the marketing/landing site, separate
   from the chatbot app itself.

Both are **deployed and pushed**:
- Landing site live at https://landing-lac-psi-72.vercel.app (Vercel project rooted at
  `landing/` subdirectory)
- GitHub: commit `7af1afc` pushed to `themonkkey/swarna-andhra-chatbot`

---

## 1. `app.py` — what changed

- Glassmorphism/neumorphism CSS in `BRAND_CSS` (~lines 417-620): translucent `rgba()` +
  `backdrop-filter: blur(28px) saturate(180%)`; neumorphism via paired `--neu-out`/`--neu-in`
  box-shadow tokens.
- Green mesh background: `.stApp::before` with 4–5 radial-gradient blobs (needed for glass to
  read visually — glass on plain white is invisible).
- Sidebar rebuilt: "How to Use" → 3 numbered steps (`.sb-step`); "What's Inside" → compact
  `.sb-rows` key/value table. Killed the old 9-line prose block.
- Hero: when `not st.session_state.messages` → `.sa-hero` (centered, Pahlé badge, h1,
  subtitle, Claude-style). Once chatting starts → `.sa-topbar` (compact inline).
- Card heading color: `.vstage .fcard h4,.vstage .acard h4{color:var(--lime);font-weight:700;}`
- Model: pinned to `gemini-3.5-flash-lite` as default.
- Added 503 retry with exponential backoff (4 attempts, `2**attempt` sec) in `call_llm()`
  Gemini branch.
- Mobile sidebar bleed-through fix scoped tightly to
  `section[data-testid="stSidebar"][aria-expanded="true"]` (don't widen this selector, it was
  leaking into desktop before the scope was added).

Not done: no functional/retrieval changes. This was purely visual.

---

## 2. `landing/index.html` — the big rebuild

### Design system
- Fonts: **Bodoni Moda** (h1/h2/h3 — Didone/Vogue lineage, chosen explicitly to avoid
  "fancy AI-generated font" look) + **Public Sans** (h4/body). Loaded via Google Fonts link
  tag in `<head>`.
- Palette: INK `#0B2E20`-ish dark green, LIME `#C6FF6A` accent, white. Same family as the
  chatbot's `var(--lime)`.
- Nav: `background:rgba(11,46,32,.62);backdrop-filter:blur(28px) saturate(170%);` lemon-green
  accent per user request.
- Footer: `background:var(--ink);border-top:1px solid rgba(255,255,255,.10);`

### Video ambient background system (core mechanism)
Every major section has `data-vid="<loop-name>"`. JS `mount()` injects:
```html
<div class="amb"><video ... /><div class="amb-fallback"></div><div class="amb-scrim" style="..."></div></div>
```
- **Lazy load**: IntersectionObserver, `rootMargin:'300px'`, except `.hero` which is eager
  (loads immediately, no IO wait).
- **LOOP_SCRIM** table maps each loop name → `[top, mid, bottom]` scrim opacity — every video
  has different brightness so each needed independently tuned scrim values. Don't reuse one
  scrim across videos without checking contrast.
- **Section → video assignments** (current, do not reshuffle without reason):
  hero=aerial, ink-section=ink, About=handloom, Methodology-open=ledger,
  Methodology-base=**gridwork** (see fix below), Methodology-close=glass,
  Districts=**glass** (user: "background video here should be glass one!"). CTA video
  (vector) is unused — CTA section was dropped.
- 8 compressed `.mp4` files live in `landing/assets/video/`: aerial, ink, ledger, handloom,
  longexposure, glass, vector, isometric, gridwork.

### Fixed bugs (don't reintroduce)
- **`.amb-fallback` covering video**: fallback div is a later DOM sibling and was painting
  over the playing video. Fix: `.amb video.ready ~ .amb-fallback{opacity:0;}`.
- **IntersectionObserver never fires in a backgrounded/hidden tab** — this breaks both video
  lazy-load testing AND the scroll-narrative step tracking if you rely on IO for either.
  Scroll narrative was rewritten off IO entirely: pure `rAF` + `window.scrollY` sync
  (`window.__syncNarr` exposed as a test hook). When testing lazy video loads via the browser
  tool, `tabs_select` to front the tab first or IO silently no-ops.
- **Methodology video 13.5x scale distortion**: `.narr` (the Methodology scroll container) is
  ~12,110px tall. `.amb{position:absolute;inset:0}` stretched a 720p video to fill that whole
  height → looked like a static blur, not a video. Fix: **`.narr > .amb{position:fixed;}`** —
  pins the ambient video to the viewport instead of the scroll container. This is a load-bearing
  rule; if the Methodology video looks stretched/blurry again, check this selector first.
- **Map label position**: was `top:50%;transform:translate(-50%,-50%)` — user flagged Andhra
  Pradesh label rendering dead-center over the map. Fixed to
  `top:clamp(18px,3vw,28px);left:50%;transform:translateX(-50%)` (pinned near top instead).
  `.map-box.picked .map-label{opacity:0}` fades the label once a district is selected.
- **isometric.mp4 in Methodology was wrong tonally** — user: "it doesn't match... too
  literal/toy-like." Replaced with `gridwork.mp4`, generated by the user from Veo matching the
  `gridwork` master prompt (macro ledger-paper texture). Cropped Veo watermark
  (1120×1280px region) before compressing to 644KB.
- **Districts/map layout symmetry**: `align-items:stretch` on `.map-layout` grid,
  `.map-box{display:flex;flex-direction:column;justify-content:center}` so map and text panel
  match height exactly (user explicitly asked for "symmetry and parallelism").

### Scroll narrative (Methodology section)
- No animation library. One `rAF`-throttled scroll handler computes which `.chap` step is
  nearest viewport-center, writes `data-step="N"` on the container, toggles `.on` class,
  updates rail dots.
- All SVG animation is **pure CSS**, scoped like `[data-step="N"] #sc1 .dist{opacity:1;...}`.
  No per-frame JS touches the SVGs.

### Assets generated this session
- `landing/og-image.jpg` — 1200×630, Python PIL: green mesh gradient, AP state seal badge,
  eyebrow pill, Georgia Bold h1 (white+lime), Public Sans subtitle.
- `landing/favicon.ico` + `landing/icons/` (16/32/48/180/192/512px) — extracted from the AP
  state seal embedded inside `swarna-logo-crop.svg`.
- `landing/assets/swarna-logo-crop.svg` optimized: 3 embedded raster PNGs downscaled from
  huge source resolutions (e.g. 3629×4096) to max 480px with Pillow. **5.1MB → 540KB.** If
  this file balloons again, check for re-embedded full-res source images.

---

## 3. Figma MCP illustration work — IN PROGRESS, this is the next task

Figma file: `WH4TFZto8rBqY0IqJJ6cqn` ("Swarna Andhra — Methodology Scenes"), 4 frames:
- **sc1** state-districts (district grid with lime "pick" highlight)
- **sc2** eleven-industries (bar chart)
- **sc3** three-approaches (state→district flow tree) — **user explicitly flagged this one**
  as needing completion/enhancement
- **sc4** formula-chain (4 stacked term boxes)

Palette used in Figma: INK `rgb(14,74,60)`, LIME `rgb(198,255,106)`, W `rgb(255,255,255)`.

Pipeline: Figma → export SVG per frame → `landing/assets/scenes/sc{1,2,3,4}.svg` →
`scripts/build_scenes.py` converts Figma layer-name `id`s into CSS classes the stylesheet
drives via `[data-step="N"]` → writes `landing/assets/scenes/scenes.inc.html` (pasted inline
into `index.html`).

**`build_scenes.py` was just updated** (present on disk, already read this session) with new
label class-map entries so scenes can carry on-canvas text annotations that animate in sync
with their parent element instead of sitting static:
```python
(re.compile(r"^lbl-pick$"),           "dist pick"),
(re.compile(r"^(val|lbl)-(t\d)$"),    "term {1}"),
(re.compile(r"^lbl-(?:state|primary|secondary|tertiary|topstate|districts)$"), None),
```
The last pattern (→ `None`) means those specific label ids get **stripped entirely** — they're
either redundant with visible text elsewhere or not yet designed for.

**What's actually left to do (the user's literal ask):**
"complete and enhance these illustrations using Figma MCP, match them to the current page's
visual system" — i.e. go into Figma via the `mcp__56b63082...` Figma MCP tools (or whichever
Figma MCP is connected next session — tool prefix may differ), open file
`WH4TFZto8rBqY0IqJJ6cqn`, and:
1. Review current state of sc1–sc4 frames (`get_screenshot` / `get_design_context` on the
   file/frames).
2. Add/complete whatever's missing in sc3 specifically (flagged by user) — likely missing
   labels or a cleaner flow-tree layout, given the new `lbl-*` class map entries were added
   in anticipation of this.
3. Re-export all 4 SVGs to `landing/assets/scenes/sc{1,2,3,4}.svg`.
4. Run `python3 scripts/build_scenes.py` to regenerate `scenes.inc.html`.
5. Paste/diff the new `scenes.inc.html` content into `index.html`'s inline SVG blocks.
6. Visually verify in the browser preview against `[data-step]` CSS — scroll through the
   Methodology section and confirm animations still trigger correctly (labels didn't exist in
   the CSS animation timeline before, so scroll-triggered opacity/highlight rules may need new
   selectors added to match the new `dist pick` / `term t{n}` label classes).

This is genuinely not started yet — no Figma MCP calls were made this session before it ended.

---

## 4. Known loose ends / do NOT forget

- **GitHub auth is fragile.** `gh` CLI is authenticated as `aryaninternships-netizen`, which
  has **no push access** to `themonkkey/swarna-andhra-chatbot`. Last push used a one-off PAT
  pasted directly in chat by the user (`ghp_FJTf24...`), applied via
  `git -c credential.helper=` (not cached to disk). **User said they would revoke that token
  the same day (2026-08-05)** — assume it is dead. Before any future push, ask the user for a
  fresh token or get proper `gh auth login` set up under the right account.
- **Chatbot CTA links are stubbed.** Landing page buttons link to
  `andhrachatbot.streamlit.app`, which currently redirects to a Streamlit login wall (not
  actually deployed/public). User said leave as-is until the chatbot itself is deployed
  somewhere real — don't "fix" this link without checking whether a real deployment exists
  yet.
- **Vercel MCP tool is unauthenticated in this environment** — noted as unavailable this
  session (`plugin:vercel:vercel` requires OAuth, non-interactive sessions can't do it). If
  Vercel deploys are needed, either use the Vercel CLI/dashboard directly or get the user to
  authorize the connector interactively first.
- Vercel project for the landing page was created rooted at `landing/` (not repo root) —
  `.vercelignore` in that folder excludes `*.bak.*` and `.DS_Store`. Don't recreate a second
  Vercel project pointed at repo root; it'll conflict.

---

## 5. Quick orientation for a cold-start Claude

1. Read this file top to bottom (done, you're here).
2. If continuing the Figma work: load Figma MCP tools via ToolSearch, open
   `WH4TFZto8rBqY0IqJJ6cqn`, start with sc3.
3. If touching `landing/index.html`, note it's 68KB — read specific sections, don't reread
   whole file per edit.
4. Don't touch RAG/retrieval/embedding code without reading
   `handoff/2026-07-30/SESSION_STATE.md` first — that's a separate concern with its own open
   bugs and benchmark findings, unrelated to this session's UI work.
