/* ===========================================================================
   Swarna Andhra — M3 Scheduled / agency mandal template.

   39 of the 718 mandal entries in mandal_index.json classify as M3, all of them
   inside Alluri Seetharama Raju, Parvathipuram Manyam or Polavaram. Their
   node.why reads 'scheduled/agency mandal'.

   THESIS — an administrative fact, then borrowed context, then the document.
   A scheduled-area mandal is not usefully described as "rural" and cannot be
   ranked on income, because no mandal-level income exists. So this page states
   the administrative status, states plainly what it can and cannot show, then
   hands over to the parent constituency's published figures — clearly marked as
   the constituency's — and finally to the vision document.

   It deliberately does NOT editorialise about disadvantage, forest dependence or
   tribal welfare outcomes. We hold no mandal-level figure of any kind, so any
   such sentence would be assertion, not data. The archetype exists to stop the
   page framing the place as merely rural or ranking it; it is not a licence to
   narrate a story the corpus does not carry.

   DATA CONTRACT
   The only input is the ENRICHED MANDAL NODE from DASH.enrichMandal(). Every
   key read here is on DASH.MANDAL_KEYS. Nothing is fetched; synchronous.

   THE DEFINING CONSTRAINT
   node.has_own_figures is always false. There is no mandal GDP, population or
   NOT-YET-EXTRACTED, NOT NON-EXISTENT. An earlier version of this file claimed
   no mandal figures existed anywhere. That was wrong: the mandal vision PDFs
   carry GVA by broad sector and sub-sector, population, literacy, land holdings,
   land use, crops, irrigation and more, in extractable tables. They simply have
   not been parsed into this site yet. node.has_own_figures stays false until an
   extractor lands; do not word anything as though the data does not exist.
   Everything under
   node.inherited describes THE CONSTITUENCY — a mandal is one of typically 3-6
   inside it — so every inherited figure in this file is rendered inside one
   section that names node.inherited_from, and every label carrying a number
   repeats that constituency name. When node.inherited is null the whole block is
   replaced by DASH.empty(); nothing is stubbed, zeroed or placeheld.

   PDFs
   node.pdfs are repo-relative paths to local files that are NOT web-servable
   from landing/. The document is named; no href is emitted, because a link that
   404s is worse than no link.

   COLOURS
   No colour literals, no inline colour styles. Every block is a library
   component or plain markup on the library's own classes, so the dark .vstage
   overrides in components.css apply unchanged.
   =========================================================================== */
(function (global) {
  'use strict';

  var DASH = global.DASH;
  global.DASH_TPL = global.DASH_TPL || {};

  var SECTOR_ORDER = ['agri', 'industry', 'services'];

  function n(v) { return DASH.num(v); }
  function txt(s) { return String(s === null || s === undefined ? '' : s).trim(); }
  function e(s) { return DASH.esc(s); }

  function para(parts) {
    var ps = (parts || []).filter(Boolean).map(function (p) { return '<p>' + p + '</p>'; });
    return ps.length ? '<div class="d-narr">' + ps.join('') + '</div>' : '';
  }

  function list(node) { return Array.isArray(node) ? node : []; }

  /* Sibling mandals, de-duplicated by name. The roster can carry one mandal
     twice — once under its -R entry and once under -U — and both collapse to the
     same display name, which would read as two different places and would also
     inflate the "one of N" count. De-duplicated here, and reported upstream
     rather than patched there: this template does not own the index. */
  function sibNames(node) {
    var seen = {}, out = [];
    list(node.siblings).map(txt).filter(Boolean).forEach(function (s) {
      if (seen[s]) return;
      seen[s] = 1;
      out.push(s);
    });
    return out;
  }

  /* ------------------------------------------------------------ identity ---
     The breadcrumb is district -> constituency -> mandal, already filtered of
     empty names by enrich.js. Rendered as text, not links: this template has no
     knowledge of the page's routing. */

  function breadcrumb(node) {
    var bits = list(node.breadcrumb)
      .map(function (b) { return b && txt(b.name) ? e(txt(b.name)) : ''; })
      .filter(Boolean);
    if (!bits.length) return '';
    return '<p class="d-drill-lbl">' + bits.join(' &rsaquo; ') + '</p>';
  }

  /* The portal's own -R/-U marker. 47 of 794 roster entries carry none and
     arrive as 'unknown'; that is never guessed here or anywhere upstream. The
     marker is reported as a roster fact and explicitly demoted, because in a
     scheduled area the rural/urban split is not the operative frame. */
  function kindSentence(node) {
    var k = txt(node.kind);
    if (k === 'rural' || k === 'urban') {
      return 'The constituency roster marks this mandal <strong>' + e(k) + '</strong>. ' +
        'That marker is recorded here for completeness only — in a scheduled area the ' +
        'rural/urban split is not the frame the vision document works in.';
    }
    return 'The constituency roster carries <strong>no rural or urban marker</strong> for ' +
      'this mandal, and none is assumed here. It is one of the 47 roster entries with no ' +
      'marker published.';
  }

  function identity(node) {
    var why = txt(node.why);
    var isScheduled = /scheduled|agency/i.test(why);

    var lead = isScheduled
      ? 'This mandal is shown with the <strong>scheduled (agency) area</strong> view ' +
        'because its district is one of the three AP districts treated as agency ' +
        'areas here \u2014 Alluri Seetharama Raju, Parvathipuram Manyam and Polavaram. ' +
        'The mandal roster itself records no scheduled-area field; this is a ' +
        'district-level classification, not a per-mandal one. It says nothing about ' +
        'income or output, and no income or output figure for this mandal exists in ' +
        'this dataset.'
      : 'This mandal is shown with the agency view.' +
        (why ? ' The record states: &ldquo;' + e(why) + '&rdquo;.' : '');

    var where = '';
    var c = txt(node.constituency), d = txt(node.district).replace(/_/g, ' ');
    if (c && d) {
      where = 'It sits in the <strong>' + e(c) + '</strong> assembly constituency, ' +
        e(d) + ' district.';
    } else if (c) {
      where = 'It sits in the <strong>' + e(c) + '</strong> assembly constituency.';
    } else if (d) {
      where = 'It sits in ' + e(d) + ' district.';
    }

    return breadcrumb(node) + para([lead, where, kindSentence(node)]);
  }

  /* ---------------------------------------------- what this page can show ---
     node.has_own_figures is in the contract precisely so a template must
     acknowledge the situation rather than quietly assume otherwise. Stated in
     plain words, before any borrowed number appears, so a reader meets the
     caveat first and the figures second. */

  function scope(node) {
    var c = txt(node.inherited_from);
    var sibs = sibNames(node);
    /* this mandal plus its siblings — stated only when the roster gives us both */
    var count = sibs.length ? sibs.length + 1 : 0;

    var a = 'Mandal-level figures are not yet loaded into this dashboard. The mandal ' +
      'vision documents do publish them \u2014 GVA by sector, population, literacy and ' +
      'land use \u2014 but those tables have not been extracted from the PDFs into this ' +
      'site yet.';

    var b;
    if (c) {
      b = 'Every figure on this page below therefore belongs to the <strong>' + e(c) +
        '</strong> constituency as a whole' +
        (count ? ', of which this mandal is one of ' + count + '' : '') +
        '. A constituency figure is not this mandal\'s share of anything, and it is not ' +
        'divided down here.';
    } else {
      b = 'No parent constituency record is attached to this view, so no economic figure ' +
        'is shown on this page at all.';
    }

    return para([a, b]);
  }

  /* ---------------------------------------------------- inherited context ---
     ALL of node.inherited lives inside this one section, whose title, note and
     every component label name node.inherited_from. Baseline is measured;
     target is a plan. They are never summed and the library renders them
     differently. */

  function inheritedHeadline(node, c) {
    var inh = node.inherited;
    var cards = [];

    cards.push(DASH.statCard({
      label: c + ' constituency — GCDP baseline',
      value: DASH.fmtCr(inh.gcdp_baseline) || null,
      sub: txt(inh.year_baseline) + ' — measured, whole constituency'
    }));

    cards.push(DASH.statCard({
      label: c + ' constituency — GCDP target',
      value: DASH.fmtCr(inh.gcdp_target) || null,
      sub: txt(inh.year_target) + ' — a plan, not an outturn'
    }));

    cards.push(DASH.statCard({
      label: c + ' constituency — CAGR',
      value: DASH.fmtPct(inh.cagr) || null,
      sub: 'a year, ' + txt(inh.year_baseline) + ' to ' + txt(inh.year_target) + ', as published'
    }));

    return DASH.statRow(cards);
  }

  function inheritedBullet(node, c) {
    var inh = node.inherited;
    if (n(inh.gcdp_baseline) === null && n(inh.gcdp_target) === null) {
      return DASH.empty(
        'No baseline or target GCDP is published for the ' + c + ' constituency, so no ' +
        'growth bar is drawn.'
      );
    }
    return DASH.growthBullet({
      rows: [{
        name: c + ' constituency — whole economy',
        baseline: inh.gcdp_baseline,
        target: inh.gcdp_target,
        cagr: inh.cagr
      }],
      baselineYear: txt(inh.year_baseline),
      targetYear: txt(inh.year_target)
    });
  }

  function inheritedShares(node, c) {
    var sh = node.inherited.shares;
    if (!sh || typeof sh !== 'object') {
      return DASH.empty(
        'The sector split of the ' + c + ' constituency\'s GCDP is not published in this record.'
      );
    }
    var use = {};
    SECTOR_ORDER.forEach(function (k) { if (n(sh[k]) !== null) use[k] = n(sh[k]); });
    if (!Object.keys(use).length) {
      return DASH.empty(
        'The sector split of the ' + c + ' constituency\'s GCDP is not published in this record.'
      );
    }
    return DASH.sectorDonut({
      shares: use,
      title: c + ' constituency sector shares',
      centerLabel: 'of ' + c + ' GCDP'
    });
  }

  function inherited(node) {
    var c = txt(node.inherited_from);
    if (!node.inherited || !c) {
      return DASH.empty(
        'No parent constituency record is attached to this mandal, and no figure exists at ' +
        'mandal level, so no economic figures can be shown for this place.'
      );
    }

    var inh = node.inherited;
    var thrust = Array.isArray(inh.thrust) ? inh.thrust : [];

    var body = inheritedHeadline(node, c) +
      DASH.sourceNote(
        'Every figure in this section is the ' + c + ' constituency\'s, published for the ' +
        'constituency as a whole. None of it is measured for this mandal and none of it is ' +
        'this mandal\'s share. Baseline ' + txt(inh.year_baseline) + ' is measured; target ' +
        txt(inh.year_target) + ' is a plan.'
      ) +
      inheritedBullet(node, c) +
      inheritedShares(node, c);

    if (thrust.length) {
      body += '<p class="d-drill-lbl">Thrust sectors named for the ' + e(c) +
        ' constituency</p>' + DASH.thrustChips(thrust);
    }

    return body;
  }

  /* ------------------------------------------------------------- siblings ---
     The other mandals sharing the parent constituency. This is the honest way
     to show what the inherited figures actually span. */

  function siblings(node) {
    /* The roster can carry a mandal twice — once under its -R entry and once
       under -U — and both collapse to one name. Listing the same place twice
       would read as two mandals, so the list is de-duplicated here. Reported
       upstream rather than fixed there: this template does not own the index. */
    var sibs = sibNames(node);
    var c = txt(node.constituency);
    if (!sibs.length) {
      return DASH.empty(
        'No other mandals are listed' + (c ? ' for the ' + c + ' constituency' : '') +
        ' in the roster.'
      );
    }
    return DASH.drillList({
      items: sibs,
      label: 'Other mandals sharing ' +
        (c ? 'the ' + c + ' constituency' : 'this constituency') +
        ' — the constituency figures above cover all of them together',
      onpick: 'DASH_PICK_MANDAL'
    });
  }

  /* ------------------------------------------------------------- document ---
     node.pdfs are repo-relative paths to local files. They are NOT servable
     from landing/, so the document is named and never linked. */

  function base(p) {
    var s = txt(p).split('/').pop();
    return s.replace(/\.pdf$/i, '').replace(/_/g, ' ');
  }

  function document_(node) {
    var pdfs = list(node.pdfs).map(txt).filter(Boolean);
    if (!node.has_pdf || !pdfs.length) {
      return DASH.empty('No mandal vision document is recorded for this mandal.');
    }
    var items = pdfs.map(function (p) { return { name: base(p), sub: 'PDF' }; });
    return DASH.drillList({
      items: items,
      label: pdfs.length === 1
        ? 'A mandal vision and action plan exists for this mandal:'
        : pdfs.length + ' mandal vision and action plan documents exist for this mandal:'
    }) + DASH.sourceNote(
      'These are documents held in the project corpus, not files published on this site, ' +
      'so no download link is offered here. They carry this mandal\u2019s own GVA, ' +
      'demographic and land-use tables, which are not yet extracted into this dashboard.'
    );
  }

  /* ------------------------------------------------------------------ main */

  global.DASH_TPL.M3 = function (node) {
    if (!node || typeof node !== 'object') {
      return DASH.empty('No mandal record was supplied.');
    }

    var name = txt(node.name);
    var mCons = txt(node.constituency), mDist = txt(node.district).replace(/_/g, ' ');
    var out = '<div class="dash dash-m3">';

    var of = [];
    if (mCons) of.push({ kind: 'constituency', name: mCons, joiner: 'in' });
    if (mDist) of.push({ kind: 'district', name: mDist, joiner: 'of' });
    var mRank = (node.own && node.own.rank !== null && node.own.rank_total !== null)
      ? DASH.rankBadge({ rank: node.own.rank, total: node.own.rank_total,
          basis: 'GDDP in ' + mCons }) : '';
    out += DASH.section({
      titleHtml: DASH.placeCrumb(name || 'Mandal', 'scheduled / agency mandal', of),
      note: txt(node.why) || null,
      aside: mRank,
      body: identity(node)
    });

    out += DASH.mandalOwnSection(node);

    if (!node.has_own_figures) {
      out += DASH.section({
        title: 'What this page can and cannot show',
        note: 'No figure on this page is measured for this mandal',
        body: scope(node)
      });
    }

    var c = txt(node.inherited_from);
    out += DASH.section({
      title: c ? 'The ' + c + ' constituency, which contains this mandal' : 'Economic figures',
      note: c ? 'Constituency figures — not this mandal\'s' : null,
      body: inherited(node)
    });

    out += DASH.section({
      title: 'The rest of the constituency',
      body: siblings(node)
    });

    out += DASH.section({
      title: 'Vision document',
      body: document_(node)
    });

    out += DASH.sourceNote(txt(node.source) ||
      'AP Assembly Constituencies portal (mandal roster) · mandal vision documents');
    return out + '</div>';
  };
})(typeof window !== 'undefined' ? window : this);
