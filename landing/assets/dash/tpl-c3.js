/* ===========================================================================
   Swarna Andhra — constituency template C3: Industrial (industry >= 35%)

   Archetype thesis: the industrial growth curve IS the page. 20 of 175
   constituencies are C3.

   Order:
     stat row -> growthBullet (Industries Sector first, emphasised)
     -> compositionBars (share of GCDP) -> thrust chips
     -> profile narrative -> geography (only if published) -> mandal drill list.

   Reads ONLY the enriched node defined in enrich.js (DASH.ENRICHED_KEYS).
   Every key on that list is always present; every value may be null / [] / ''.
   Synchronous, no fetch, no colour literals: sector colours come from the data
   (node.share_colors, growth row colorHex) or from the component library.
   =========================================================================== */
(function (global) {
  'use strict';

  var D = global.DASH;
  if (!D) return;                       // components.js must load first
  global.DASH_TPL = global.DASH_TPL || {};

  function n(v) { return D.num(v); }

  function isIndustry(r) {
    return /^INDUSTR/i.test(String(r.code || '')) ||
           /industr|manufactur/i.test(String(r.name || ''));
  }

  /* Per-sector rows from the enriched node, Industries first — the steepest
     curve is the point of C3 — then the rest by baseline size.
     node.growth carries NO whole-economy TOTAL row (enrich.js strips it), so
     the total can never land on the same axis as its own components. */
  function growthRows(node) {
    var src = Array.isArray(node.growth) ? node.growth : [];
    var rows = src.filter(function (r) {
      return r && r.name && (n(r.baseline) !== null || n(r.target) !== null);
    }).map(function (r) {
      return {
        name: String(r.name),
        code: r.code || '',
        baseline: n(r.baseline),
        target: n(r.target),
        cagr: n(r.cagr),
        colorHex: r.colorHex
      };
    });
    if (!rows.length) return null;
    rows.sort(function (a, b) {
      var ai = isIndustry(a) ? 0 : 1, bi = isIndustry(b) ? 0 : 1;
      if (ai !== bi) return ai - bi;
      return (b.baseline || 0) - (a.baseline || 0);
    });
    return rows;
  }

  /* Composition items from node.shares, industry first because this is the
     industrial template. Colours are the portal's own (node.share_colors) or
     absent, in which case the library decides — never a literal from here. */
  function shareItems(node) {
    var s = node.shares || {};
    var col = node.share_colors || {};
    var defs = [
      { key: 'industry', name: 'Industry' },
      { key: 'services', name: 'Services' },
      { key: 'agri', name: 'Agriculture & allied' }
    ];
    var ind = [], rest = [];
    defs.forEach(function (d) {
      var pct = n(s[d.key]);
      if (pct === null) return;
      var it = { name: d.name, pct: pct, colorHex: col[d.key] };
      if (d.key === 'industry') ind.push(it); else rest.push(it);
    });
    rest.sort(function (a, b) { return b.pct - a.pct; });
    return ind.concat(rest);
  }

  /* --------------------------------------------------------------------- C3 */

  global.DASH_TPL.C3 = function (node) {
    node = node || {};
    var by = node.year_baseline || '2023-24';
    var ty = node.year_target || '2028-29';

    var rows = growthRows(node);
    var indRow = rows && rows.filter(isIndustry)[0];

    var out = '<div class="d-tpl d-tpl-c3">';

    /* ---- 1. stat row ---------------------------------------------------- */

    var cards = [];

    cards.push(D.statCard({
      label: 'GCDP baseline',
      value: D.fmtCr(node.gcdp_baseline) || null,
      sub: by + ' · measured',
      delta: n(node.gcdp_target) !== null
        ? 'Target ' + ty + ' ' + D.fmtCr(node.gcdp_target) + ' (a plan)'
        : null
    }));

    cards.push(D.statCard({
      label: 'Industry share',
      value: D.fmtPct(node.shares && node.shares.industry) || null,
      sub: 'of GCDP, ' + by
    }));

    /* Only call it an industry CAGR when a per-sector row actually says so.
       Otherwise it is the whole-economy CAGR and is labelled as such. */
    if (indRow && indRow.cagr !== null) {
      cards.push(D.statCard({
        label: 'Industry CAGR',
        value: D.fmtPct(indRow.cagr) || null,
        sub: 'planned, ' + by + ' to ' + ty
      }));
    } else {
      cards.push(D.statCard({
        label: 'GCDP CAGR (all sectors)',
        value: D.fmtPct(node.cagr) || null,
        sub: 'planned, ' + by + ' to ' + ty +
          (rows ? '' : ' · no sector split published for this record')
      }));
    }

    /* Provenance exactly as the portal states it, or nothing at all. 10 of 175
       records state none — this must never be back-filled with an assumption. */
    var popBits = [];
    if (node.population_note) popBits.push(node.population_note);
    if (n(node.area_sqkm) !== null) popBits.push(D.grp(node.area_sqkm) + ' sq km');
    if (n(node.density) !== null) popBits.push(D.grp(node.density) + ' per sq km');
    cards.push(D.statCard({
      label: 'Population',
      value: n(node.population) !== null ? D.grp(Math.round(n(node.population))) : null,
      sub: popBits.join(' · ')
    }));

    out += D.section({
      title: node.name ? node.name : 'Constituency',
      note: 'Industrial constituency' + (node.why ? ' — ' + node.why : ''),
      body: D.statRow(cards)
    });

    /* ---- 2. the industrial growth curve --------------------------------- */

    var growthBody;
    if (rows) {
      growthBody = D.growthBullet({
        rows: rows,
        emphasis: 'Industr',
        baselineYear: by,
        targetYear: ty
      });

      /* Reconciliation against the portal's own whole-economy target. A single
         sector cannot exceed the constituency total. The figure is published,
         so it is plotted unaltered — but the reader is told it does not add up.
         Nothing is suppressed and nothing is adjusted. */
      var tot = n(node.gcdp_target), flagged = [];
      if (tot !== null && tot > 0) {
        rows.forEach(function (r) {
          if (r.target !== null && r.target > tot) flagged.push(r.name);
        });
      }
      if (flagged.length) {
        growthBody += D.sourceNote(
          'Published as-is, but does not reconcile: the ' + ty + ' target for ' +
          flagged.join(', ') + ' exceeds the portal\'s own ' + ty +
          ' target for the whole constituency. Both figures are the portal\'s and ' +
          'both are shown unaltered; the inconsistency is the portal\'s too.'
        );
      }
    } else {
      /* Bare path: no per-sector rows exist, so the thesis of this template
         cannot be drawn. Say that, rather than stubbing an un-emphasised
         whole-economy bar that pretends to be the sector story. */
      growthBody = D.empty(
        'Sector-wise baselines and targets are not published for this ' +
        'constituency, so the industrial growth path cannot be charted. The ' +
        'whole-economy baseline and target are shown above.'
      );
    }

    out += D.section({
      title: 'Industrial growth path',
      note: 'Baseline ' + by + ' measured · target ' + ty + ' planned',
      body: growthBody
    });

    /* ---- 3. composition of the economy ---------------------------------- */

    var items = shareItems(node);
    var compBody = items.length
      ? D.compositionBars({ items: items })   /* scale:'share' — width IS the % */
      : D.empty('Sector shares are not published for this constituency.');

    compBody += D.sourceNote(
      'Sub-sector splits within industry (manufacturing, construction, mining, ' +
      'utilities) are not published at constituency level, so the composition ' +
      'shown is the three official sector aggregates.'
    );

    out += D.section({
      title: 'Composition of the economy',
      note: 'Share of GCDP, ' + by,
      body: compBody
    });

    /* ---- 4. thrust sectors ----------------------------------------------- */

    out += D.section({
      title: 'Thrust sectors',
      note: 'Swarna Andhra Vision 2029',
      body: D.thrustChips(node.thrust)
    });

    /* ---- 5. narrative ---------------------------------------------------- */

    out += D.section({
      title: 'Constituency profile',
      note: 'AP Assembly Constituencies portal',
      body: node.profile_html
        ? D.narrative(node.profile_html)
        : D.empty('No constituency profile text is published for this place.')
    });

    /* Geography is rendered only when the portal actually published it. There
       is no connectivity or infrastructure field at constituency level, so no
       heading here claims to be about one. */
    if (node.geography_html) {
      out += D.section({
        title: 'Geography',
        note: 'AP Assembly Constituencies portal',
        body: D.narrative(node.geography_html)
      });
    }

    /* ---- 6. mandal drill list -------------------------------------------- */

    var mandals = Array.isArray(node.mandals) ? node.mandals : [];
    out += D.section({
      title: 'Mandals',
      note: mandals.length ? mandals.length + ' in this constituency' : '',
      body: D.drillList({
        items: mandals,
        label: 'Mandals in this constituency',
        emptyReason: 'No mandal list is published for this constituency.'
      })
    });

    out += D.sourceNote(node.source ? 'Source: ' + node.source + '. GCDP baseline ' +
      by + '; target ' + ty + ' (Swarna Andhra Vision 2029 plan).' : D.SOURCE_APC);

    return out + '</div>';
  };
})(typeof window !== 'undefined' ? window : this);
