# Methodology slide background videos

Drop a per-slide background video here and add its name to `manifest.json`.
Only the slide on screen (and the one next to it) ever decodes, so twelve
videos in this folder still means at most two playing at once.

## The twelve slide names (data-bg on each <section class="md-slide">)

| # | name        | slide |
|---|-------------|-------|
| 1 | title       | How a district's income is estimated |
| 2 | why         | Measurement exists to be used |
| 3 | gva         | Value added is what is left after inputs |
| 4 | routes      | Three routes to the same total |
| 5 | levels      | One economy, four levels |
| 6 | split       | Sixteen sub-sectors |
| 7 | approach    | Top-down, bottom-up, mixed |
| 8 | chain       | From value added to rupees per person |
| 9 | vintage     | The five estimate stages |
| 10| district    | District estimates are harder |
| 11| mandal      | Mandal figures |
| 12| takeaways   | Five things to carry back |

## To light a slide up

1. Save the video as `<name>.mp4` here, e.g. `gva.mp4`.
   - Muted, looping, H.264 MP4. Keep it small: 1280x720 or less, a few MB.
   - Landscape, since it is covered (object-fit:cover) behind a glass panel.
2. Add the name to `manifest.json`:
   { "have": ["gva", "vintage"] }
3. Reload. No cache stamp needed — the manifest is fetched no-store.

A name in `have` with no matching .mp4 falls back to the dark stage silently.
