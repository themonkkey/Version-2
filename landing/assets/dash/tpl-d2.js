/* ===========================================================================
   Swarna Andhra — D2 Agrarian heartland district template.

   11 of 28 districts are D2 — Eluru, Bapatla, Krishna, West Godavari,
   Konaseema, Ananthapuramu, Nandyal, Sri Satya Sai, Prakasam, Chittoor and
   East Godavari. It is the largest district group, so it must read as the
   main case and not as a fallback layout: land, crops, livestock and
   aquaculture are the economy here, and the template leads with them.

   Composition:
     identity + stat row (GDDP, agriculture share of THIS district, per-capita
     income with its rank and peer set named, population)
     -> composition bars of node.sectors, agriculture-facing rows drawn first
        as their own group, the rest of the economy second, both captioned as
        share of THIS district's GDVA
     -> the agriculture & allied aggregate across four years: a value
        trajectory, then the two DIFFERENT percentages side by side, each
        captioned with which one it is
     -> sector donut, agriculture emphasised
     -> drill list of constituencies
     -> source note.

   DATA CONTRACT
   The only input is the ENRICHED DISTRICT NODE defined in the header comment
   of enrich.js. Every key read here is on DASH.DISTRICT_KEYS. Nothing is
   fetched; the function is synchronous. node.enriched === false means only
   the bare index record was available, and every block below has a defined
   bare-path rendering.

   THE TWO PERCENTAGES — the one way to get this template badly wrong
   Each aggregate point carries BOTH:
     pct_of_district     = the sector's share of THIS district's GDVA
     pct_of_state_sector = this district's share of the STATE total for that
                           sector
   These are not the same number and can differ several-fold. Every place
   either is rendered in this file states in words which one it is, in the
   caption immediately attached to the geometry.

   VINTAGES
   The four-year series spans TRE / SRE / FRE / FAE estimates. Only 2025-26 is
   the First Advance Estimate. Every year is labelled with its own code and the
   series carries a note saying they are not one vintage.

   HONESTY
   No figure is invented. Missing input becomes an explicit empty state naming
   what is missing — never a zero, never a placeholder, never an em dash
   standing in for a value. Ranks always name the peer set.

   COLOURS
   This file defines no colour literals and no colour custom properties of its
   own. The only colour it emits is `currentColor`, which resolves to the page
   text colour on the light page and to white inside a .vstage dark stage, so
   the trajectory bars are legible in both without a hand-rolled override.
   =========================================================================== */
(function (global) {
  'use strict';

  var D = global.DASH;
  global.DASH_TPL = global.DASH_TPL || {};

  var SECTOR_LABEL = {
    agri: 'Agriculture & allied',
    industry: 'Industry',
    services: 'Services'
  };

  /* The agriculture-facing rows inside node.sectors. Matched by name because
     the workbook gives no sector code. Anything not matched here is simply
     drawn in the second group — nothing is dropped or reclassified silently. */
  var AGRI_ROW = [
    /^agricultur/i,
    /^horticultur/i,
    /^live\s*stock/i,
    /^forestry/i,
    /^fishing/i
  ];

  function n(v) { return D.num(v); }
  function txt(s) { return String(s === null || s === undefined ? '' : s).trim(); }

  function isAgriRow(name) {
    for (var i = 0; i < AGRI_ROW.length; i++) {
      if (AGRI_ROW[i].test(name)) return true;
    }
    return false;
  }

  /* 1 -> "1st". Used only for ranks that exist in the data. */
  function ordinal(v) {
    var i = n(v);
    if (i === null) return '';
    i = Math.round(i);
    var mod100 = i % 100, mod10 = i % 10;
    var suf = (mod100 >= 11 && mod100 <= 13) ? 'th'
      : mod10 === 1 ? 'st' : mod10 === 2 ? 'nd' : mod10 === 3 ? 'rd' : 'th';
    return i + suf;
  }

  function peerCount(node) {
    var c = n(node.district_count);
    if (c !== null && c > 0) return c;
    if (Array.isArray(node.peers) && node.peers.length) return node.peers.length;
    return null;
  }

  /* "5th of 28 districts by per-capita income" — never a bare rank. */
  function rankPhrase(node, rank, measure) {
    var o = ordinal(rank);
    if (!o) return '';
    var c = peerCount(node);
    return c === null ? o + ' by ' + measure : o + ' of ' + c + ' districts by ' + measure;
  }

  function signed(pct) {
    var v = n(pct);
    if (v === null) return '';
    return (v >= 0 ? '+' : '') + D.fmtPct(v);
  }

  /* The label of the point before the last one that carries a value, so a
     growth figure can name the year it is measured against instead of being an
     unattributed percentage. */
  function priorLabel(series) {
    if (!Array.isArray(series)) return '';
    var seen = [];
    for (var i = 0; i < series.length; i++) {
      if (series[i] && n(series[i].value) !== null) seen.push(series[i]);
    }
    if (seen.length < 2) return '';
    return txt(seen[seen.length - 2].year) || txt(seen[seen.length - 2].label);
  }

  function growthDelta(value, series) {
    var g = signed(value);
    if (!g) return null;
    var prev = priorLabel(series);
    return prev ? g + ' over ' + prev : g;
  }

  function latest(node) { return txt(node.latest_year) || ''; }

  /* ------------------------------------------------------------ stat cards */

  function stats(node) {
    var yr = latest(node);
    var sh = node.shares || {};
    var cards = [];

    if (n(node.gddp) !== null) {
      var gsub = [];
      if (yr) gsub.push(yr);
      var gr = rankPhrase(node, node.gddp_rank, 'district GDDP');
      if (gr) gsub.push(gr);
      cards.push(D.statCard({
        label: 'District GDDP',
        value: D.fmtCr(node.gddp),
        sub: gsub.join(' · ') || null,
        delta: growthDelta(node.gddp_growth, node.gddp_series)
      }));
    }

    if (n(sh.agri) !== null) {
      cards.push(D.statCard({
        label: SECTOR_LABEL.agri,
        value: D.fmtPct(sh.agri),
        /* pct_of_district. Named as such so it can never be read as this
           district's share of the state's agriculture. */
        sub: 'share of this district\'s own GDVA' + (yr ? ', ' + yr : '')
      }));
    }

    if (n(node.pci) !== null) {
      cards.push(D.statCard({
        label: 'Per-capita income',
        value: D.fmtRs(node.pci),
        sub: yr || null,
        delta: growthDelta(node.pci_growth, node.pci_series)
      }));
    }

    var rp = rankPhrase(node, node.pci_rank, 'per-capita income');
    if (rp) {
      cards.push(D.statCard({
        label: 'Income rank',
        value: ordinal(node.pci_rank),
        sub: rp
      }));
    }

    if (n(node.population) !== null) {
      cards.push(D.statCard({
        label: 'Population',
        value: D.grp(Math.round(n(node.population))),
        sub: 'persons, AP district workbook'
      }));
    }

    if (!cards.length) {
      return D.empty(
        'No headline figures — GDDP, per-capita income, sector shares or ' +
        'population — are available for this district.'
      );
    }
    return D.statRow(cards);
  }

  /* ------------------------------------------------------ composition bars

     scale is left at the library default ('share'): the track is 100%, so bar
     width IS the published percentage of this district's GDVA and the caption
     is exactly what the geometry encodes. Never pass scale:'relative' under a
     share caption — that makes width mean rank instead.

     pct_of_district only. pct_of_state_sector is a different measure and is
     never fed to these bars; it appears once, further down, under its own
     caption. */
  function sectorBars(rows) {
    return D.compositionBars({
      items: rows.map(function (s) {
        return { name: s.name, pct: s.pct_of_district };
      })
    });
  }

  function composition(node) {
    var yr = latest(node);
    var sectors = (Array.isArray(node.sectors) ? node.sectors : []).filter(function (s) {
      return s && txt(s.name) && n(s.pct_of_district) !== null;
    });

    if (!sectors.length) {
      return D.empty(
        'Sector-wise figures for this district are not in this record. They ' +
        'come from the district workbook payload, which was not attached.'
      );
    }

    var agri = sectors.filter(function (s) { return isAgriRow(s.name); });
    var rest = sectors.filter(function (s) { return !isAgriRow(s.name); });

    var out = '';

    if (agri.length) {
      out += '<p class="d-drill-lbl">Land, livestock and water — ' + agri.length +
        ' sector' + (agri.length === 1 ? '' : 's') + '</p>';
      out += sectorBars(agri);
      out += D.sourceNote(
        'Each bar is that sector\'s share of THIS district\'s GDVA' +
        (yr ? ' in ' + yr : '') + ', drawn against a 100% track. It is not the ' +
        'district\'s share of the state\'s output in that sector.'
      );
    }

    if (rest.length) {
      out += '<p class="d-drill-lbl">The rest of the economy — ' + rest.length +
        ' sector' + (rest.length === 1 ? '' : 's') + '</p>';
      out += sectorBars(rest);
      out += D.sourceNote(
        'Same measure and same 100% track as the group above: share of this ' +
        'district\'s own GDVA' + (yr ? ', ' + yr : '') + '. Totals, taxes and ' +
        'subsidies are excluded from the sector list, so these shares do not ' +
        'add to 100%.'
      );
    }

    return out;
  }

  /* --------------------------------------------- four-year agriculture path

     Three things, kept deliberately apart because two of them are percentages
     that mean different things:

       1. the value of agriculture & allied output, year by year, in Rs crore
       2. pct_of_district      — share of this district's own GDVA
       3. pct_of_state_sector  — this district's share of AP's agriculture

     (2) and (3) are drawn as two separate bar groups with two separate
     captions, never on one axis and never under one heading. */

  function trajectoryBars(points) {
    var usable = points.filter(function (p) { return n(p.value) !== null && n(p.value) > 0; });
    if (usable.length < 2) {
      return D.empty(
        'A four-year path needs at least two years with a published value; ' +
        'this record has ' + usable.length + '.'
      );
    }
    var max = usable.reduce(function (a, p) { return Math.max(a, n(p.value)); }, 0);
    if (max <= 0) return D.empty('The published agriculture values for this district are zero.');

    var lastPoint = usable[usable.length - 1];

    var cols = points.map(function (p) {
      var v = n(p.value);
      var yr = txt(p.year) || txt(p.label);
      var head, bar;
      if (v === null || v <= 0) {
        head = '<span style="opacity:.62">not published</span>';
        bar = '';
      } else {
        head = D.esc(D.fmtCr(v));
        bar = '<div role="img" aria-label="' + D.esc(yr + ': ' + D.fmtCr(v)) + '"' +
          ' style="width:100%;height:' + (v / max * 100).toFixed(2) + '%;' +
          'background:currentColor;opacity:' + (p === lastPoint ? '.55' : '.28') + ';' +
          'border-radius:6px 6px 0 0"></div>';
      }
      return '<div style="flex:1 1 0;min-width:0;text-align:center">' +
        '<div style="font-size:.78rem;font-weight:700;margin-bottom:6px">' + head + '</div>' +
        '<div style="height:92px;display:flex;align-items:flex-end">' + bar + '</div>' +
        '<div style="font-size:.7rem;opacity:.62;margin-top:6px;word-break:break-word">' +
          D.esc(yr) + '</div>' +
      '</div>';
    }).join('');

    return '<div style="display:flex;gap:10px;align-items:flex-end">' + cols + '</div>';
  }

  function pctBars(points, field) {
    var items = [];
    points.forEach(function (p) {
      var v = n(p[field]);
      if (v === null) return;
      items.push({ name: txt(p.year) || txt(p.label), pct: v });
    });
    if (!items.length) {
      return D.empty('This percentage is not published for any year in this record.');
    }
    return D.compositionBars({ items: items });
  }

  function agriPath(node) {
    var agg = node.aggregates && node.aggregates.agri;
    var points = (Array.isArray(agg) ? agg : []).filter(function (p) { return p && txt(p.year); });

    if (!points.length) {
      return D.empty(
        'The four-year agriculture & allied series is not in this record. It ' +
        'comes from the district workbook payload, which was not attached.'
      );
    }

    var out = '';

    out += '<p class="d-drill-lbl">Agriculture &amp; allied output, Rs crore</p>';
    out += trajectoryBars(points);
    out += D.sourceNote(
      'Bar heights are relative to the tallest year shown; they are not a ' +
      'share of anything. Each year is a different estimate vintage: TRE, SRE ' +
      'and FRE are revised estimates of earlier years, and only 2025-26 (FAE) ' +
      'is the First Advance Estimate. The figures are printed above each bar.'
    );

    out += '<div style="display:grid;gap:16px;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));margin-top:18px">';

    out += '<div>' +
      '<p class="d-drill-lbl">Share of THIS district\'s GDVA</p>' +
      pctBars(points, 'pct_of_district') +
      D.sourceNote(
        'How much of this district\'s own economy agriculture & allied is, ' +
        'year by year. Bars run against a 100% track, so width is the ' +
        'percentage itself.'
      ) +
    '</div>';

    out += '<div>' +
      '<p class="d-drill-lbl">Share of ANDHRA PRADESH\'s agriculture</p>' +
      pctBars(points, 'pct_of_state_sector') +
      D.sourceNote(
        'A different measure from the one beside it: how much of the state\'s ' +
        'whole agriculture & allied output this one district produces. Bars ' +
        'again run against a 100% track, where 100% would be the entire state ' +
        'sector.'
      ) +
    '</div>';

    return out + '</div>';
  }

  /* ------------------------------------------------------------------ donut */

  function donut(node) {
    var sh = node.shares;
    if (!sh || (n(sh.agri) === null && n(sh.industry) === null && n(sh.services) === null)) {
      return D.empty('The three sector aggregates are not published for this district.');
    }
    return D.sectorDonut({
      shares: sh,
      emphasis: 'agri',
      title: txt(node.name) + ' sector shares',
      centerLabel: 'of district GDVA'
    });
  }

  /* ------------------------------------------------------------------ main */

  global.DASH_TPL.D2 = function (node) {
    if (!node || typeof node !== 'object') {
      return D.empty('No district record was supplied.');
    }

    var name = txt(node.name) || txt(node.key).replace(/_/g, ' ');
    var yr = latest(node);
    var out = '<div class="dash dash-d2">';

    out += D.section({
      titleHtml: D.placeCrumb(name || 'District', 'agrarian heartland district'),
      note: yr ? 'District figures, ' + yr : null,
      aside: D.rankBadge({ rank: node.pci_rank, total: n(node.district_count) || 28,
        basis: 'per-capita income' }),
      body: stats(node) +
        D.sparkRow(node.gddp_series, node.pci_series) +
        (txt(node.why) ? D.sourceNote('Classified agrarian heartland: ' + txt(node.why) + '.') : '') +
        (node.enriched === false
          ? D.sourceNote(
              'Only the district index record was available for this render, so ' +
              'the four-year series and the sector-wise detail below are not shown.'
            )
          : '')
    });

    out += D.section({
      title: 'What this district produces',
      note: yr ? 'Share of this district\'s GDVA, ' + yr : 'Share of this district\'s GDVA',
      body: composition(node)
    });

    out += D.section({
      title: 'The agriculture base over four years',
      note: 'Estimates of four different vintages — see the note under the bars',
      body: agriPath(node)
    });

    out += D.section({
      title: 'Agriculture, industry and services',
      note: yr ? 'Share of this district\'s GDVA, ' + yr : 'Share of this district\'s GDVA',
      body: donut(node)
    });

    out += D.section({
      title: 'Constituencies',
      note: Array.isArray(node.constituencies) && node.constituencies.length
        ? node.constituencies.length + ' in this district'
        : null,
      body: D.drillList({
        /* Names are passed through exactly as the index holds them, because
           the pick handler is expected to look the record up by that key —
           the same convention the mandal drill list already follows. */
        items: (Array.isArray(node.constituencies) ? node.constituencies : [])
          .map(txt).filter(Boolean),
        label: 'Assembly constituencies in this district',
        onpick: 'DASH_PICK_CONSTITUENCY',
        emptyReason: 'No constituencies are listed for this district.'
      })
    });

    out += D.sourceNote(txt(node.source) || D.SOURCE_DIST);
    return out + '</div>';
  };
})(typeof window !== 'undefined' ? window : this);
