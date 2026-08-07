/* ===========================================================================
   Swarna Andhra — district template D3: Industrial corridor (industry >= 30%
   of GDVA).

   Archetype thesis: manufacturing, mining, construction and utilities dominate,
   and the CONCENTRATION is the point. 2 of 28 districts are D3 —
   Anakapalle (industry 52.6% of its own GDVA) and YSR Kadapa (32.5%).

   Order:
     stat row (GDDP · industry share of the district · this district's share of
     the STATE industrial economy · per-capita income with its rank named)
     -> compositionBars of the industrial sub-sectors
     -> the industry aggregate's four-year path
     -> sectorDonut with industry emphasised
     -> rankStrip: this district's footprint in each state-level sector
     -> constituency drill list.

   THE PERCENTAGE TRAP — read before editing.
   Every aggregate/sector point carries TWO different percentages:
     pct_of_district     = the sector's share of THIS district's GDVA
     pct_of_state_sector = this district's share of the STATE total for that sector
   Anakapalle industry is 52.64% of Anakapalle and 7.59% of Andhra Pradesh's
   industry. In this file the two are kept in physically separate helpers
   (districtShareItems / stateFootprintPeers) and every caption naming one of
   them is written next to the helper that supplies it. Never cross them.

   Reads ONLY the enriched district node defined in enrich.js
   (DASH.DISTRICT_KEYS). Every key on that list is always present; every value
   may be null / [] / ''. Renders on the bare path (dist payload absent) too.

   Synchronous, no fetch, no build step, no colour literals, no custom CSS:
   every visual comes from the shared library, so the .vstage dark-stage
   overrides in components.css apply unchanged.
   =========================================================================== */
(function (global) {
  'use strict';

  var D = global.DASH;
  if (!D) return;                       // components.js must load first
  global.DASH_TPL = global.DASH_TPL || {};

  function n(v) { return D.num(v); }

  /* The four sector rows the workbook publishes inside "Industry". Matched by
     name because the workbook carries no sector codes. Order is the order the
     industrial story is normally told in. */
  var INDUSTRIAL = [
    { label: 'Manufacturing', re: /^manufactur/i },
    { label: 'Mining & Quarrying', re: /mining/i },
    { label: 'Construction', re: /^construction/i },
    { label: 'Electricity, Gas, Water Supply', re: /electricity/i }
  ];

  function sectorsOf(node) {
    return Array.isArray(node.sectors) ? node.sectors : [];
  }

  /* Industrial sub-sectors, matched against node.sectors. Returns the raw rows
     so each caller can choose WHICH percentage it wants — and say so. */
  function industrialRows(node) {
    var src = sectorsOf(node);
    var out = [];
    INDUSTRIAL.forEach(function (d) {
      for (var i = 0; i < src.length; i++) {
        var s = src[i];
        if (s && s.name && d.re.test(s.name)) { out.push({ def: d, row: s }); return; }
      }
    });
    return out;
  }

  /* ---- percentage A: share of THIS district's GDVA ---------------------- */
  function districtShareItems(node) {
    return industrialRows(node).map(function (p) {
      return { name: p.def.label, pct: n(p.row.pct_of_district) };
    }).filter(function (it) { return it.pct !== null; });
  }

  /* ---- percentage B: this district's share of the STATE total ----------- */
  function stateFootprintPeers(node) {
    return industrialRows(node).map(function (p) {
      return { name: p.def.label, value: n(p.row.pct_of_state_sector) };
    }).filter(function (it) { return it.value !== null; });
  }

  function aggSeries(node, key) {
    var a = node.aggregates;
    if (!a || !Array.isArray(a[key])) return [];
    return a[key].filter(function (p) { return p && p.year; });
  }

  function lastWith(arr, field) {
    for (var i = arr.length - 1; i >= 0; i--) {
      if (arr[i] && n(arr[i][field]) !== null) return arr[i];
    }
    return null;
  }

  /* "2025-26 (FAE)" -> "2025-26 First Advance Estimate". Vintages are never
     collapsed: a four-year series spans four different estimate classes. */
  var VINTAGE = {
    TRE: 'Third Revised Estimate',
    SRE: 'Second Revised Estimate',
    FRE: 'Further Revised Estimate',
    FAE: 'First Advance Estimate'
  };
  function vintageOf(year) {
    var m = String(year || '').match(/\(([A-Z]+)\)/);
    return m && VINTAGE[m[1]] ? VINTAGE[m[1]] : '';
  }
  function yearOnly(year) {
    return String(year || '').replace(/\s*\(.*\)$/, '');
  }
  function yearPhrase(year) {
    var v = vintageOf(year);
    return v ? yearOnly(year) + ' ' + v : yearOnly(year);
  }

  function ordinal(i) {
    var s = ['th', 'st', 'nd', 'rd'], v = i % 100;
    return i + (s[(v - 20) % 10] || s[v] || s[0]);
  }

  function signedPct(v) {
    var x = n(v);
    if (x === null) return null;
    return (x > 0 ? '+' : '') + D.fmtPct(x);
  }

  /* --------------------------------------------------------------------- D3 */

  global.DASH_TPL.D3 = function (node) {
    node = node || {};

    var latest = node.latest_year || '';
    var latestPhrase = yearPhrase(latest) || latest;

    var ind = aggSeries(node, 'industry');
    var indLatest = lastWith(ind, 'pct_of_district');
    var indState = lastWith(ind, 'pct_of_state_sector');

    var out = '<div class="d-tpl d-tpl-d3">';

    /* ---- 1. stat row ---------------------------------------------------- */

    var cards = [];

    /* GDDP, with the year-on-year change against the PREVIOUS point's own
       vintage — the two figures are not the same estimate class. */
    var gs = Array.isArray(node.gddp_series) ? node.gddp_series : [];
    var prev = gs.length >= 2 ? gs[gs.length - 2] : null;
    var gDelta = null;
    if (n(node.gddp_growth) !== null && prev && prev.year) {
      gDelta = signedPct(node.gddp_growth) + ' over ' + yearOnly(prev.year) +
        (prev.estimate ? ' (' + prev.estimate + ')' : '');
    } else if (n(node.gddp_growth) !== null) {
      gDelta = signedPct(node.gddp_growth) + ' year on year';
    }
    cards.push(D.statCard({
      label: 'District GDDP',
      value: D.fmtCr(node.gddp) || null,
      sub: latestPhrase,
      delta: gDelta
    }));

    /* PERCENTAGE A — share of this district's own GDVA. */
    var indShare = indLatest ? n(indLatest.pct_of_district)
      : (node.shares ? n(node.shares.industry) : null);
    cards.push(D.statCard({
      label: 'Industry share of this district',
      value: D.fmtPct(indShare) || null,
      sub: 'of ' + (node.name || 'the district') + '’s own GDVA, ' +
        (indLatest ? yearPhrase(indLatest.year) : latestPhrase)
    }));

    /* PERCENTAGE B — a completely different number: this district's slice of
       the state's industrial economy. Labelled so it cannot be read as A. */
    cards.push(D.statCard({
      label: 'Share of AP’s industry',
      value: indState ? (D.fmtPct(indState.pct_of_state_sector) || null) : null,
      sub: indState
        ? 'this district’s share of Andhra Pradesh’s total industrial GDVA, ' +
          yearPhrase(indState.year)
        : ''
    }));

    /* Rank always names its peer set — never a bare "rank 12". */
    var pciSub = latestPhrase;
    var rk = n(node.pci_rank), cnt = n(node.district_count);
    if (rk !== null && cnt !== null) {
      pciSub += ' · ' + ordinal(rk) + ' of ' + cnt +
        ' districts by per-capita income';
    }
    cards.push(D.statCard({
      label: 'Per-capita income',
      value: D.fmtRs(node.pci) || null,
      sub: pciSub,
      delta: signedPct(node.pci_growth)
    }));

    out += D.section({
      titleHtml: D.placeCrumb(node.name || 'District', 'industrial corridor district'),
      /* node.why already reads "industry 52.6% — industrial corridor", so the
         archetype name is not repeated in front of it. */
      note: node.why ? String(node.why) : 'Industrial corridor',
      aside: D.rankBadge({ rank: rk, total: cnt || 28, basis: 'per-capita income' }),
      /* When the per-capita income figure itself is not attached the card is
         dropped rather than stubbed — but the rank, which IS carried on the
         summary record, is still worth stating, with its peer set named. */
      body: D.statRow(cards) +
        D.sparkRow(node.gddp_series, node.pci_series) +
        ((n(node.pci) === null && rk !== null && cnt !== null)
          ? D.sourceNote('The per-capita income figure is not attached for this ' +
            'district. Its rank is carried on the summary record: ' + ordinal(rk) +
            ' of ' + cnt + ' districts by per-capita income.')
          : '')
    });

    /* ---- 2. inside industry — the concentration is the headline --------- */

    var subItems = districtShareItems(node);      /* PERCENTAGE A only */
    var subBody;
    if (subItems.length) {
      /* scale:'share' (the default) — the track is 100%, so bar width IS the
         published share of the district's GDVA. Not a ranking. */
      subBody = D.compositionBars({ items: subItems });

      var rows = industrialRows(node);
      var valBits = rows.map(function (p) {
        var v = D.fmtCr(p.row.value);
        return v ? p.def.label + ' ' + v : null;
      }).filter(Boolean);
      if (valBits.length) {
        subBody += D.sourceNote('Gross value added, ' + latestPhrase + ': ' +
          valBits.join(' · ') + '.');
      }

      var grBits = rows.map(function (p) {
        var g = signedPct(p.row.growth);
        return g ? p.def.label + ' ' + g : null;
      }).filter(Boolean);
      if (grBits.length && prev && prev.year) {
        subBody += D.sourceNote('Change over ' + yearOnly(prev.year) +
          (prev.estimate ? ' (' + prev.estimate + ')' : '') + ': ' +
          grBits.join(' · ') + '.');
      }

      /* Only assert that the parts make up the aggregate when they actually
         do, to the published precision. */
      if (indShare !== null) {
        var sum = subItems.reduce(function (a, it) { return a + it.pct; }, 0);
        if (Math.abs(sum - indShare) <= 0.2 && subItems.length === INDUSTRIAL.length) {
          subBody += D.sourceNote('These four rows are the whole of the industry ' +
            'aggregate: they sum to ' + D.fmtPct(sum, 2) + ' of the district’s GDVA.');
        }
      }
    } else {
      subBody = D.empty('The industrial sub-sector split (manufacturing, mining ' +
        'and quarrying, construction, electricity, gas and water supply) is not ' +
        'attached for this district, so the composition of its industry cannot ' +
        'be shown.');
    }

    out += D.section({
      title: 'Inside industry',
      note: 'Each sub-sector as a share of this district’s own GDVA, ' + latestPhrase,
      body: subBody
    });

    /* ---- 3. the industry aggregate's four-year path ---------------------- */

    var pathItems = ind.map(function (p) {
      return { name: yearOnly(p.year) + (vintageOf(p.year) ? ' · ' + String(p.year).match(/\(([A-Z]+)\)/)[1] : ''),
               pct: n(p.pct_of_district) };
    }).filter(function (it) { return it.pct !== null; });

    var pathBody;
    if (pathItems.length >= 2) {
      /* Same percentage as section 2 — share of the district's own GDVA — one
         row per year. scale:'share', so each bar's width is that year's share. */
      pathBody = D.compositionBars({ items: pathItems });

      var lvlBits = ind.map(function (p) {
        var v = D.fmtCr(p.value);
        return v ? yearOnly(p.year) + ' ' + v : null;
      }).filter(Boolean);
      if (lvlBits.length) {
        pathBody += D.sourceNote('Industry gross value added: ' +
          lvlBits.join(' · ') + '.');
      }

      var vintBits = ind.map(function (p) {
        var v = vintageOf(p.year);
        return v ? yearOnly(p.year) + ' ' + v : null;
      }).filter(Boolean);
      if (vintBits.length) {
        pathBody += D.sourceNote('These four years are not equally firm. ' +
          vintBits.join('; ') + '. Only the last is an advance estimate and it ' +
          'will be revised.');
      }

      /* PERCENTAGE B again, kept in prose and named in full so it can never be
         mistaken for the bars above it. */
      var fpBits = ind.map(function (p) {
        var v = D.fmtPct(p.pct_of_state_sector);
        return v ? yearOnly(p.year) + ' ' + v : null;
      }).filter(Boolean);
      if (fpBits.length) {
        pathBody += D.sourceNote('A different measure, for contrast: this ' +
          'district’s share of Andhra Pradesh’s total industrial GDVA was ' +
          fpBits.join(' · ') + '. That is not the same figure as the bars ' +
          'above, which are industry’s share of this district.');
      }
    } else {
      pathBody = D.empty('The four-year industry series is not attached for this ' +
        'district, so its path cannot be charted.');
    }

    out += D.section({
      title: 'Industry’s four-year path',
      note: 'Share of this district’s own GDVA, by year — estimate vintages differ',
      body: pathBody
    });

    /* ---- 4. the whole economy, industry emphasised ----------------------- */

    var shares = node.shares && typeof node.shares === 'object' ? {
      agri: n(node.shares.agri),
      industry: n(node.shares.industry),
      services: n(node.shares.services)
    } : null;

    var donutBody;
    if (shares && (shares.agri !== null || shares.industry !== null || shares.services !== null)) {
      donutBody = D.sectorDonut({
        shares: shares,
        emphasis: 'industry',
        title: (node.name || 'District') + ' sector shares',
        centerLabel: 'of district GDVA'
      });
    } else {
      donutBody = D.empty('Sector aggregate shares are not published for this district.');
    }

    out += D.section({
      title: 'The whole economy',
      note: 'Share of this district’s own GDVA, ' +
        (indLatest ? yearPhrase(indLatest.year) : latestPhrase),
      body: donutBody
    });

    /* ---- 5. footprint in the state — PERCENTAGE B, as a ranking ---------- */

    var fpPeers = stateFootprintPeers(node);
    var fpBody;
    if (fpPeers.length >= 2) {
      /* rankStrip bars are scaled to the largest item, so this strip is a
         RANKING of where this district weighs most within the state — the
         caption says exactly that, and every value is printed. */
      fpBody = D.rankStrip({
        label: 'Ranked by where this district weighs most in the state — ' +
          'bar length is position in this ranking, the number is the share',
        peers: fpPeers,
        unit: '% of the AP total'
      });
      fpBody += D.sourceNote('Each figure is ' + (node.name || 'this district') +
        '’s share of Andhra Pradesh’s total gross value added in that ' +
        'sector, ' + latestPhrase + '. It is not the sector’s share of this ' +
        'district — that is the "Inside industry" figure above.');
      if (rk !== null && cnt !== null) {
        fpBody += D.sourceNote('On per-capita income this district ranks ' +
          ordinal(rk) + ' of ' + cnt + ' districts. Per-district GDDP and ' +
          'per-capita income figures for the other districts are not carried on ' +
          'this record, so a district-against-district bar chart is not drawn.');
      }
    } else {
      fpBody = D.empty('This district’s share of the state total for each ' +
        'industrial sector is not attached for this district.');
    }

    out += D.section({
      title: 'Footprint in the state',
      note: 'Share of Andhra Pradesh’s total, per sector, ' + latestPhrase,
      body: fpBody
    });

    /* ---- 6. constituency drill list -------------------------------------- */

    var cons = Array.isArray(node.constituencies) ? node.constituencies : [];
    out += D.section({
      title: 'Constituencies',
      note: cons.length ? cons.length + ' in this district' : '',
      body: D.drillList({
        items: cons.map(function (c) { return String(c).replace(/_/g, ' '); }),
        label: 'Assembly constituencies in this district',
        onpick: 'DASH_PICK_CONSTITUENCY',
        emptyReason: 'No constituency list is carried for this district.'
      })
    });

    /* ---- provenance ------------------------------------------------------ */

    var srcBits = [];
    srcBits.push('Source: ' + (node.source || 'AP district-wise GVA/GDDP workbook') + '.');
    if (n(node.population) !== null) {
      srcBits.push('Population ' + D.grp(Math.round(n(node.population))) +
        ' persons for ' + yearOnly(latest) + ', as carried in the same workbook.');
    }
    if (!node.enriched) {
      srcBits.push('Only the summary record was available for this district; the ' +
        'four-year series and the sector detail are not attached, and the sections ' +
        'that need them say so rather than estimating.');
    }
    out += D.sourceNote(srcBits.join(' '));

    return out + '</div>';
  };
})(typeof window !== 'undefined' ? window : this);
