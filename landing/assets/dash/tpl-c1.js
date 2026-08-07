/* ===========================================================================
   Swarna Andhra — C1 template: Urban / Services-led constituency
   (services-dominant; 32 of 175 constituencies)

   INPUT: the ENRICHED NODE and nothing else. Its contract is the header of
   landing/assets/dash/enrich.js; the allowed key list is DASH.ENRICHED_KEYS.
   Every key is always present, every value may be null / [] / ''.
   This function is synchronous and never fetches.

   Archetype thesis: services dominate. Agriculture is often under 1% of GCDP
   and must not occupy a third of the page — it is stated as one figure, not
   drawn as a bar that would normalise itself to full width.

   Honesty: nothing is derived that the source did not publish. Density comes
   precomputed on the node and is labelled as a ratio. Population provenance is
   whatever node.population_note states — 10 of 175 records state none, and for
   those no source is asserted. Baseline is measured, target is a plan; they are
   labelled separately and never summed.
   =========================================================================== */
(function (global) {
  'use strict';

  var D = global.DASH;
  if (!D) return;

  global.DASH_TPL = global.DASH_TPL || {};

  function arr(v) {
    return Object.prototype.toString.call(v) === '[object Array]' ? v : [];
  }

  function isServices(name, code) {
    return /^SERVICE/i.test(String(code || '')) || /serv/i.test(String(name || ''));
  }

  /* Growth rows for the bullet chart.
     Preferred: node.growth — PER-SECTOR ONLY (enrich.js has already stripped the
     whole-economy TOTAL row), Service Sector hoisted to the top because that is
     the thesis of this archetype.
     Fallback: the one row we can honestly state from the bare index record — the
     whole-constituency GCDP baseline against its 2028-29 target. Sector
     baselines are NEVER manufactured by multiplying GCDP by a share. */
  function growthRows(node) {
    var src = arr(node.growth).filter(function (r) {
      return r && r.name && (D.num(r.baseline) !== null || D.num(r.target) !== null);
    });

    if (src.length) {
      return src.map(function (r) {
        return {
          name: r.name,
          baseline: r.baseline,
          target: r.target,
          cagr: r.cagr,
          colorHex: r.colorHex        // portal's own colour, '' falls back in the library
        };
      }).sort(function (a, b) {
        return (isServices(a.name) ? 0 : 1) - (isServices(b.name) ? 0 : 1);
      });
    }

    var base = D.num(node.gcdp_baseline);
    var tgt = D.num(node.gcdp_target);
    if (base === null && tgt === null) return [];
    return [{
      name: 'Constituency GCDP (all sectors)',
      baseline: base,
      target: tgt,
      cagr: D.num(node.cagr)
      /* No colorHex: a whole-economy total must not borrow a sector's encoding.
         growthBullet falls back to var(--green). */
    }];
  }

  global.DASH_TPL.C1 = function (node) {
    node = node || {};

    var name = node.name ? String(node.name) : '';
    var BY = node.year_baseline || '2023-24';
    var TY = node.year_target || '2028-29';

    var shares = node.shares || {};
    var pop = D.num(node.population);
    var area = D.num(node.area_sqkm);
    var density = D.num(node.density);
    var base = D.num(node.gcdp_baseline);
    var cagr = D.num(node.cagr);
    var agri = D.num(shares.agri);
    var svc = D.num(shares.services);
    var popNote = node.population_note ? String(node.population_note) : '';

    var out = '<div class="dash dash-c1" data-archetype="C1">';

    /* ---- 0. identity strip -------------------------------------------- */
    var ident = '';
    if (name) {
      ident += '<h3 class="d-sec-h" style="border:0;margin:0;padding:0">' +
        '<span style="font-size:1.05rem;font-weight:800;letter-spacing:-.02em">' +
        D.esc(name) + '</span></h3>';
    }
    var sub = [];
    if (node.district) sub.push('District: ' + node.district);
    sub.push('Urban / services-led constituency');
    if (node.why) sub.push(String(node.why));
    ident += '<p class="d-src" style="margin-top:6px">' + D.esc(sub.join(' · ')) + '</p>';
    out += D.section({ body: ident });

    /* ---- 1. headline figures ------------------------------------------ */
    var cards = [
      D.statCard({
        label: 'GCDP baseline',
        value: base !== null ? D.fmtCr(base) : null,
        sub: BY + ' — measured'
      }),
      D.statCard({
        label: 'CAGR to ' + TY,
        value: cagr !== null ? D.fmtPct(cagr) + ' a year' : null,
        /* The portal publishes this figure; it is not derived here. */
        sub: 'As published, GCDP ' + BY + ' to ' + TY
      }),
      D.statCard({
        label: 'Population',
        value: pop !== null ? D.grp(Math.round(pop)) : null,
        /* Provenance only when the record carries it. Never assumed. */
        sub: popNote || ''
      }),
      D.statCard({
        label: 'Density',
        value: density !== null ? D.grp(density) + ' / km²' : null,
        sub: area !== null
          ? 'Population / area ' + D.grp(Math.round(area * 10) / 10) + ' km²'
          : 'Area not published'
      })
    ];
    out += D.section({
      title: 'The place in four figures',
      note: 'Mixed vintages — each figure is labelled',
      body: D.statRow(cards)
    });

    /* ---- 2. what the economy is made of ------------------------------- */
    var donut = D.sectorDonut({
      shares: shares,
      emphasis: 'services',
      colors: node.share_colors || {},   // portal colours when attached; library fallback otherwise
      title: (name || 'This constituency') + ' — sector shares of GCDP',
      centerLabel: 'services'
    });

    /* Agriculture as one stated figure, not a bar. A single-item
       compositionBars is a full-width bar whatever the value — 0.3% would read
       as the whole economy. */
    var agriRow = agri !== null
      ? '<div style="margin-top:14px">' + D.statCard({
          label: 'Agriculture & allied',
          value: D.fmtPct(agri),
          sub: 'share of GCDP, ' + BY
        }) + '</div>'
      : '';

    var svcLine = svc !== null
      ? '<p class="d-src">Services account for ' + D.esc(D.fmtPct(svc)) +
        ' of output; the layout on this page follows that fact.</p>'
      : '';

    out += D.section({
      title: 'A services economy',
      note: 'Shares of GCDP, ' + BY,
      body: donut + agriRow + svcLine
    });

    /* ---- 3. baseline against the plan --------------------------------- */
    var rows = growthRows(node);
    out += D.section({
      title: 'Baseline against the ' + TY + ' plan',
      note: 'Baseline ' + BY + ' measured · target ' + TY + ' planned — never summed',
      body: rows.length
        ? D.growthBullet({ rows: rows, emphasis: 'service', baselineYear: BY, targetYear: TY })
        : D.empty('No GCDP baseline or target is published for this constituency.')
    });

    /* ---- 4. where it sits in its district ------------------------------ */
    var peers = arr(node.peers).map(function (p) {
      return { name: p && p.name ? String(p.name) : '', value: D.num(p && p.gcdp_baseline) };
    }).filter(function (p) { return p.name && p.value !== null; });
    if (peers.length >= 2 && node.district) {
      out += D.section({
        title: 'Within ' + String(node.district) + ' district',
        note: 'GCDP baseline ' + BY + ', ₹ crore — measured',
        body: D.rankStrip({
          label: 'Constituencies in this district, by GCDP baseline',
          selfName: name,
          value: base,
          peers: peers,
          unit: 'cr'
        })
      });
    }

    /* ---- 5. thrust sectors --------------------------------------------- */
    if (arr(node.thrust).length) {
      out += D.section({
        title: 'Declared thrust sectors',
        note: 'Swarna Andhra Vision 2029',
        body: D.thrustChips(node.thrust)
      });
    }
    /* No thrust list: the section is dropped rather than shown empty. */

    /* ---- 6. narrative --------------------------------------------------- */
    if (node.profile_html) {
      out += D.section({
        title: 'Constituency profile',
        note: 'AP Assembly Constituencies portal',
        body: D.narrative(node.profile_html)
      });
    }
    if (node.economy_html) {
      out += D.section({
        title: 'The economy in words',
        note: 'AP Assembly Constituencies portal',
        body: D.narrative(node.economy_html)
      });
    }

    /* ---- 7. drill down --------------------------------------------------- */
    var mandals = arr(node.mandals);
    out += D.section({
      title: 'Mandals in this constituency',
      note: mandals.length ? mandals.length + ' mandals' : '',
      body: D.drillList({
        items: mandals,
        /* the page defines DASH_PICK_MANDAL; drillList guards the call site, so
           an unwired page degrades to a plain list rather than throwing */
        onpick: 'DASH_PICK_MANDAL',
        emptyReason: 'No mandal list is published for this constituency.'
      })
    });

    /* ---- 8. provenance ---------------------------------------------------- */
    out += D.sourceNote(node.source
      ? 'Source: ' + node.source + '. GCDP baseline ' + BY + ' measured; target ' +
        TY + ' is the Swarna Andhra Vision 2029 plan, not an outturn.'
      : D.SOURCE_APC);

    return out + '</div>';
  };
})(typeof window !== 'undefined' ? window : this);
