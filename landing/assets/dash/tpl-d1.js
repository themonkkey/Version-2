/* ===========================================================================
   Swarna Andhra — D1 template: Metro / urban core district
   (services-led AND top-8 per-capita income; 6 of 28 districts:
    Visakhapatnam, NTR, Guntur, Tirupati, Kakinada, SPSR Nellore)

   INPUT: the ENRICHED DISTRICT NODE and nothing else. Its contract is the
   comment block above enrichDistrict() in landing/assets/dash/enrich.js; the
   allowed key list is DASH.DISTRICT_KEYS. Every key is always present, every
   value may be null / [] / ''. This function is synchronous and never fetches.

   Archetype thesis: these are the districts where the state's urban economy
   sits. The story is SCALE and RANK — how big the economy is, how it has moved
   across four years, and where it stands among the other 27 districts.

   TWO PERCENTAGES, NEVER CONFLATED. node.aggregates.<sector>[] carries both
   pct_of_district (the sector's share of THIS district's GVA) and
   pct_of_state_sector (this district's share of the STATE total for that
   sector). Guntur agriculture is 14.04% of Guntur and 2.01% of Andhra
   Pradesh's agriculture. In this file:
     - the donut, the composition bars and node.shares are pct_of_district
       ONLY, and every caption says "share of this district's GVA";
     - pct_of_state_sector appears ONLY in its own section, whose title,
       captions and each card's sub-label say "share of the STATE total".
   No geometry is ever fed one under a caption describing the other.

   VINTAGES. The 4-year series spans four different estimate classes
   (TRE/SRE/FRE/FAE). Only 2025-26 is the First Advance Estimate. Every point
   in the trajectory carries its own vintage tag, and the figures are available
   as text (stat cards + SVG title) rather than encoded in geometry alone.

   RANK. node.peers carries pci_rank for all 28 districts but its .pci and
   .gddp are null on every record as enrich.js currently builds it, so no
   magnitude comparison can honestly be drawn. This template therefore renders
   the ordering by rank — which IS in the data — and says plainly that the
   other districts' per-capita figures are not carried here. Peer set is always
   named ("of 28 districts"), never a bare "rank 7".
   =========================================================================== */
(function (global) {
  'use strict';

  var D = global.DASH;
  if (!D) return;

  global.DASH_TPL = global.DASH_TPL || {};

  /* Integration defines this; drillList no-ops until it does. */
  var PICK_CONSTITUENCY = 'DASH_PICK_CONSTITUENCY';

  function arr(v) {
    return Object.prototype.toString.call(v) === '[object Array]' ? v : [];
  }

  function n(v) { return D.num(v); }

  /* Ordinal for rank language: 1st of 28, 7th of 28. */
  function ord(i) {
    var s = ['th', 'st', 'nd', 'rd'], v = i % 100;
    return i + (s[(v - 20) % 10] || s[v] || s[0]);
  }

  var VINTAGE = {
    TRE: 'Third Revised Estimate',
    SRE: 'Second Revised Estimate',
    FRE: 'Further Revised Estimate',
    FAE: 'First Advance Estimate'
  };

  function vintage(code) {
    return VINTAGE[code] || '';
  }

  /* A point is usable only when it carries both a label and a value. */
  function usable(series) {
    return arr(series).filter(function (p) {
      return p && p.label && n(p.value) !== null;
    });
  }

  function signed(pct) {
    var v = n(pct);
    if (v === null) return null;
    return (v > 0 ? '+' : '') + D.fmtPct(v);
  }

  /* ---------------------------------------------------------- trajectory ---
     There is no line-chart component in the library, so this is composed here:
     a plain inline SVG for the shape, and the same figures repeated as stat
     cards underneath so nothing lives in geometry alone. Colour is
     currentColor throughout — .vstage sets color:#FFF and the light page sets
     var(--label), so the chart is legible on both without a single literal.
     The vertical axis runs from zero, so bar/point heights are proportional to
     the actual figures rather than to a truncated window.                     */
  function trajectorySvg(points, unitLabel, fmt) {
    if (points.length < 2) return '';

    var W = 320, H = 96, PAD_L = 6, PAD_R = 6, TOP = 10, BASE = 80;
    var max = points.reduce(function (a, p) { return Math.max(a, n(p.value)); }, 0);
    if (max <= 0) return '';

    var span = W - PAD_L - PAD_R;
    var xy = points.map(function (p, i) {
      return {
        x: PAD_L + (points.length === 1 ? span / 2 : (i / (points.length - 1)) * span),
        y: BASE - (n(p.value) / max) * (BASE - TOP),
        p: p
      };
    });

    var aria = points.map(function (p) {
      return p.label + (p.estimate ? ' ' + p.estimate : '') + ' ' + fmt(p.value);
    }).join('; ');
    aria = unitLabel + ' — ' + aria + '. Vertical axis runs from zero.';

    var poly = xy.map(function (q) {
      return Math.round(q.x * 10) / 10 + ',' + Math.round(q.y * 10) / 10;
    }).join(' ');

    var dots = '';
    xy.forEach(function (q) {
      var advance = q.p.estimate === 'FAE';
      dots += '<circle cx="' + Math.round(q.x * 10) / 10 + '" cy="' + Math.round(q.y * 10) / 10 + '"' +
        ' r="4" fill="' + (advance ? 'none' : 'currentColor') + '"' +
        ' stroke="currentColor" stroke-width="1.6"' +
        (advance ? ' stroke-dasharray="2.2 1.8"' : '') + '></circle>';
      dots += '<line x1="' + Math.round(q.x * 10) / 10 + '" y1="' + Math.round(q.y * 10) / 10 +
        '" x2="' + Math.round(q.x * 10) / 10 + '" y2="' + BASE + '"' +
        ' stroke="currentColor" stroke-width="1" stroke-opacity=".18"></line>';
    });

    return '<div class="d-d1-traj" style="width:100%;margin:2px 0 14px">' +
      '<svg viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="xMidYMid meet"' +
      ' style="display:block;width:100%;height:auto;max-width:100%" role="img"' +
      ' aria-label="' + D.esc(aria) + '">' +
      '<title>' + D.esc(aria) + '</title>' +
      '<line x1="' + PAD_L + '" y1="' + BASE + '" x2="' + (W - PAD_R) + '" y2="' + BASE + '"' +
      ' stroke="currentColor" stroke-opacity=".28" stroke-width="1"></line>' +
      '<polyline points="' + poly + '" fill="none" stroke="currentColor"' +
      ' stroke-width="2" stroke-linejoin="round" stroke-linecap="round"></polyline>' +
      dots +
      '</svg></div>';
  }

  /* Stat card per point — the figures as text, each tagged with its own
     estimate vintage so a four-year run is never read as one firm series. */
  function trajectoryCards(points, fmt) {
    return D.statRow(points.map(function (p) {
      var g = signed(p.growth);
      return D.statCard({
        label: p.label + (p.estimate ? ' · ' + p.estimate : ''),
        value: fmt(p.value),
        sub: vintage(p.estimate) || 'Estimate class not stated',
        delta: g ? g + ' on the year' : ''
      });
    }));
  }

  /* ------------------------------------------------------------------ D1 --- */
  global.DASH_TPL.D1 = function (node) {
    node = node || {};

    var name = node.name ? String(node.name) : '';
    var LATEST = node.latest_year ? String(node.latest_year) : '';
    var total = n(node.district_count) || 28;

    var shares = node.shares && typeof node.shares === 'object' ? node.shares : null;
    var gddp = n(node.gddp);
    var gddpGrowth = n(node.gddp_growth);
    var gddpRank = n(node.gddp_rank);
    var pci = n(node.pci);
    var pciGrowth = n(node.pci_growth);
    var pciRank = n(node.pci_rank);
    var pop = n(node.population);
    var svcShare = shares ? n(shares.services) : null;

    var out = '<div class="dash dash-d1" data-archetype="D1">';

    /* ---- 0. identity ---------------------------------------------------- */
    var sub = ['Metro / urban core district'];
    if (node.why) sub.push(String(node.why));
    if (arr(node.constituencies).length) {
      sub.push(arr(node.constituencies).length + ' assembly constituencies');
    }
    if (!node.enriched) {
      sub.push('Detailed district workbook figures are not loaded for this record');
    }
    out += D.section({
      title: name || 'District',
      note: LATEST ? 'Latest year ' + LATEST : '',
      body: '<p class="d-src">' + D.esc(sub.join(' · ')) + '</p>'
    });

    /* ---- 1. headline figures -------------------------------------------- */
    var cards = [
      D.statCard({
        label: 'District GDDP',
        value: gddp !== null ? D.fmtCr(gddp) : null,
        sub: LATEST ? 'Current prices, ' + LATEST : 'Latest published year',
        delta: gddpGrowth !== null ? signed(gddpGrowth) + ' on the previous year' : ''
      }),
      D.statCard({
        label: 'Per-capita income',
        value: pci !== null ? D.fmtRs(pci) : null,
        sub: pciRank !== null
          ? ord(pciRank) + ' of ' + total + ' districts by per-capita income'
          : (LATEST ? LATEST : 'Latest published year'),
        delta: pciGrowth !== null ? signed(pciGrowth) + ' on the previous year' : ''
      }),
      D.statCard({
        label: 'Population',
        value: pop !== null ? D.grp(Math.round(pop)) + ' persons' : null,
        /* No provenance is asserted: the district node carries none. */
        sub: 'As carried in the district workbook'
      }),
      D.statCard({
        label: 'Services share',
        value: svcShare !== null ? D.fmtPct(svcShare) : null,
        sub: 'Share of THIS district’s GVA' + (LATEST ? ', ' + LATEST : '')
      })
    ];
    /* MUI sparklines under the two figures that HAVE a series. The number says
       where the district is; the line says which way it is moving. Shared with
       d2/d3/d4 via D.sparkRow; mounted by mui-charts.js after this panel paints. */
    out += D.section({
      title: 'The district in four figures',
      note: 'Each figure carries its own year and estimate class',
      body: D.statRow(cards) + D.sparkRow(node.gddp_series, node.pci_series)
    });

    /* ---- 2. four-year trajectory ---------------------------------------- */
    var gPts = usable(node.gddp_series);
    var pPts = usable(node.pci_series);

    var vintagesSeen = {};
    gPts.concat(pPts).forEach(function (p) { if (p.estimate) vintagesSeen[p.estimate] = 1; });
    var vKey = Object.keys(vintagesSeen).map(function (k) {
      return k + ' = ' + (vintage(k) || 'estimate class not documented');
    }).join(' · ');

    var trajBody = '';
    if (gPts.length >= 2) {
      trajBody += trajectorySvg(gPts, 'District GDDP, ₹ crore', D.fmtCr) +
        trajectoryCards(gPts, D.fmtCr);
    } else if (gPts.length === 1) {
      trajBody += trajectoryCards(gPts, D.fmtCr) +
        '<p class="d-src">Only one year of GDDP is published on this record, so no ' +
        'trajectory is drawn.</p>';
    } else {
      trajBody += D.empty('No GDDP series is published for this district.');
    }

    if (vKey) {
      trajBody += '<p class="d-src">' + D.esc(
        'These four points are NOT the same vintage: ' + vKey +
        '. Only the 2025-26 figure is a First Advance Estimate. ' +
        'The chart runs from zero and a hollow, dashed point marks the advance estimate.'
      ) + '</p>';
    }

    out += D.section({
      title: 'Four years of district output',
      note: 'GDDP at current prices, ₹ crore — mixed estimate vintages',
      body: trajBody
    });

    /* ---- 3. per-capita income trajectory -------------------------------- */
    if (pPts.length) {
      var pciBody = (pPts.length >= 2
        ? trajectorySvg(pPts, 'Per-capita income, ₹', D.fmtRs)
        : '') + trajectoryCards(pPts, D.fmtRs);
      var rankPts = pPts.filter(function (p) { return n(p.rank) !== null; });
      if (rankPts.length) {
        pciBody += '<p class="d-src">' + D.esc(
          'Rank among the ' + total + ' districts by per-capita income, year by year: ' +
          rankPts.map(function (p) {
            return p.label + ' ' + ord(n(p.rank));
          }).join(', ') + '.'
        ) + '</p>';
      }
      out += D.section({
        title: 'Per-capita income over four years',
        note: '₹ per person — mixed estimate vintages',
        body: pciBody
      });
    }

    /* ---- 4. what the economy is made of — SHARE OF THIS DISTRICT -------- */
    var donutBody;
    if (shares && (n(shares.agri) !== null || n(shares.industry) !== null || n(shares.services) !== null)) {
      donutBody = D.sectorDonut({
        shares: shares,
        emphasis: 'services',
        title: (name || 'This district') + ' — sector shares of its own GVA',
        centerLabel: 'services'
      });
      if (svcShare !== null) {
        donutBody += '<p class="d-src">' + D.esc(
          'Services are ' + D.fmtPct(svcShare) + ' of ' + (name || 'this district') +
          '’s own gross value added' + (LATEST ? ' in ' + LATEST : '') +
          '. This is the share of the district’s economy, not its share of the state.'
        ) + '</p>';
      }
    } else {
      donutBody = D.empty('Sector shares are not published for this district.');
    }
    out += D.section({
      title: 'A services-led economy',
      note: 'Share of THIS district’s GVA' + (LATEST ? ', ' + LATEST : ''),
      body: donutBody
    });

    /* ---- 5. the top sectors — SHARE OF THIS DISTRICT -------------------- */
    var allSectors = arr(node.sectors).filter(function (s) {
      return s && s.name && n(s.pct_of_district) !== null;
    });
    /* Top 3 only. In most districts the top three sectors are half the economy or
       more, so three dots tell the "what does this place run on" story without a
       17-row wall. A dot plot rather than bars: the eye reads the gap between #1
       and #3 as a position, which is the point. */
    var sectors = allSectors.slice(0, 3);

    var compBody;
    if (sectors.length) {
      compBody = D.sectorDots(sectors.map(function (s) {
        return { name: s.name, pct: n(s.pct_of_district), rank: n(s.rank) };
      }), { total: total });
      compBody += '<p class="d-src">' + D.esc(
        'The three largest sectors by their share of ' + (name || 'this district') +
        '’s own GVA' + (LATEST ? ', ' + LATEST : '') +
        '. Rank is this district’s standing in that sector among the ' + total +
        ' districts. ' + allSectors.length + ' sectors are published in all; totals, ' +
        'taxes and subsidies are excluded so these do not double-count.'
      ) + '</p>';
    } else {
      compBody = D.empty('Sector-level figures are not published for this district.');
    }
    out += D.section({
      title: 'What this district runs on',
      note: 'Top three sectors by share of THIS district’s GVA — not of the state',
      body: compBody
    });

    /* ---- 5b. how the split has MOVED ------------------------------------
       The section above is one year's division. This is the same division across
       four, which is where the actual story is: a metro district shifting between
       industry and services shows up here and nowhere else. */
    var aggAll = node.aggregates && typeof node.aggregates === 'object' ? node.aggregates : null;
    if (aggAll) {
      out += D.section({
        title: 'How the split has moved',
        note: 'Share of district output, ' + (node.gddp_series && node.gddp_series.length
          ? node.gddp_series[0].label + ' to ' + node.gddp_series[node.gddp_series.length - 1].label
          : 'four years'),
        wide: true,
        body: D.compositionRibbon({
          series: aggAll,
          emptyReason: 'The year-on-year sector split is not published for this district.'
        })
      });
    }

    /* ---- 6. weight in the STATE — pct_of_state_sector, kept apart -------- */
    var agg = aggAll;
    if (agg) {
      var SEC = [
        { k: 'agri', label: 'Agriculture & allied' },
        { k: 'industry', label: 'Industry' },
        { k: 'services', label: 'Services' }
      ];
      var stateCards = SEC.map(function (s) {
        var series = arr(agg[s.k]);
        var latest = null;
        for (var i = series.length - 1; i >= 0; i--) {
          if (series[i] && n(series[i].pct_of_state_sector) !== null) { latest = series[i]; break; }
        }
        return D.statCard({
          label: s.label,
          value: latest ? D.fmtPct(n(latest.pct_of_state_sector), 2) : null,
          sub: 'Of Andhra Pradesh’s TOTAL ' + s.label.toLowerCase() + ' output' +
            (latest && latest.label ? ', ' + latest.label : '')
        });
      });
      var anyState = stateCards.some(function (c) { return c.indexOf('d-stat-v') !== -1; });
      out += D.section({
        title: 'What this district contributes to the state',
        note: 'This district’s share of the STATE total for each sector',
        body: anyState
          ? D.statRow(stateCards) +
            '<p class="d-src">' + D.esc(
              'A different measure from the shares above. These figures say how much of ' +
              'Andhra Pradesh’s output in each sector comes from ' +
              (name || 'this district') + '. The section above says how much of ' +
              (name || 'this district') + '’s own economy each sector is. ' +
              'The two are not interchangeable and can differ several-fold.'
            ) + '</p>'
          : D.empty('State-share figures are not published for this district.')
      });
    }

    /* ---- 7. rank among the 28 ------------------------------------------- */
    var peers = arr(node.peers).filter(function (p) { return p && p.name; });

    /* Prefer a real magnitude comparison if per-capita figures for peers are
       ever carried; they are null on every peer as enrich.js builds the node
       today, so this branch stays dormant rather than inventing values. */
    var pciPeers = peers.map(function (p) {
      return { name: String(p.name), value: n(p.pci) };
    }).filter(function (p) { return p.value !== null; });

    var rankBody;
    if (pciPeers.length >= 2 && pci !== null) {
      rankBody = D.rankStrip({
        label: 'Per-capita income across the ' + total + ' districts of Andhra Pradesh' +
          (LATEST ? ', ' + LATEST : ''),
        selfName: name || undefined,
        value: pci,
        peers: pciPeers,
        unit: '₹'
      });
    } else {
      var ladder = peers.filter(function (p) { return n(p.pci_rank) !== null; })
        .sort(function (a, b) { return n(a.pci_rank) - n(b.pci_rank); });
      if (ladder.length >= 2) {
        rankBody = D.drillList({
          label: 'All districts ordered by per-capita income rank, 1 = highest',
          items: ladder.map(function (p) {
            /* self by key when both carry one, else by display name */
            var self = (node.key && p.key && String(p.key) === String(node.key)) ||
              (!!name && String(p.name) === name);
            return {
              name: String(p.name),
              sub: ord(n(p.pci_rank)) + ' of ' + total + (self ? ' · this district' : '')
            };
          })
        });
        rankBody += '<p class="d-src">' + D.esc(
          'An ordering, not a magnitude comparison: this record carries each district’s ' +
          'per-capita income RANK but not the other districts’ per-capita figures, so no ' +
          'bar is drawn against them.' +
          (pciRank !== null && pci !== null
            ? ' ' + (name || 'This district') + ' is ' + ord(pciRank) + ' of ' + total +
              ' districts by per-capita income, at ' + D.fmtRs(pci) +
              (LATEST ? ' in ' + LATEST : '') + '.'
            : '')
        ) + '</p>';
      } else {
        rankBody = D.empty('Per-capita income ranks for the other districts are not ' +
          'carried on this record, so no peer comparison is drawn.');
      }
    }

    var rankNote = [];
    if (gddpRank !== null) {
      rankNote.push(ord(gddpRank) + ' of ' + total + ' districts by GDDP');
    }
    if (pciRank !== null) {
      rankNote.push(ord(pciRank) + ' of ' + total + ' districts by per-capita income');
    }
    if (rankNote.length) {
      rankBody += '<p class="d-src">' + D.esc(
        (name || 'This district') + ': ' + rankNote.join('; ') + '.'
      ) + '</p>';
    }

    out += D.section({
      title: 'Where it stands among the ' + total + ' districts',
      note: 'Peer set: all districts of Andhra Pradesh' + (LATEST ? ', ' + LATEST : ''),
      body: rankBody
    });

    /* ---- 8. drill down --------------------------------------------------- */
    var cons = arr(node.constituencies).filter(function (c) { return c; });
    out += D.section({
      title: 'Assembly constituencies',
      note: cons.length
        ? cons.length + ' constituencies · figures on the next level are constituency GCDP, ' +
          'a different series from district GDDP'
        : '',
      wide: true,
      body: D.drillList({
        items: cons.map(function (c) { return String(c).replace(/_/g, ' '); }),
        label: cons.length ? 'Drill down' : '',
        onpick: PICK_CONSTITUENCY,
        emptyReason: 'No constituencies are listed for this district.'
      })
    });

    /* ---- 9. provenance ---------------------------------------------------- */
    out += D.sourceNote(
      (node.source ? 'Source: ' + node.source + '.' : D.SOURCE_DIST) +
      ' The four-year series spans four estimate vintages; only ' +
      (LATEST || 'the latest year') + ' is a First Advance Estimate and it is not an outturn.' +
      (node.enriched ? '' : ' The detailed district workbook was not attached to this record, ' +
        'so only the index figures are shown.')
    );

    return out + '</div>';
  };
})(typeof window !== 'undefined' ? window : this);
