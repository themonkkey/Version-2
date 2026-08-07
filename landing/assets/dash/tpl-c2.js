/* ===========================================================================
   Swarna Andhra — C2 Agrarian constituency template.

   83 of 175 constituencies are C2. This is the largest group, so it must read
   as the main case, not as a fallback: the land, the crop/aqua mix and the
   share of the economy agriculture carries are the story.

   Composition:
     stat-card row -> composition bars (share of GCDP) -> growth bullets
     (Agricultural & Allied first) -> geography / profile narrative ->
     thrust chips -> mandal drill list -> source note.

   DATA CONTRACT
   The only input is the ENRICHED NODE defined in enrich.js. Every key read
   here is on DASH.ENRICHED_KEYS. Nothing is fetched; the function is
   synchronous. node.enriched === false means only the bare index record was
   available, and every block below has a defined bare-path rendering.

   HONESTY
   No figure is invented. Missing input becomes an explicit empty state naming
   what is missing — never a zero, never a placeholder. Baseline is 2023-24 and
   MEASURED; target is 2028-29 and A PLAN. They are never summed and never
   share an unlabelled axis. Provenance is only ever asserted from the data
   (node.population_note), never assumed.

   COLOURS
   Sector colours come from node.share_colors (the portal's own colorHex) or
   from the growth rows' colorHex. When neither exists the component library's
   verified fallback is used. This file defines no colour literals.
   =========================================================================== */
(function (global) {
  'use strict';

  var DASH = global.DASH;
  global.DASH_TPL = global.DASH_TPL || {};

  var SECTOR_LABEL = {
    agri: 'Agriculture & allied',
    industry: 'Industry',
    services: 'Services'
  };
  var SECTOR_ORDER = ['agri', 'industry', 'services'];

  function n(v) { return DASH.num(v); }

  function txt(s) { return String(s === null || s === undefined ? '' : s).trim(); }

  /* Does a sanitised HTML string carry any visible text? */
  function hasProse(html) {
    return typeof html === 'string' && html.replace(/<[^>]*>/g, '').trim() !== '';
  }

  function baseYear(node) { return txt(node.year_baseline) || '2023-24'; }
  function tgtYear(node) { return txt(node.year_target) || '2028-29'; }

  /* ------------------------------------------------------------ stat cards */

  function stats(node) {
    var sh = node.shares || {};
    var by = baseYear(node);
    var cards = [];

    cards.push(DASH.statCard({
      label: 'GCDP baseline',
      value: DASH.fmtCr(node.gcdp_baseline) || null,
      sub: by + ' — measured',
      delta: n(node.cagr) !== null
        ? DASH.fmtPct(node.cagr) + ' CAGR planned to ' + tgtYear(node)
        : null
    }));

    cards.push(DASH.statCard({
      label: SECTOR_LABEL.agri,
      value: DASH.fmtPct(sh.agri) || null,
      sub: 'share of GCDP, ' + by
    }));

    cards.push(DASH.statCard({
      label: 'Area',
      value: n(node.area_sqkm) ? DASH.grp(node.area_sqkm) + ' sq km' : null,
      sub: 'constituency extent'
    }));

    /* Revenue villages exist only once the portal payload is attached. An
       omitted card is honest; an empty one would be noise on all 83 seats. On
       the bare path the slot carries population instead, when published. */
    if (n(node.revenue_villages) !== null) {
      cards.push(DASH.statCard({
        label: 'Revenue villages',
        value: DASH.grp(n(node.revenue_villages)),
        sub: 'AP Assembly Constituencies portal'
      }));
    } else if (n(node.population) !== null) {
      cards.push(DASH.statCard({
        label: 'Population',
        /* population_note is provenance exactly as the portal states it; 10 of
           175 records state none, and for those no source is claimed here. */
        value: DASH.grp(n(node.population)),
        sub: txt(node.population_note) || null
      }));
    }

    return DASH.statRow(cards);
  }

  /* -------------------------------------------------------- composition bars

     No crop-wise or aquaculture-wise percentages are published for any
     constituency, so what is drawn is the sector composition that IS
     published, agriculture first. The unquantified crop/aqua mix is carried by
     the thrust chips below, where it does not pretend to be a measurement.

     scale is left at the library default ('share'): the track is 100%, so bar
     width IS the published percentage and the caption is what the geometry
     encodes. Do not pass scale:'relative' here — that makes width mean rank. */
  function composition(node) {
    var sh = node.shares || {};
    var colors = node.share_colors || {};
    var items = [];

    SECTOR_ORDER.forEach(function (k) {
      var v = n(sh[k]);
      if (v === null) return;
      items.push({
        name: SECTOR_LABEL[k],
        pct: v,
        colorHex: typeof colors[k] === 'string' ? colors[k] : ''
      });
    });

    if (!items.length) {
      return DASH.empty('Sector shares of GCDP are not published for this constituency.');
    }
    return DASH.compositionBars({ items: items });
  }

  /* ------------------------------------------------------------ growth rows

     node.growth is PER-SECTOR ONLY — enrich.js strips the portal's whole-economy
     TOTAL row and surfaces it as gcdp_baseline / gcdp_target / cagr, so the
     total can never land on the same axis as its own components. It is [] on
     the bare path, and the bare path deliberately does NOT draw a one-bar
     "baseline to target" chart: the whole-economy pair is stated as two
     explicitly labelled cards instead. */

  var AGRI_RE = /^(agri|primary)/i;

  function rank(name) {
    return AGRI_RE.test(name) ? 0 : 5;
  }

  function growthSection(node) {
    var by = baseYear(node);
    var ty = tgtYear(node);
    var rows = Array.isArray(node.growth) ? node.growth.slice() : [];

    rows = rows.filter(function (r) {
      return r && txt(r.name) && (n(r.baseline) !== null || n(r.target) !== null);
    });

    if (rows.length) {
      rows.sort(function (a, b) { return rank(a.name) - rank(b.name); });
      return DASH.section({
        title: 'Sector baselines and targets',
        note: by + ' measured → ' + ty + ' planned',
        body: DASH.growthBullet({
          rows: rows.map(function (r) {
            return {
              name: r.name,
              baseline: r.baseline,
              target: r.target,
              cagr: r.cagr,
              colorHex: r.colorHex
            };
          }),
          emphasis: 'Agri',
          baselineYear: by,
          targetYear: ty
        }) + DASH.sourceNote(
          'Sector rows only. The whole-economy GCDP total is reported above and ' +
          'is kept off this axis: the published sector figures do not add up to it.'
        )
      });
    }

    var base = n(node.gcdp_baseline);
    var tgt = n(node.gcdp_target);
    if (base === null && tgt === null) {
      return DASH.section({
        title: 'Baselines and targets',
        body: DASH.empty('No baseline or target figures are published for this constituency.')
      });
    }

    return DASH.section({
      title: 'Whole economy: baseline and target',
      note: 'Sector-wise baselines and targets are not published in this record',
      body: DASH.statRow([
        DASH.statCard({
          label: 'GCDP baseline',
          value: DASH.fmtCr(base) || null,
          sub: by + ' — measured'
        }),
        DASH.statCard({
          label: 'GCDP target',
          value: DASH.fmtCr(tgt) || null,
          sub: ty + ' — a plan, not an outturn'
        })
      ]) + DASH.sourceNote(
        'The two figures are of different kinds and are not comparable as an ' +
        'outturn: the baseline is measured, the target is the Vision 2029 plan. ' +
        'They are not added together.'
      )
    });
  }

  /* -------------------------------------------------------------- narrative

     Geography first — on an agrarian seat the land is the lead — then the
     constituency profile. Both are portal prose, already sanitised by
     enrich.js and sanitised again by DASH.narrative. node.why is a one-line
     classification note, not prose, so it stays a caption on the header. */
  function landAndPlace(node) {
    var out = '';
    if (hasProse(node.geography_html)) out += DASH.narrative(node.geography_html);
    if (hasProse(node.profile_html)) out += DASH.narrative(node.profile_html);
    if (!out) {
      return DASH.empty(
        'Land-use and geography prose has not been published for this ' +
        'constituency on the AP Assembly Constituencies portal.'
      );
    }
    return out;
  }

  /* ------------------------------------------------------------------ main */

  global.DASH_TPL.C2 = function (node) {
    if (!node || typeof node !== 'object') {
      return DASH.empty('No constituency record was supplied.');
    }

    var by = baseYear(node);
    var name = txt(node.name);
    var district = txt(node.district);
    var out = '<div class="dash dash-c2">';

    out += DASH.section({
      title: name ? name + ' — agrarian constituency' : 'Agrarian constituency',
      note: district ? district + ' district · ' + by + ' baseline' : by + ' baseline',
      body: stats(node) +
        (txt(node.why) ? DASH.sourceNote('Classified agrarian: ' + txt(node.why) + '.') : '')
    });

    out += DASH.section({
      title: 'What the economy is made of',
      note: 'Share of GCDP, ' + by + ' — bars are drawn against a 100% track',
      body: composition(node)
    });

    out += growthSection(node);

    out += DASH.section({
      title: 'Land and geography',
      body: landAndPlace(node)
    });

    out += DASH.section({
      title: 'Thrust sectors',
      note: 'Named in the Vision 2029 plan; no share is published for each',
      body: DASH.thrustChips(node.thrust)
    });

    out += DASH.section({
      title: 'Mandals',
      note: Array.isArray(node.mandals) && node.mandals.length
        ? node.mandals.length + ' in this constituency'
        : null,
      body: DASH.drillList({
        items: Array.isArray(node.mandals) ? node.mandals : [],
        label: 'Mandals in this constituency',
        onpick: 'DASH_PICK_MANDAL',
        emptyReason: 'No mandals are listed for this constituency.'
      })
    });

    out += DASH.sourceNote(txt(node.source) || DASH.SOURCE_APC);
    return out + '</div>';
  };
})(typeof window !== 'undefined' ? window : this);
