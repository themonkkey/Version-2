/* ===========================================================================
   Swarna Andhra — constituency template C4: Mixed / Transitional
   40 of 175 constituencies. No sector leads, so nothing is promoted: the
   comparison itself is the content and all three sectors read at equal weight.

   window.DASH_TPL.C4(node) -> HTML string.

   INPUT: the ENRICHED NODE and nothing else. Its contract is the header of
   landing/assets/dash/enrich.js and the allowed key list is DASH.ENRICHED_KEYS.
   Every key is always present; every value may be null / [] / ''. This
   template reads no globals, fetches nothing, and never assumes a value.

   Honesty: no figure is invented. Anything the record does not carry is
   dropped with an explicit reason via DASH.empty(). Baseline (2023-24,
   measured) and target (2028-29, a plan) are labelled as such everywhere and
   are never summed. Provenance is echoed only when node.population_note
   carries it — 10 of 175 records state none, and for those nothing is claimed.
   =========================================================================== */
(function (global) {
  'use strict';

  var DASH = global.DASH;
  if (!DASH) return;                       // library must load first
  global.DASH_TPL = global.DASH_TPL || {};

  var SECTORS = [
    { key: 'agri',     label: 'Agriculture & allied' },
    { key: 'industry', label: 'Industry' },
    { key: 'services', label: 'Services' }
  ];

  /* Mandal drill-down hook. The enriched node carries no callback (correctly —
     it is data, not wiring), so the page defines this global if it wants the
     list interactive. drillList degrades to a plain list when it is absent. */
  var PICK_MANDAL = 'DASH_PICK_MANDAL';

  /* --- small readers, each tolerant of null ------------------------------ */

  function n(v) { return DASH.num(v); }

  function str(v) { return typeof v === 'string' ? v : ''; }

  function arr(v) { return Array.isArray(v) ? v : []; }

  /* The three published shares, in fixed sector order, with the portal's own
     colour when the record carries one. No colour is ever invented here: when
     share_colors is null the bars fall back to the library's stylesheet. */
  function compositionItems(node) {
    var shares = node.shares && typeof node.shares === 'object' ? node.shares : null;
    if (!shares) return [];
    var colors = node.share_colors && typeof node.share_colors === 'object'
      ? node.share_colors : null;
    var out = [];
    SECTORS.forEach(function (s) {
      var pct = n(shares[s.key]);
      if (pct === null) return;
      out.push({
        name: s.label,
        pct: pct,
        colorHex: colors && typeof colors[s.key] === 'string' ? colors[s.key] : ''
      });
    });
    return out;
  }

  /* Per-sector rows only. enrich.js has already stripped the whole-economy
     TOTAL row, so nothing here can put a total on the same axis as its parts. */
  function growthRows(node) {
    var out = [];
    arr(node.growth).forEach(function (r) {
      if (!r || !r.name) return;
      if (n(r.baseline) === null && n(r.target) === null) return;
      out.push({
        name: String(r.name),
        baseline: n(r.baseline),
        target: n(r.target),
        cagr: n(r.cagr),
        colorHex: typeof r.colorHex === 'string' ? r.colorHex : ''
      });
    });
    return out;
  }

  /* node.peers is [{name, gcdp_baseline}], siblings in the same district and
     this constituency included. rankStrip wants {name, value}. */
  function peerRows(node) {
    var out = [];
    arr(node.peers).forEach(function (p) {
      if (!p || !p.name) return;
      var v = n(p.gcdp_baseline);
      if (v === null) return;
      out.push({ name: String(p.name), value: v });
    });
    return out;
  }

  function grid(body) {
    return '<div class="d-c4-grid" style="display:grid;gap:16px;' +
      'grid-template-columns:repeat(auto-fit,minmax(260px,1fr));align-items:start">' +
      body + '</div>';
  }

  function hasProse(html) {
    return !!String(html || '').replace(/<[^>]*>/g, '').trim();
  }

  /* ---------------------------------------------------------------- render */

  global.DASH_TPL.C4 = function (node) {
    node = node || {};

    var name = str(node.name);
    var district = str(node.district);
    var yb = str(node.year_baseline) || '2023-24';
    var yt = str(node.year_target) || '2028-29';

    var base = n(node.gcdp_baseline);
    var tgt = n(node.gcdp_target);
    var cagr = n(node.cagr);
    var pop = n(node.population);
    var popNote = str(node.population_note);

    var out = '';

    /* ---- 1. headline figures ------------------------------------------- */
    var c4Dist = district ? district.replace(/_/g, ' ') : '';
    var c4Rank = DASH.peerRank(node.peers, name, 'gcdp_baseline');
    out += DASH.section({
      titleHtml: DASH.placeCrumb(name || 'Constituency', 'mixed / transitional constituency',
        c4Dist ? [{ kind: 'district', name: c4Dist, joiner: 'of' }] : []),
      note: 'GCDP ' + yb + ' measured · ' + yt + ' planned',
      aside: c4Rank ? DASH.rankBadge({ rank: c4Rank.rank, total: c4Rank.total,
        basis: 'GCDP in ' + c4Dist }) : '',
      body: DASH.statRow([
        DASH.statCard({
          label: 'GCDP baseline',
          value: base !== null ? DASH.fmtCr(base) : null,
          sub: yb + ' — measured'
        }),
        DASH.statCard({
          label: 'GCDP target',
          value: tgt !== null ? DASH.fmtCr(tgt) : null,
          sub: yt + ' — a plan, not an outturn'
        }),
        DASH.statCard({
          label: 'Planned CAGR',
          value: cagr !== null ? DASH.fmtPct(cagr) + ' a year' : null,
          sub: 'Implied by the ' + yb + ' to ' + yt + ' plan'
        }),
        DASH.statCard({
          label: 'Population',
          value: pop !== null ? DASH.grp(pop) : null,
          /* Provenance is echoed verbatim, never asserted. Ten records carry
             none; for those the sub is omitted entirely rather than filled
             with an assumed "Census 2011". */
          sub: popNote || null
        })
      ])
    });

    /* ---- 2. three sectors, one encoding, equal weight -------------------- */
    /* Deliberately a single chart. An earlier draft drew the same three shares
       twice, as a donut and as bars, in two different colour encodings side by
       side. These are bars on a fixed 100% track (the library default), so the
       width of each bar IS its published percentage — which is exactly what
       the caption claims, and lets three near-equal sectors be read as such.
       No sector is emphasised: that is the whole point of the archetype. */
    var items = compositionItems(node);
    out += DASH.section({
      title: 'Three sectors, no leader',
      note: (str(node.why) ? node.why + ' · ' : '') +
        'share of GCDP, ' + yb + ' · bars are drawn against a 100% track',
      body: items.length
        ? DASH.compositionBars({ items: items })
        : DASH.empty('Sector shares of GCDP are not published for this constituency.')
    });

    /* ---- 3. growth, all rows, none emphasised --------------------------- */
    var rows = growthRows(node);
    var growthBody;
    if (rows.length) {
      growthBody = DASH.growthBullet({
        rows: rows,                       // source order, no emphasis
        baselineYear: yb,
        targetYear: yt
      });
    } else if (base !== null || tgt !== null) {
      /* Bare path: the per-sector rupee split is not on this record. Chart the
         all-sector figure alone and say so. It is not mixed with the shares
         above — those are percentages, and the two are never combined. */
      growthBody = DASH.growthBullet({
        rows: [{ name: 'GCDP, all sectors', baseline: base, target: tgt, cagr: cagr }],
        baselineYear: yb,
        targetYear: yt
      }) + DASH.sourceNote(
        'Per-sector rupee baselines and targets are not carried on this record, ' +
        'so only the all-sector figure is charted. The sector split above is a ' +
        'share of GCDP, not a rupee amount.');
    } else {
      growthBody = DASH.empty(
        'No baseline or target rupee figures are published for this constituency.');
    }

    out += DASH.section({
      title: 'Baseline to target',
      note: yb + ' measured → ' + yt + ' planned · the two are shown separately, never summed',
      body: growthBody
    });

    /* ---- 4. against its district siblings -------------------------------- */
    var peers = peerRows(node);
    out += DASH.section({
      title: 'Against its district',
      note: 'Baselines only — targets are plans and are not ranked',
      body: peers.length >= 2
        ? DASH.rankStrip({
            label: 'GCDP baseline ' + yb + (district
              ? ' — constituencies of ' + district + ' district'
              : ' — peer constituencies'),
            value: base,
            selfName: name || undefined,
            peers: peers,
            unit: 'cr'
          })
        : DASH.empty(district
            ? 'Fewer than two constituencies of ' + district + ' district carry a ' +
              'published baseline, so no ranking is drawn.'
            : 'This record does not name a parent district, so no peer set can be built.')
    });

    /* ---- 5. thrust sectors ----------------------------------------------- */
    out += DASH.section({
      title: 'Thrust sectors',
      note: 'As listed by the AP Assembly Constituencies portal',
      body: DASH.thrustChips(arr(node.thrust))
    });

    /* ---- 6. portal prose, only when the record carries it ---------------- */
    var prose = '';
    if (hasProse(node.economy_html)) prose += DASH.narrative(node.economy_html);
    if (hasProse(node.profile_html)) prose += DASH.narrative(node.profile_html);
    if (hasProse(node.geography_html)) prose += DASH.narrative(node.geography_html);
    if (prose) {
      out += DASH.section({
        title: 'In the portal’s words',
        note: 'Published text, reproduced unedited',
        body: grid(prose)
      });
    }

    /* ---- 7. drill down to mandals ---------------------------------------- */
    var mandals = arr(node.mandals);
    out += DASH.section({
      title: 'Mandals',
      note: mandals.length
        ? mandals.length + ' mandals · no mandal-level figures are published'
        : null,
      body: DASH.drillList({
        items: mandals,
        label: 'Drill down',
        onpick: PICK_MANDAL,
        emptyReason: 'No mandals are listed for this constituency.'
      })
    });

    /* SOURCE_APC carries the same attribution as node.source plus the year and
       estimate-class framing, which the bare attribution line does not. */
    out += DASH.sourceNote(DASH.SOURCE_APC);

    return '<div class="d-tpl d-tpl-c4" data-archetype="C4">' + out + '</div>';
  };
})(typeof window !== 'undefined' ? window : this);
