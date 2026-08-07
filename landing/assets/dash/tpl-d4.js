/* ===========================================================================
   Swarna Andhra — D4 Emerging / Agency district template.

   9 of 28 districts are D4: three scheduled/agency districts (Alluri Seetharama
   Raju, Parvathipuram Manyam, Polavaram) and six bottom-8-PCI districts
   (Srikakulam, Vizianagaram, Palnadu, Markapuram, Kurnool, Annamayya).

   THESIS — a plan, not a scoreboard.
   Ranking these districts on income alone is the wrong frame, so the layout
   leads with DIRECTION OF TRAVEL and COMPOSITION, not with rank:
     stat row (GDDP, GDDP growth, population, PCI)
       -> 4-year GDDP trajectory
       -> composition of the district's own GDVA (node.sectors)
       -> tri-sector donut
       -> this district's weight inside the STATE sector totals
       -> constituency drill list -> source note.
   Rank appears once, as plain text naming the peer set, and only where the
   data carries it. node.why is echoed verbatim, because 'scheduled/agency
   district' and 'PCI rank N/28 — emerging' are DIFFERENT situations and this
   template must not describe an agency district as merely low-income.

   DATA CONTRACT
   The only input is the ENRICHED DISTRICT NODE defined in enrich.js. Every key
   read here is on DASH.DISTRICT_KEYS. Nothing is fetched; synchronous.
   node.enriched === false means only the bare index record was available, and
   every block below has a defined bare-path rendering.

   THE TWO PERCENTAGES
   node.aggregates[k][i] and node.sectors[i] each carry BOTH pct_of_district
   (the sector's share of THIS district's GDVA) and pct_of_state_sector (this
   district's share of the STATE total for that sector). They differ by several
   times over. In this file they are read through two named helpers, never
   inline, and every caption states which one the geometry encodes.

   COLOURS
   No colour literals. The trajectory SVG paints in currentColor only, so it
   follows the surrounding text colour on both the light page and the dark
   .vstage. Every other block is a library component and inherits the library's
   dark-stage handling.
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

  /* how many of the ~17 real sectors the composition block shows */

  function n(v) { return DASH.num(v); }
  function txt(s) { return String(s === null || s === undefined ? '' : s).trim(); }

  /* --- the two percentages, read only through these ---------------------- */
  /* share of THIS district's own GDVA */
  function pctOfDistrict(o) { return n(o && o.pct_of_district); }
  /* this district's share of the STATE total for that sector */
  function pctOfStateSector(o) { return n(o && o.pct_of_state_sector); }

  function latestYear(node) { return txt(node.latest_year) || '2025-26 (FAE)'; }

  /* node.why is the classifier's own sentence. Agency status is asserted only
     when the classifier asserted it — never inferred from a low rank. */
  function isAgency(node) { return /scheduled|agency/i.test(txt(node.why)); }

  function headline(node) {
    return isAgency(node) ? 'scheduled / agency district' : 'emerging district';
  }

  /* ------------------------------------------------------------ stat cards */

  function stats(node) {
    var ly = latestYear(node);
    var cards = [];

    cards.push(DASH.statCard({
      label: 'District GDDP',
      value: DASH.fmtCr(node.gddp) || null,
      sub: ly,
      /* growth is the leading figure for this archetype, so it rides the
         headline card as well as carrying its own card below */
      delta: n(node.gddp_growth) !== null
        ? DASH.fmtPct(node.gddp_growth) + ' over the previous year'
        : null
    }));

    cards.push(DASH.statCard({
      label: 'GDDP growth',
      value: DASH.fmtPct(node.gddp_growth) || null,
      sub: ly + ' over the previous year'
    }));

    cards.push(DASH.statCard({
      label: 'Population',
      value: n(node.population) !== null ? DASH.grp(n(node.population)) + ' persons' : null,
      sub: ly + ' — district workbook'
    }));

    cards.push(DASH.statCard({
      label: 'Per-capita income',
      value: DASH.fmtRs(node.pci) || null,
      sub: ly,
      delta: n(node.pci_growth) !== null
        ? DASH.fmtPct(node.pci_growth) + ' over the previous year'
        : null
    }));

    return DASH.statRow(cards);
  }

  /* ---------------------------------------------------------- trajectory ---

     There is no line-chart component, so this is composed here: a column per
     year, height proportional to GDDP, painted in currentColor at two opacity
     levels (latest year solid, earlier years washed). Nothing is encoded in
     geometry alone — every figure repeats as text in the list below and inside
     the SVG's aria-label and <title>.

     The four years are DIFFERENT ESTIMATE VINTAGES. The chart says so in its
     axis labels (each column is tagged with its own vintage code) and again in
     the caption. Only 2025-26 is the First Advance Estimate. */

  function trajectorySvg(pts) {
    var W = 640, H = 168, PAD_B = 34, PAD_T = 24;
    var max = 0;
    pts.forEach(function (p) { max = Math.max(max, p.value); });
    if (max <= 0) return '';

    var slot = W / pts.length;
    var bw = Math.min(74, slot * 0.46);
    var body = '';
    var aria = [];

    pts.forEach(function (p, i) {
      var cx = slot * (i + 0.5);
      var h = (p.value / max) * (H - PAD_B - PAD_T);
      var y = H - PAD_B - h;
      var isLast = i === pts.length - 1;

      body += '<rect x="' + (cx - bw / 2).toFixed(1) + '" y="' + y.toFixed(1) + '"' +
        ' width="' + bw.toFixed(1) + '" height="' + Math.max(h, 1).toFixed(1) + '"' +
        ' rx="3" fill="currentColor" fill-opacity="' + (isLast ? '0.82' : '0.30') + '"></rect>';

      if (p.growth !== null) {
        body += '<text x="' + cx.toFixed(1) + '" y="' + (y - 7).toFixed(1) + '"' +
          ' text-anchor="middle" font-size="13" font-weight="700"' +
          ' fill="currentColor" fill-opacity="0.78">' +
          DASH.esc(DASH.fmtPct(p.growth)) + '</text>';
      }

      body += '<text x="' + cx.toFixed(1) + '" y="' + (H - PAD_B + 16) + '"' +
        ' text-anchor="middle" font-size="13" fill="currentColor" fill-opacity="0.72">' +
        DASH.esc(p.label) + '</text>';

      if (p.estimate) {
        body += '<text x="' + cx.toFixed(1) + '" y="' + (H - PAD_B + 30) + '"' +
          ' text-anchor="middle" font-size="11" letter-spacing="0.5"' +
          ' fill="currentColor" fill-opacity="0.5">' + DASH.esc(p.estimate) + '</text>';
      }

      aria.push(p.label + (p.estimate ? ' ' + p.estimate : '') + ' ' + DASH.fmtCr(p.value) +
        (p.growth !== null ? ', ' + DASH.fmtPct(p.growth) + ' over the previous year' : ''));
    });

    /* baseline rule */
    body += '<line x1="0" y1="' + (H - PAD_B) + '" x2="' + W + '" y2="' + (H - PAD_B) + '"' +
      ' stroke="currentColor" stroke-opacity="0.18" stroke-width="1"></line>';

    var label = 'District GDDP by year. ' + aria.join('. ') + '.';

    return '<div style="overflow-x:auto;max-width:100%">' +
      '<svg viewBox="0 0 ' + W + ' ' + H + '" width="100%" height="auto"' +
      ' preserveAspectRatio="xMidYMid meet" role="img" style="display:block;max-width:100%"' +
      ' aria-label="' + DASH.esc(label) + '">' +
      '<title>' + DASH.esc(label) + '</title>' + body + '</svg></div>';
  }

  function trajectoryList(pts) {
    var out = '<ul class="d-legend">';
    pts.forEach(function (p, i) {
      var isLast = i === pts.length - 1;
      out += '<li' + (isLast ? ' class="is-emph"' : '') + '>' +
        '<span class="d-dot" style="background:currentColor;opacity:' +
          (isLast ? '.82' : '.3') + '"></span>' +
        '<span class="d-lg-n">' + DASH.esc(p.label) +
          (p.estimate ? ' (' + DASH.esc(p.estimate) + ')' : '') +
          (p.growth !== null ? ' &middot; ' + DASH.esc(DASH.fmtPct(p.growth)) + ' growth' : '') +
        '</span>' +
        '<span class="d-lg-v">' + DASH.esc(DASH.fmtCr(p.value)) + '</span>' +
      '</li>';
    });
    return out + '</ul>';
  }

  function trajectory(node) {
    var pts = (Array.isArray(node.gddp_series) ? node.gddp_series : [])
      .filter(function (p) { return p && n(p.value) !== null; })
      .map(function (p) {
        return {
          label: txt(p.label) || txt(p.year),
          estimate: txt(p.estimate),
          value: n(p.value),
          growth: n(p.growth)
        };
      });

    if (pts.length < 2) {
      return DASH.empty(
        'The year-by-year GDDP series is not available for this district, so no ' +
        'trajectory is drawn.'
      );
    }

    var svg = trajectorySvg(pts);
    if (!svg) {
      return DASH.empty('The published GDDP figures for these years are zero, so no trajectory is drawn.');
    }

    var vintages = [];
    pts.forEach(function (p) {
      if (p.estimate && vintages.indexOf(p.estimate) === -1) vintages.push(p.estimate);
    });

    var caption = 'Column height is GDDP in ₹ crore; the figure above each column is ' +
      'growth over the previous year. ';
    caption += vintages.length > 1
      ? 'The years carry different estimate vintages (' + vintages.join(', ') +
        ') and are not equally firm — only 2025-26 is the First Advance Estimate. ' +
        'Each column is tagged with its own vintage.'
      : 'Every year shown carries the same estimate vintage' +
        (vintages.length ? ' (' + vintages[0] + ')' : '') + '.';

    return svg + trajectoryList(pts) + DASH.sourceNote(caption);
  }

  /* ------------------------------------------------------- composition ----

     node.sectors is the ~17 real sectors for the latest year, already sorted by
     pct_of_district descending, with totals, taxes and subsidies excluded so
     they never double-count. The bars use the library default scale ('share'):
     the track is 100%, so bar width IS the published share of this district's
     own GDVA. Do NOT pass scale:'relative' under this caption. */

  function composition(node) {
    var all = Array.isArray(node.sectors) ? node.sectors : [];
    var items = [];

    all.forEach(function (s) {
      if (!s) return;
      var name = txt(s.name);
      var pct = pctOfDistrict(s);          /* share of THIS district's GDVA */
      if (!name || pct === null) return;
      items.push({ name: name, pct: pct, rank: n(s.rank) });
    });

    if (!items.length) {
      return DASH.empty(
        'Sector-wise shares of this district\'s GDVA are not published in this record.'
      );
    }

    /* Top 3 as a dot plot (see components.js sectorDots). Three sectors carry the
       "what this place runs on" story; the full 17-bar list was a wall. */
    var shown = items.slice(0, 3);
    var covered = shown.reduce(function (a, it) { return a + it.pct; }, 0);
    var note = DASH.sourceNote(
      'The three largest of ' + items.length + ' published sectors, together ' +
      DASH.fmtPct(covered) + ' of this district\'s GDVA. Rank is this district\'s ' +
      'standing in that sector statewide. Totals, taxes and subsidies are excluded ' +
      'from the published list, so these shares do not double-count.'
    );

    return DASH.sectorDots(shown, { total: n(node.district_count) || 28 }) + note;
  }

  /* --------------------------------------------------------------- donut --
     Tri-sector shares. node.shares is the LATEST pct_of_district for each
     aggregate — a share of this district. It is never the state-sector figure. */

  function donut(node) {
    var sh = node.shares && typeof node.shares === 'object' ? node.shares : null;
    if (!sh) {
      return DASH.empty(
        'The agriculture / industry / services split of this district\'s GDVA is ' +
        'not published in this record.'
      );
    }
    var use = {};
    SECTOR_ORDER.forEach(function (k) {
      if (n(sh[k]) !== null) use[k] = n(sh[k]);
    });
    if (!Object.keys(use).length) {
      return DASH.empty(
        'The agriculture / industry / services split of this district\'s GDVA is ' +
        'not published in this record.'
      );
    }
    return DASH.sectorDonut({
      shares: use,
      centerLabel: 'of district GDVA'
    });
  }

  /* ------------------------------------------- weight inside the state -----

     THE OTHER PERCENTAGE. pct_of_state_sector is this district's share of the
     ANDHRA PRADESH total for that sector — a completely different number from
     the share above. Drawn against the same 100% track, where 100% would mean
     the whole state's output of that sector sits in this district. The caption
     and the section title both say so. */

  function stateWeight(node) {
    var agg = node.aggregates && typeof node.aggregates === 'object' ? node.aggregates : null;
    if (!agg) {
      return DASH.empty(
        'This district\'s share of the state sector totals is not published in this record.'
      );
    }

    var items = [];
    SECTOR_ORDER.forEach(function (k) {
      var series = Array.isArray(agg[k]) ? agg[k] : [];
      var latest = null;
      for (var i = series.length - 1; i >= 0; i--) {
        if (series[i] && pctOfStateSector(series[i]) !== null) { latest = series[i]; break; }
      }
      if (!latest) return;
      items.push({
        name: SECTOR_LABEL[k],
        pct: pctOfStateSector(latest)   /* share of the STATE total, not of this district */
      });
    });

    if (!items.length) {
      return DASH.empty(
        'This district\'s share of the state sector totals is not published in this record.'
      );
    }

    return DASH.compositionBars({ items: items }) + DASH.sourceNote(
      'Each bar is this district\'s share of Andhra Pradesh\'s TOTAL output in that ' +
      'sector, drawn against a 100% track — 100% would mean the entire state\'s ' +
      'output sits in this district. This is not the sector\'s share of the district, ' +
      'which is the figure shown above; the two are different numbers.'
    );
  }

  /* ---------------------------------------------------- rank, stated plainly

     Shown once, as text, with the peer set named. Growth rank is preferred to
     level rank where the data carries one; the PCI rank is stated flatly and is
     never styled as a score. */

  function rankLine(node) {
    var count = n(node.district_count) || 28;
    var bits = [];

    if (n(node.gddp_rank) !== null) {
      bits.push(DASH.grp(n(node.gddp_rank)) + ' of ' + count +
        ' districts by district GDDP, ' + latestYear(node));
    }
    if (n(node.pci_rank) !== null) {
      bits.push(DASH.grp(n(node.pci_rank)) + ' of ' + count +
        ' districts by per-capita income');
    }
    if (!bits.length) return '';
    return DASH.sourceNote('Position among peers: ' + bits.join('; ') + '.');
  }

  /* ------------------------------------------------------------------ main */

  global.DASH_TPL.D4 = function (node) {
    if (!node || typeof node !== 'object') {
      return DASH.empty('No district record was supplied.');
    }

    var name = txt(node.name);
    var ly = latestYear(node);
    var out = '<div class="dash dash-d4">';

    /* ---- header: what this place is, then the four headline figures ---- */
    var why = txt(node.why);
    var classNote = why
      ? DASH.sourceNote(
          isAgency(node)
            ? 'Classified from the district record as a scheduled / agency district. ' +
              'That is a constitutional and administrative status, not a statement ' +
              'about income, and it is the reason this view leads with trajectory ' +
              'rather than with rank.'
            : 'Classified as emerging: ' + why + ', out of ' +
              (n(node.district_count) || 28) + ' districts.'
        )
      : '';

    out += DASH.section({
      title: name ? name + ' — ' + headline(node) : headline(node),
      note: ly + ' — First Advance Estimate',
      body: stats(node) + DASH.sparkRow(node.gddp_series, node.pci_series) + classNote +
        (node.enriched === false
          ? DASH.sourceNote(
              'Only the summary index record was available for this district; the ' +
              'year-by-year workbook figures are not attached to this view.'
            )
          : '')
    });

    /* ---- the lead: direction of travel ---- */
    out += DASH.section({
      title: 'Where the district economy is going',
      note: 'District GDDP, four years, oldest first',
      body: trajectory(node) + rankLine(node)
    });

    /* ---- what the economy is made of ---- */
    out += DASH.section({
      title: 'What the district economy is made of',
      note: 'Share of this district\'s own GDVA, ' + ly + ' — bars against a 100% track',
      body: composition(node)
    });

    out += DASH.section({
      title: 'Agriculture, industry and services',
      note: 'Share of this district\'s own GDVA, ' + ly,
      body: donut(node)
    });

    /* ---- the same sectors, measured against the state ---- */
    out += DASH.section({
      title: 'This district\'s weight in the state',
      note: 'Share of Andhra Pradesh\'s total for each sector, ' + ly,
      body: stateWeight(node)
    });

    /* ---- children ---- */
    var kids = Array.isArray(node.constituencies) ? node.constituencies : [];
    out += DASH.section({
      title: 'Constituencies',
      note: kids.length ? kids.length + ' in this district' : null,
      body: DASH.drillList({
        items: kids,
        label: 'Assembly constituencies in this district',
        onpick: 'DASH_PICK_CONSTITUENCY',
        emptyReason: 'No constituencies are listed for this district.'
      })
    });

    out += DASH.sourceNote(txt(node.source) || DASH.SOURCE_DIST);
    return out + '</div>';
  };
})(typeof window !== 'undefined' ? window : this);
