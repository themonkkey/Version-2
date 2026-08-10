/* ===========================================================================
   Swarna Andhra — M2 template: Urban / municipal mandal
   (121 of the mandal roster carry the portal's -U marker)

   INPUT: the ENRICHED MANDAL NODE and nothing else. Its contract is the
   comment block above enrichMandal() in landing/assets/dash/enrich.js; the
   allowed key list is DASH.MANDAL_KEYS. This function is synchronous and
   never fetches.

   THE CONSTRAINT THAT SHAPES THIS PAGE
   No structured figures exist at mandal level anywhere in the corpus. The
   NOT-YET-EXTRACTED, NOT NON-EXISTENT. An earlier version of this file claimed
   no mandal figures existed anywhere. That was wrong: the mandal vision PDFs
   carry GVA by broad sector and sub-sector, population, literacy, land holdings,
   land use, crops, irrigation and more, in extractable tables. They simply have
   not been parsed into this site yet. node.has_own_figures stays false until an
   extractor lands; do not word anything as though the data does not exist.
   Every number this page can show is INHERITED from the parent constituency
   and describes THE CONSTITUENCY — a mandal is one of typically 3-6 inside
   it, so a constituency figure is not this mandal's share of anything.

   Consequently every inherited figure rendered here carries the parent's
   name, from node.inherited_from, inside its own label, caption or centre
   text — not merely in a distant section heading. A reader who screenshots
   one card still sees whose figure it is.

   An urban mandal is exactly where a reader most expects municipal detail —
   ward counts, civic assets, town budgets — and we have none of it. So the
   page states the boundary explicitly and early rather than padding itself
   with borrowed numbers until it resembles the district and constituency
   pages. A shorter honest page beats a fuller misleading one.

   No colour literals; every visual is a shared-library component, so the
   .vstage dark-stage overrides in components.css apply unchanged.
   =========================================================================== */
(function (global) {
  'use strict';

  var D = global.DASH;
  if (!D) return;

  global.DASH_TPL = global.DASH_TPL || {};

  function arr(v) {
    return Object.prototype.toString.call(v) === '[object Array]' ? v : [];
  }
  function txt(v) {
    return typeof v === 'string' ? v.trim() : (v === 0 ? '0' : '');
  }
  /* basename of a repo-relative path, for naming a document we cannot link to */
  function baseName(p) {
    var s = String(p || '');
    var i = s.lastIndexOf('/');
    return i > -1 ? s.slice(i + 1) : s;
  }

  /* Author-written copy, as paragraphs. DASH.narrative() is for SOURCE prose:
     its sanitiser falls back to escaping the whole string when no DOM is
     present, so passing our own markup through it would render tags as text
     off-DOM. Copy written here is emitted directly instead, with every dynamic
     fragment escaped at the point it is interpolated. Class is the library's
     own .d-narr, so the dark-stage rules still apply. */
  function prose(paras) {
    var body = paras.filter(Boolean).map(function (t) {
      return '<p>' + t + '</p>';
    }).join('');
    return body ? '<div class="d-narr">' + body + '</div>' : '';
  }

  /* ------------------------------------------------------------ identity ---
     The -U marker is the portal's own, so urban status may be ASSERTED here —
     but only when it is actually present. If a record reaches M2 with kind
     'unknown' (the 47 unmarked entries are never guessed) the page says the
     marker is absent instead of claiming a town. */
  function identity(node) {
    var crumbs = arr(node.breadcrumb).map(function (b) {
      return b && b.name ? String(b.name) : '';
    }).filter(Boolean);

    var out = '';
    if (crumbs.length > 1) {
      out += '<p class="d-drill-lbl">' + D.esc(crumbs.join('  ›  ')) + '</p>';
    }

    var line = [];
    if (node.kind === 'urban') {
      line.push('The AP portal marks this mandal urban (-U): a town or municipal area.');
    } else if (node.kind === 'unknown') {
      line.push('The portal carries no rural/urban marker for this mandal, so neither is asserted here.');
    } else {
      line.push('Mandal record.');
    }
    /* node.why for an M2 record restates the -U marker almost word for word.
       Printing both reads as a stutter, so it is shown only when it adds
       something the sentence above does not already say. */
    var why = txt(node.why);
    if (why && !/marks this mandal urban/i.test(why)) line.push(why + '.');
    out += D.sourceNote(line.join(' '));
    return out;
  }

  /* ------------------------------------------------- the boundary notice ---
     node.has_own_figures is in the contract precisely so a template must
     acknowledge the situation rather than quietly assume otherwise. */
  function boundary(node) {
    var from = txt(node.inherited_from);
    var sibs = arr(node.siblings).filter(function (s) { return txt(s); });
    var total = sibs.length + 1;

    /* The contract fixes has_own_figures at false. It is read rather than
       assumed, so that if a mandal-level source ever lands, this page states
       the change instead of silently continuing to deny it. */
    if (node.has_own_figures) {
      return prose(['This mandal now carries figures of its own. This template ' +
        'predates that source and does not yet render them.']);
    }

    var p = ['Mandal-level figures are not yet loaded into this dashboard. The ' +
      'mandal vision documents do publish them \u2014 GVA by broad sector and ' +
      'sub-sector, population, literacy, land use and more \u2014 but those tables ' +
      'have not been extracted from the PDFs into this site yet.'];

    if (from) {
      p.push('What follows is ' + D.esc(from) + ' constituency context. Those ' +
        'figures describe the whole constituency' +
        (sibs.length ? ', of which this mandal is one of ' + total + ' mandals' : '') +
        '. They are not this mandal\u2019s figures and not its share of anything.');
    } else {
      p.push('No parent constituency record was attached to this mandal, so ' +
        'not even inherited context can be shown.');
    }
    return prose(p);
  }

  /* ---------------------------------------------------- inherited figures ---
     Each card names the constituency in its own label. Baseline is measured,
     target is a plan; they are labelled separately and never summed. */
  function inheritedStats(node) {
    var inh = node.inherited;
    var from = txt(node.inherited_from);
    if (!inh || !from) {
      return D.empty('No parent constituency figures are attached to this mandal, ' +
        'and no figures are published at mandal level.');
    }

    var by = txt(inh.year_baseline);
    var ty = txt(inh.year_target);
    var base = D.num(inh.gcdp_baseline);
    var tgt = D.num(inh.gcdp_target);
    var cagr = D.num(inh.cagr);
    /* the LARGEST sector, read from the data — not services. Services leads in
       only 56 of the 121 urban mandals' parent constituencies; Pedana is 77.75%
       agriculture. Urban status is a fact about this mandal and says nothing
       about which sector leads the constituency around it. */
    var SECTOR_LABEL = { agri: 'agriculture', industry: 'industry', services: 'services' };
    var leadKey = null, leadVal = null;
    ['agri', 'industry', 'services'].forEach(function (k) {
      var v = D.num((inh.shares || {})[k]);
      if (v !== null && (leadVal === null || v > leadVal)) { leadVal = v; leadKey = k; }
    });

    var cards = [];
    if (base !== null) {
      cards.push(D.statCard({
        label: from + ' constituency — GCDP baseline',
        value: D.fmtCr(base),
        sub: by + ' — measured, constituency-wide'
      }));
    }
    if (tgt !== null) {
      cards.push(D.statCard({
        label: from + ' constituency — GCDP target',
        value: D.fmtCr(tgt),
        sub: ty + ' — a plan, not an outturn'
      }));
    }
    if (cagr !== null) {
      cards.push(D.statCard({
        label: from + ' constituency — CAGR',
        value: D.fmtPct(cagr) + ' a year',
        sub: 'As published, ' + by + ' to ' + ty
      }));
    }
    if (leadVal !== null) {
      cards.push(D.statCard({
        label: from + ' constituency — largest sector',
        value: D.fmtPct(leadVal) + ' ' + SECTOR_LABEL[leadKey],
        sub: 'Share of constituency GCDP, ' + by
      }));
    }

    if (!cards.length) {
      return D.empty('The parent constituency record carries no published GCDP figures.');
    }
    return D.statRow(cards);
  }

  /* Sector shares of the PARENT. Services is emphasised because an urban
     mandal sits inside a services-weighted economy — but the emphasis is a
     reading aid, not a claim about this mandal's own composition, and the
     donut's centre text names the constituency. */
  function parentShares(node) {
    var inh = node.inherited;
    var from = txt(node.inherited_from);
    if (!inh || !from || !inh.shares) {
      return D.empty('Sector shares are not available for this mandal\u2019s parent constituency.');
    }
    /* Emphasise whichever sector actually leads, read from the data. Hard-wiring
       services here was wrong: services is the largest share in only 56 of the 121
       urban mandals' parent constituencies. Pedana is 77.75% agriculture and 12.93%
       services, and highlighting services there asserted the opposite of the truth.
       Urban status is a fact about the mandal; it says nothing about which sector
       leads the constituency around it. */
    var lead = null, best = -1;
    ['agri', 'industry', 'services'].forEach(function (k) {
      var v = D.num(inh.shares[k]);
      if (v !== null && v > best) { best = v; lead = k; }
    });
    return D.sectorDonut({
      shares: inh.shares,
      emphasis: lead,
      title: from + ' constituency sector shares',
      /* name the constituency AND the level — the centre is the largest type in
         the figure, and "12.9% / of Pedana" read as this mandal's own number */
      centerLabel: 'of ' + from + ' constituency'
    });
  }

  /* One honest row: the whole-constituency baseline against its target.
     Sector baselines are never manufactured by multiplying GCDP by a share,
     and nothing here is apportioned down to the mandal. */
  function parentGrowth(node) {
    var inh = node.inherited;
    var from = txt(node.inherited_from);
    if (!inh || !from) return '';
    var base = D.num(inh.gcdp_baseline);
    var tgt = D.num(inh.gcdp_target);
    if (base === null && tgt === null) return '';

    return D.growthBullet({
      rows: [{
        name: from + ' constituency GCDP (all sectors)',
        baseline: base,
        target: tgt,
        cagr: D.num(inh.cagr)
        /* No colorHex: a whole-economy total must not borrow a sector's
           encoding. growthBullet falls back to var(--green). */
      }],
      baselineYear: txt(inh.year_baseline),
      targetYear: txt(inh.year_target)
    });
  }

  /* -------------------------------------------------------------- documents */
  function documents(node) {
    var pdfs = arr(node.pdfs).filter(function (p) { return txt(p); });
    if (!node.has_pdf || !pdfs.length) {
      return D.empty('No mandal vision document has been located for this mandal.');
    }
    /* These are repo-relative files, not web-servable from the landing site.
       Naming them is honest; linking them would 404. */
    var items = pdfs.map(function (p) {
      return { name: baseName(p), sub: 'PDF' };
    });
    return D.drillList({
      items: items,
      label: pdfs.length === 1
        ? 'One vision document exists for this mandal, holding its GVA, demographic and land-use tables. It is not yet extracted into this dashboard.'
        : pdfs.length + ' vision documents exist for this mandal, holding its GVA, demographic and land-use tables. They are not yet extracted into this dashboard.'
    }) + D.sourceNote('Held in the project corpus, not published on this site, ' +
      'so no link is offered here.');
  }

  /* ------------------------------------------------------------------ main */

  global.DASH_TPL.M2 = function (node) {
    if (!node || typeof node !== 'object') {
      return D.empty('No mandal record was supplied.');
    }

    var name = txt(node.name);
    var from = txt(node.inherited_from);
    var cons = txt(node.constituency);
    var district = txt(node.district).replace(/_/g, ' ');
    var sibs = arr(node.siblings).filter(function (s) { return txt(s); });

    var out = '<div class="dash dash-m2" data-archetype="M2">';

    /* 1. identity */
    var noteBits = [];
    if (cons) noteBits.push(cons + ' constituency');
    if (district) noteBits.push(district + ' district');
    var of = [];
    if (cons) of.push({ kind: 'constituency', name: cons, joiner: 'in' });
    if (district) of.push({ kind: 'district', name: district, joiner: 'of' });
    var mRank = (node.own && node.own.rank !== null && node.own.rank_total !== null)
      ? D.rankBadge({ rank: node.own.rank, total: node.own.rank_total,
          basis: 'GDDP in ' + cons }) : '';
    out += D.section({
      titleHtml: D.placeCrumb(name || 'Mandal', node.kind === 'urban' ? 'urban mandal' : 'mandal', of),
      aside: mRank,
      body: identity(node)
    });

    /* the mandal's own extracted economics, when a GVA table was found */
    out += D.mandalOwnSection(node);

    /* what this page can and cannot show — only meaningful when there are NO own
       figures; with own figures present the distinction is already made above */
    if (!node.has_own_figures) {
      out += D.section({
        title: 'What this page can and cannot show',
        note: 'Read this before the figures below',
        body: boundary(node)
      });
    }

    /* 3-5. parent constituency context, only when a parent is attached */
    if (from) {
      out += D.section({
        title: from + ' constituency — headline figures',
        note: 'Constituency-wide, not this mandal',
        body: inheritedStats(node) +
          D.sourceNote('Every figure in this section belongs to ' + from +
            ' constituency as a whole. None of it is apportioned to ' +
            (name || 'this mandal') + ', and no such apportionment is published.')
      });

      out += D.section({
        title: 'What the ' + from + ' economy is made of',
        note: 'Share of ' + from + ' constituency GCDP',
        body: parentShares(node) +
          D.sourceNote('The largest sector is highlighted, read from the data — urban ' +
            'status describes this mandal, not which sector leads the constituency ' +
            'around it. The split shown is ' + from +
            ' constituency\u2019s, not this mandal\u2019s — no mandal-level split exists.')
      });

      var growth = parentGrowth(node);
      if (growth) {
        out += D.section({
          title: 'Baseline and target for ' + from,
          note: 'Constituency-wide; baseline measured, target planned',
          wide: true,
          body: growth
        });
      }

      var thrust = arr(node.inherited && node.inherited.thrust);
      if (thrust.length) {
        out += D.section({
          title: 'Thrust sectors named for ' + from,
          note: 'From the constituency plan; no mandal-level thrust list is published',
          body: D.thrustChips(thrust)
        });
      }
    }

    /* 6. siblings */
    out += D.section({
      title: 'Other mandals in ' + (cons || 'this constituency'),
      note: sibs.length ? sibs.length + ' others' : null,
      body: D.drillList({
        items: sibs,
        label: from
          ? 'The ' + from + ' figures above cover these mandals together with ' +
            (name || 'this one') + '.'
          : 'Mandals sharing this constituency. No figures are published for any of them.',
        emptyReason: 'No other mandals are listed for this constituency.'
      })
    });

    /* 7. vision document */
    out += D.section({
      title: 'Mandal vision document',
      body: documents(node)
    });

    out += D.sourceNote(txt(node.source) ||
      'AP Assembly Constituencies portal (mandal roster) · mandal vision documents');
    return out + '</div>';
  };
})(typeof window !== 'undefined' ? window : this);
