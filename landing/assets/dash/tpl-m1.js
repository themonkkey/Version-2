/* ===========================================================================
   Swarna Andhra — M1 Rural mandal template.

   632 of 794 mandal entries are M1. It is the largest group by a wide margin,
   so it must read as the main case and not as a fallback.

   THE DEFINING CONSTRAINT
   No structured figures exist at mandal level anywhere in the corpus. The
   NOT-YET-EXTRACTED, NOT NON-EXISTENT. An earlier version of this file claimed
   no mandal figures existed anywhere. That was wrong: the mandal vision PDFs
   carry GVA by broad sector and sub-sector, population, literacy, land holdings,
   land use, crops, irrigation and more, in extractable tables. They simply have
   not been parsed into this site yet. node.has_own_figures stays false until an
   extractor lands; do not word anything as though the data does not exist.
   Every number this page can display is INHERITED from the parent constituency
   and describes THE CONSTITUENCY — a mandal is one of typically 3-6 mandals
   inside it, so a constituency figure is not this mandal's share of anything.

   The page is therefore narrative-and-context-first. It is deliberately shorter
   than the district and constituency pages. It is not padded with borrowed
   numbers to match their density.

   Composition:
     identity header (breadcrumb, rural/urban marker as the portal states it)
     -> what this page can and cannot show
     -> the parent constituency's economy, every figure attributed to
        node.inherited_from, inside ONE section that names it
     -> the other mandals of that constituency, so a reader can move sideways
     -> the vision document, named but not linked
     -> source note.

   DATA CONTRACT
   The only input is the ENRICHED MANDAL NODE defined in enrich.js. Every key
   read here is on DASH.MANDAL_KEYS. Nothing is fetched; synchronous.

   HONESTY
   - No figure is invented. Missing input becomes DASH.empty naming what is
     missing — never a zero, never a placeholder.
   - No inherited figure is ever presented as the mandal's own. Each one is
     labelled with node.inherited_from, and all of them live in one section
     whose title and note say whose figures they are.
   - Baseline is node.inherited.year_baseline and MEASURED; target is
     year_target and A PLAN. They are never summed.
   - node.kind === 'unknown' for 47 of 794 entries. Those say the portal states
     no marker; rural is never asserted for them.
   - node.pdfs are repo-relative local paths, NOT web-servable from landing/.
     The document is named; no link is emitted, because it would 404.

   COLOURS
   Composed only from the existing tokens and library classes. This file
   defines no colour literals and no inline colour styles.
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
  function esc(s) { return DASH.esc(s); }

  /* ------------------------------------------------------------- breadcrumb */

  function breadcrumb(node) {
    var bits = (Array.isArray(node.breadcrumb) ? node.breadcrumb : [])
      .filter(function (b) { return b && txt(b.name); })
      .map(function (b) {
        var lvl = txt(b.level);
        var suffix = lvl === 'district' ? ' district'
          : lvl === 'constituency' ? ' constituency'
          : lvl === 'mandal' ? ' mandal' : '';
        return esc(txt(b.name) + suffix);
      });
    if (!bits.length) return '';
    return '<p class="d-drill-lbl">' + bits.join(' &rsaquo; ') + '</p>';
  }

  /* --------------------------------------------------------- what we can say

     node.kind is the portal's own -R/-U marker, never guessed. 'unknown' means
     the portal published no marker, and this template must not fill that in. */

  function kindLine(node) {
    var kind = txt(node.kind);
    var why = txt(node.why);
    var lead;

    if (kind === 'rural') {
      lead = 'The AP constituencies portal marks this mandal <strong>rural</strong>.';
    } else if (kind === 'urban') {
      lead = 'The AP constituencies portal marks this mandal <strong>urban</strong>, ' +
        'though it is laid out here with the rural template.';
    } else {
      lead = 'The AP constituencies portal publishes <strong>no rural or urban marker' +
        '</strong> for this mandal, so none is asserted here.';
    }
    /* node.why for an unmarked mandal reads 'shown as rural by default' — that is
       the classifier's own note and would contradict the sentence above it, so it is
       carried only where the portal actually stated a marker. */
    var showWhy = why && kind !== 'unknown';
    return '<p>' + lead + (showWhy ? ' <small>(' + esc(why) + ')</small>' : '') + '</p>';
  }

  function scopeNote(node) {
    var name = txt(node.name);
    var cons = txt(node.inherited_from) || txt(node.constituency);
    var sibs = Array.isArray(node.siblings) ? node.siblings.length : 0;
    var within = sibs > 0 && cons
      ? ' It is one of <strong>' + (sibs + 1) + '</strong> mandals in ' + esc(cons) + '.'
      : '';

    var body = kindLine(node);

    /* has_own_figures is always false and is in the contract precisely so that a
       template acknowledges the situation rather than quietly assuming otherwise. */
    if (node.has_own_figures === false) {
      body += '<p><strong>Mandal figures are not yet loaded into this dashboard.</strong> ' +
        'The mandal vision documents do publish them \u2014 GVA by sector, population, ' +
        'literacy, land use and more \u2014 but those figures have not been extracted ' +
        'from the PDFs into this dashboard yet.' + within + '</p>';
      body += '<p>Everything numeric below therefore describes ' +
        (cons ? esc(cons) + ' constituency' : 'the parent constituency') +
        ' as a whole &mdash; not ' + (name ? esc(name) : 'this mandal') +
        ', and not this mandal&rsquo;s share of it.</p>';
    } else {
      /* Defensive: the contract fixes this to false. If it ever changes, say
         nothing rather than assert either way. */
      body += '<p>The coverage of figures for this mandal is not stated in the record.</p>';
    }

    return DASH.narrative(body);
  }

  /* --------------------------------------------- inherited constituency block

     Every inherited figure lives in THIS section and nowhere else, and both the
     section title and every card label name node.inherited_from. That is what
     keeps a constituency figure from ever reading as the mandal's own. */

  function inheritedStats(node, cons) {
    var inh = node.inherited;
    var by = txt(inh.year_baseline);
    var ty = txt(inh.year_target);
    var cards = [];

    cards.push(DASH.statCard({
      label: cons + ' constituency — GCDP baseline',
      value: DASH.fmtCr(inh.gcdp_baseline) || null,
      sub: by + ' — measured, whole constituency'
    }));

    cards.push(DASH.statCard({
      label: cons + ' constituency — GCDP target',
      value: DASH.fmtCr(inh.gcdp_target) || null,
      sub: ty + ' — a plan, not an outturn'
    }));

    if (n(inh.cagr) !== null) {
      cards.push(DASH.statCard({
        label: cons + ' constituency — planned CAGR',
        value: DASH.fmtPct(inh.cagr),
        sub: by + ' to ' + ty + ', as published'
      }));
    }

    var row = DASH.statRow(cards);
    if (!row) return '';
    return row + DASH.sourceNote(
      'Both figures belong to ' + cons + ' constituency, of which this mandal is one ' +
      'part. The baseline is measured and the target is the Vision 2029 plan; they are ' +
      'of different kinds, are not comparable as an outturn, and are not added together.'
    );
  }

  function inheritedShares(node, cons) {
    var sh = node.inherited.shares;
    if (!sh || typeof sh !== 'object') {
      return DASH.empty(
        'Sector shares are not published for ' + cons + ' constituency, and none ' +
        'exist at mandal level.'
      );
    }
    var items = [];
    SECTOR_ORDER.forEach(function (k) {
      var v = n(sh[k]);
      if (v === null) return;
      items.push({ name: SECTOR_LABEL[k], pct: v });
    });
    if (!items.length) {
      return DASH.empty(
        'Sector shares are not published for ' + cons + ' constituency, and none ' +
        'exist at mandal level.'
      );
    }
    /* library default scale:'share' — the track is 100%, so bar width IS the
       published percentage. Do not pass 'relative' under a share caption. */
    return DASH.compositionBars({ items: items }) + DASH.sourceNote(
      'Share of ' + cons + ' constituency GCDP, ' +
      txt(node.inherited.year_baseline) +
      '. The split within this mandal is not published and is not implied by these bars.'
    );
  }

  function inheritedSection(node) {
    var cons = txt(node.inherited_from);
    var inh = node.inherited;

    if (!inh || !cons) {
      var named = txt(node.constituency);
      return DASH.section({
        title: 'The economy this mandal sits inside',
        body: DASH.empty(
          named
            ? 'The record for ' + named + ' constituency was not attached, so no ' +
              'economic context can be shown. No figures exist at mandal level.'
            : 'No parent constituency was attached to this mandal, so there are no ' +
              'figures to show. None exist at mandal level.'
        )
      });
    }

    var body = inheritedStats(node, cons);
    body += inheritedShares(node, cons);

    var thrust = Array.isArray(inh.thrust) ? inh.thrust : [];
    if (thrust.length) {
      body += '<p class="d-drill-lbl">Thrust sectors named for ' + esc(cons) +
        ' constituency in the Vision 2029 plan</p>' + DASH.thrustChips(thrust);
    }

    return DASH.section({
      title: cons + ' constituency — the economy this mandal sits inside',
      note: 'Every figure in this section is ' + cons + '’s, not this mandal’s',
      body: body,
      wide: true
    });
  }

  /* ---------------------------------------------------------------- siblings */

  function siblingSection(node) {
    var sibs = Array.isArray(node.siblings) ? node.siblings.filter(function (s) {
      return txt(s);
    }) : [];
    var cons = txt(node.inherited_from) || txt(node.constituency);

    return DASH.section({
      title: 'The rest of the constituency',
      note: sibs.length
        ? sibs.length + ' other mandal' + (sibs.length === 1 ? '' : 's') +
          (cons ? ' in ' + cons : '')
        : null,
      body: DASH.drillList({
        items: sibs,
        label: cons
          ? 'Other mandals in ' + cons + ' constituency'
          : 'Other mandals in the same constituency',
        onpick: 'DASH_PICK_MANDAL',
        emptyReason: cons
          ? 'No other mandals are listed for ' + cons + ' constituency.'
          : 'No sibling mandals are listed for this mandal.'
      })
    });
  }

  /* ------------------------------------------------------------- vision docs

     node.pdfs are repo-relative paths to local files. They are NOT served from
     landing/, so no link is emitted — a link here would 404. The document is
     named so a reader knows it exists and can ask for it. */

  function docSection(node) {
    var pdfs = Array.isArray(node.pdfs) ? node.pdfs.filter(function (p) {
      return txt(p);
    }) : [];

    if (!node.has_pdf || !pdfs.length) {
      return DASH.section({
        title: 'Mandal vision document',
        body: DASH.empty(
          'No mandal vision document has been collected for this mandal. ' +
          'Where one exists it carries the mandal\u2019s own GVA, demographic and ' +
          'land-use tables.'
        )
      });
    }

    var names = pdfs.map(function (p) {
      var base = txt(p).split('/').pop().replace(/\.pdf$/i, '').replace(/[_-]+/g, ' ');
      return '<li>' + esc(base) + '</li>';
    }).join('');

    return DASH.section({
      title: 'Mandal vision document',
      note: pdfs.length + ' document' + (pdfs.length === 1 ? '' : 's') + ' on file',
      body: DASH.narrative(
        '<p>' + (pdfs.length === 1 ? 'A vision and action plan exists' :
          'Vision and action plans exist') + ' for this mandal:</p>' +
        '<ul>' + names + '</ul>' +
        '<p>' + (pdfs.length === 1 ? 'It is' : 'They are') + ' held in the project ' +
        'corpus as ' + (pdfs.length === 1 ? 'a PDF' : 'PDFs') + ' and ' +
        (pdfs.length === 1 ? 'is' : 'are') + ' not published from this site, so no ' +
        'link is given here. ' + (pdfs.length === 1 ? 'It carries' : 'They carry') +
        ' this mandal&rsquo;s own GVA, demographic and land-use tables, which are ' +
        'not yet extracted into this dashboard.</p>'
      )
    });
  }

  /* ------------------------------------------------------------------- main */

  global.DASH_TPL.M1 = function (node) {
    if (!node || typeof node !== 'object') {
      return DASH.empty('No mandal record was supplied.');
    }

    var name = txt(node.name);
    var district = txt(node.district).replace(/_/g, ' ');
    var cons = txt(node.constituency);
    var out = '<div class="dash dash-m1">';

    var noteBits = [];
    if (district) noteBits.push(district + ' district');
    if (cons) noteBits.push(cons + ' constituency');

    /* "X mandal in Y constituency of Z district", with the mandal's GMDP rank
       among its constituency siblings pinned right when the figures exist. */
    var of = [];
    if (cons) of.push({ kind: 'constituency', name: cons, joiner: 'in' });
    if (district) of.push({ kind: 'district', name: district, joiner: 'of' });
    var mRank = (node.own && node.own.rank !== null && node.own.rank_total !== null)
      ? DASH.rankBadge({ rank: node.own.rank, total: node.own.rank_total,
          basis: 'GDDP in ' + cons }) : '';
    out += DASH.section({
      titleHtml: DASH.placeCrumb(name || 'Mandal', 'mandal', of),
      body: breadcrumb(node) + scopeNote(node),
      aside: mRank,
      wide: true
    });

    out += DASH.mandalOwnSection(node);
    out += inheritedSection(node);
    out += siblingSection(node);
    out += docSection(node);

    out += DASH.sourceNote(
      (txt(node.source) ||
        'AP Assembly Constituencies portal (mandal roster) · mandal vision documents') +
      (node.has_own_figures
        ? ' Mandal GVA figures are from this mandal’s own vision-document statement; ' +
          'any figure labelled “constituency” is inherited and marked as such.'
        : ' No GVA table could be extracted for this mandal, so the figures above are ' +
          'the parent constituency’s, each labelled as one.')
    );
    return out + '</div>';
  };
})(typeof window !== 'undefined' ? window : this);
