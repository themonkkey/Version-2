# Deck content schema (scripts/deck_content/<slug>.json)

The single source the deck renderer consumes. Authored from the case-study txt
files; content is VERBATIM from the source (typos and all), only STRUCTURE is
added. Chrome (running footers, slide numbers, speaker notes, "THANK YOU"
slides) is excluded. Source/citation lines go in `source` fields, never in
body blocks.

```json
{
  "slug": "east-godavari-coconut-coir",
  "title": "...", "eyebrow": "...", "subtitle": "...",
  "audience": "...",                      // optional cover audience line
  "source_note": "...",                   // optional deck-level attribution
  "hero_stats": [{"value": "#2", "label": "Global producer"}],
  "sections": [
    {
      "kicker": "THE CASE FOR ACTION",    // caps eyebrow, optional
      "title": "The Problem We Are Trying to Solve",
      "lead": "one-sentence standfirst",  // optional
      "source": "Source: TNAU ...",       // optional per-section footnote line
      "blocks": [ <typed blocks> ]
    }
  ]
}
```

## Block types

| type | shape | renders as |
|---|---|---|
| `p` | `{text}` | paragraph |
| `callout` | `{label?, text}` | emphasis box ("Officer takeaway", "Message for AP") |
| `quote` | `{text, attribution?}` | pull quote |
| `stats` | `{items:[{value,label,qualifier?}], footnote?}` | stat tiles; label is the COMPLETE statement incl. any wrapped lines |
| `cards` | `{items:[{n?,title,body}]}` | heading+body cards (problems, pillars, lessons); `n` keeps asserted ordinals |
| `list` | `{title?, items:[text]}` | titled bullet list; items are full statements |
| `chips` | `{items:[text]}` | short standalone phrases ONLY (product baskets, keywords) |
| `pairs` | `{items:[{term,desc}]}` | definition rows (term + gloss) |
| `steps` | `{items:[{n,title,body}]}` | numbered sequence / roadmap |
| `flow` | `{stages:[{name,desc}], closing?}` | linear chain with arrow connectors; `›` tokens never rendered as content |
| `phases` | `{groups:[{label,name?,period?,tasks:[text]}]}` | phased plan; label like "PHASE 1" or "Days 0-15" |
| `timeline` | `{items:[{period,title?,desc}]}` | era/date rows |
| `table` | `{cols:[...], rows:[[...]], footnote?}` | real table; cells verbatim, row integrity sacred |
| `compare` | `{cols:[{title,items:[text]}]}` | two/three-column lists (For Farmers vs For Consumers) |
| `groups` | `{groups:[{name,items:[text] or [{term,desc}]}]}` | grouped checklists (KPI groups, measure themes) |
| `series` | `{title?, unit?, points:[{label,value}]}` | bar chart |
| `swot` | `{s:[],w:[],o:[],t:[]}` | quadrants |
| `hierarchy` | `{tiers:[{level?,name,desc}], closing?}` | org tiers |
| `fanout` | `{input, branches:[{component, products:[text]}]}` | one input to many outputs |

## Fidelity rules (the whole point)
1. Text verbatim from the txt source, unescaped (`\~` -> `~`). Em/en dashes
   KEPT in the JSON; the renderer resolves em dashes per site policy.
2. Every wrapped multi-line label is REJOINED into one complete statement.
   No box may contain a fragment that cannot stand alone.
3. Numbers never separate from what they measure; table rows never re-pair.
4. Titles/kickers/subheads never appear inside blocks; arrows never content.
5. Nothing invented, nothing dropped except chrome. If a line fits no type,
   use `p` - never force it into stats/chips.
