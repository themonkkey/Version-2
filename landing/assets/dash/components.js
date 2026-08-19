/* ===========================================================================
   Swarna Andhra — dashboard shared component library
   Plain script. Defines window.DASH. Every builder returns an HTML STRING.

   Honesty contract enforced here, not left to callers:
     - no builder invents a number; missing input yields DASH.empty(reason)
     - baseline (measured) and target (planned) render differently and are
       never summed
     - portal prose is sanitised, portal text is escaped
   =========================================================================== */
(function (global) {
  'use strict';

  /* ---------------------------------------------------------------- utils */

  function esc(s) {
    if (s === null || s === undefined) return '';
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function isNum(n) {
    return typeof n === 'number' && isFinite(n);
  }

  /* Coerce portal values that arrive as numeric strings ("419.61"). */
  function num(v) {
    if (isNum(v)) return v;
    if (typeof v === 'string') {
      var c = v.replace(/,/g, '').trim();
      if (c !== '' && isFinite(Number(c))) return Number(c);
    }
    return null;
  }

  function grp(n) {
    // Indian digit grouping: 12,34,567
    var s = String(n);
    var neg = s.charAt(0) === '-';
    if (neg) s = s.slice(1);
    var parts = s.split('.');
    var i = parts[0];
    var out;
    if (i.length <= 3) {
      out = i;
    } else {
      var last3 = i.slice(-3);
      var rest = i.slice(0, -3);
      out = rest.replace(/\B(?=(\d{2})+(?!\d))/g, ',') + ',' + last3;
    }
    if (parts[1]) out += '.' + parts[1];
    return (neg ? '-' : '') + out;
  }

  function round(n, dp) {
    var f = Math.pow(10, dp || 0);
    return Math.round(n * f) / f;
  }

  /** Rupees-crore. fmtCr(3768) -> "₹3,768 cr". Returns '' when not a number. */
  function fmtCr(n) {
    var v = num(n);
    if (v === null) return '';
    var dp = Math.abs(v) < 100 ? 1 : 0;
    return '₹' + grp(round(v, dp)) + ' cr';
  }

  /** Plain rupees. */
  function fmtRs(n) {
    var v = num(n);
    if (v === null) return '';
    return '₹' + grp(round(v, 0));
  }

  /** Percent. fmtPct(46.43) -> "46.4%" */
  function fmtPct(n, dp) {
    var v = num(n);
    if (v === null) return '';
    return round(v, dp === undefined ? 1 : dp) + '%';
  }

  /* --------------------------------------------------------- sanitisation */

  var ALLOWED_TAGS = {
    P: 1, BR: 1, SPAN: 1, DIV: 1, STRONG: 1, B: 1, EM: 1, I: 1, U: 1,
    UL: 1, OL: 1, LI: 1, H1: 1, H2: 1, H3: 1, H4: 1, H5: 1, H6: 1,
    BLOCKQUOTE: 1, A: 1, SMALL: 1, SUB: 1, SUP: 1, HR: 1,
    TABLE: 1, THEAD: 1, TBODY: 1, TR: 1, TH: 1, TD: 1
  };
  var ALLOWED_ATTRS = { href: 1, title: 1, colspan: 1, rowspan: 1 };
  var DROP_WHOLE = { SCRIPT: 1, STYLE: 1, IFRAME: 1, OBJECT: 1, EMBED: 1, LINK: 1, META: 1, FORM: 1, INPUT: 1, BUTTON: 1, SVG: 1, MATH: 1, TEMPLATE: 1, NOSCRIPT: 1, IMG: 1, PICTURE: 1, SOURCE: 1,
    AUDIO: 1, VIDEO: 1, BASE: 1, TEXTAREA: 1, SELECT: 1, OPTION: 1, LABEL: 1 };

  /**
   * Strip everything not on the allow-list from portal-supplied HTML prose.
   * Removes script/style/iframe wholesale, drops every event-handler
   * attribute, and blocks javascript:/data: URLs.
   */
  function sanitise(html) {
    if (html === null || html === undefined) return '';
    var src = String(html);
    if (typeof document === 'undefined') return esc(src);

    // Parse into a <template>. Its contents live in an inert owner document
    // with no browsing context, so nothing loads and nothing executes — not
    // scripts, and not <img onerror>, which DOES fire in a plain detached div.
    // The clean-up therefore happens entirely inside tpl.content; only after
    // every dangerous node is gone do we adopt it into the live document.
    var tpl = document.createElement('template');
    tpl.innerHTML = src;
    var host = tpl.content;

    (function walk(node) {
      var kids = Array.prototype.slice.call(node.childNodes);
      for (var i = 0; i < kids.length; i++) {
        var el = kids[i];
        if (el.nodeType === 8) { node.removeChild(el); continue; }   // comment
        if (el.nodeType !== 1) continue;                              // text ok
        var tag = el.tagName;

        if (DROP_WHOLE[tag]) { node.removeChild(el); continue; }

        if (!ALLOWED_TAGS[tag]) {
          // Unknown tag: keep its text content, discard the element.
          while (el.firstChild) node.insertBefore(el.firstChild, el);
          node.removeChild(el);
          continue;
        }

        var attrs = Array.prototype.slice.call(el.attributes);
        for (var j = 0; j < attrs.length; j++) {
          var name = attrs[j].name.toLowerCase();
          var val = attrs[j].value;
          if (!ALLOWED_ATTRS[name] || /^on/.test(name)) {
            el.removeAttribute(attrs[j].name);
            continue;
          }
          if (name === 'href') {
            var u = val.replace(/[\s\u0000-\u001F]/g, '').toLowerCase();
            if (!/^(https?:|mailto:|tel:|#|\/)/.test(u)) {
              el.removeAttribute('href');
            } else {
              el.setAttribute('rel', 'noopener noreferrer');
              el.setAttribute('target', '_blank');
            }
          }
        }
        walk(el);
      }
    })(host);

    // Everything unsafe is gone; serialise via a wrapper (fragments have no
    // innerHTML of their own).
    var out = document.createElement('div');
    out.appendChild(host);
    return out.innerHTML;
  }

  /* Sector colours the portal supplies inline; reject anything else. */
  function hex(c, fallback) {
    if (typeof c === 'string' && /^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/.test(c.trim())) {
      return c.trim();
    }
    return fallback || 'var(--label-3)';
  }

  /* ------------------------------------------------------------ primitives */

  /** Explicit, calm "no data and why" state. */
  function empty(reason) {
    return '<div class="d-empty">' +
      '<span class="d-empty-k">No data</span>' +
      '<span class="d-empty-r">' + esc(reason || 'This figure is not available for this place.') + '</span>' +
      '</div>';
  }

  /** Titled wrapper. body is an html string.
      o.aside is optional right-aligned HTML for the header row (e.g. a rank
      badge). o.titleHtml, when set, is used verbatim instead of esc(o.title) —
      for a breadcrumb whose parent segments are styled; callers pass pre-escaped
      HTML only. */
  function section(o) {
    o = o || {};
    var body = typeof o.body === 'string' ? o.body : '';
    if (!body) return '';
    var head = '';
    if (o.title || o.titleHtml || o.aside) {
      var h4 = (o.title || o.titleHtml)
        ? '<h4>' + (o.titleHtml ? o.titleHtml : esc(o.title)) + '</h4>' : '';
      head = '<div class="d-sec-h">' + h4 +
        (o.note ? '<span class="d-sec-note">' + esc(o.note) + '</span>' : '') +
        (o.aside ? '<div class="d-sec-aside">' + o.aside + '</div>' : '') +
        '</div>';
    }
    // wide:true makes the section span both columns once .dash goes two-up.
    // Use it for anything with a time axis or a long list of names.
    var cls = 'd-sec' + (o.wide ? ' d-sec--wide' : '');
    return '<section class="' + cls + '">' + head + '<div class="d-sec-b">' + body + '</div></section>';
  }

  /* Rank of one member within a peer list by a numeric key, plus the count of
     members that actually carry that key. Used for a constituency's standing
     among its sibling constituencies in the same district. Returns {rank, total}
     or null when the self member has no value or fewer than two peers do. */
  function peerRank(peers, selfName, key) {
    // peer names are index keys (underscores); a template's node.name is the
    // display label (spaces). Normalise both so "Visakhapatnam East" matches
    // "Visakhapatnam_East".
    var norm = function (s) { return String(s || '').replace(/[\s_]+/g, ' ').trim().toLowerCase(); };
    var selfKey = norm(selfName);
    var vals = (peers || []).map(function (p) {
      return { key: norm(p && p.name), v: num(p && p[key]) };
    }).filter(function (p) { return p.key && p.v !== null; });
    if (vals.length < 2) return null;
    var hasSelf = vals.some(function (p) { return p.key === selfKey; });
    if (!hasSelf) return null;
    vals.sort(function (a, b) { return b.v - a.v; });          // 1 = largest
    var rank = 0;
    for (var i = 0; i < vals.length; i++) {
      if (vals[i].key === selfKey) { rank = i + 1; break; }
    }
    return { rank: rank, total: vals.length };
  }

  /* --------------------------------------------------------- place header */

  /* The breadcrumb title for a level's first section: the place, then where it
     sits. District has no parent, so it is just the name; a constituency reads
     "Bhimili, constituency of Visakhapatnam"; a mandal "Anaparthi, mandal in
     Anaparthi of East Godavari". Parents are dimmed so the place itself leads.
     `of` is an ordered array of {kind, name}, nearest parent first.
     Returns HTML (pre-escaped) for section({titleHtml}). */
  function placeCrumb(name, kind, of) {
    var out = '<span class="d-crumb-self">' + esc(name || '') + '</span>';
    if (kind) out += '<span class="d-crumb-kind">' + esc(kind) + '</span>';
    var parents = (of || []).filter(function (p) { return p && p.name; });
    if (parents.length) {
      var joiner = parents[0].joiner || 'of';
      var tail = parents.map(function (p, i) {
        var j = i === 0 ? joiner : (p.joiner || 'of');
        /* Parents are the only written record of where you are, so they are
           the natural way back up. Rendered as buttons rather than spans; the
           page owns the routing and listens for [data-crumb-up]. */
        return '<span class="d-crumb-j">' + esc(j) + '</span>' +
          '<button type="button" class="d-crumb-parent" data-crumb-up="' +
            esc(p.kind || '') + '" title="Back to ' + esc(p.name) + '">' +
            esc(p.name) + '</button>' +
          (p.kind ? ' <span class="d-crumb-pk">' + esc(p.kind) + '</span>' : '');
      }).join(' ');
      out += ' <span class="d-crumb-path">' + tail + '</span>';
    }
    return out;
  }

  /* Right-aligned rank badge for a header aside. The BASIS is mandatory: a bare
     "#3 of 28" is meaningless without saying ranked by what, and the ranking
     logic differs per level (districts by per-capita income statewide,
     constituencies by GCDP within their district). Returns '' when rank or total
     is missing, so a level with no rank simply shows no badge rather than a
     fabricated one. */
  function rankBadge(o) {
    o = o || {};
    var rank = num(o.rank), total = num(o.total);
    if (rank === null || total === null || total < 1) return '';
    return '<span class="d-rankbadge" role="img" aria-label="Ranked ' +
      esc(round(rank, 0) + ' of ' + round(total, 0) + ' by ' + (o.basis || 'this measure')) + '">' +
      '<span class="d-rb-pos"><span class="d-rb-hash">#</span>' + round(rank, 0) +
      '<span class="d-rb-of">of ' + round(total, 0) + '</span></span>' +
      (o.basis ? '<span class="d-rb-basis">' + esc(o.basis) + '</span>' : '') +
      '</span>';
  }

  /* --------------------------------------------------- compositionRibbon */

  /* Stacked area: how a district's economy is DIVIDED, and how that division has
     moved over four years.

     Why this and not the donut it replaces: a donut shows one year, so the reader
     sees a split but not a direction. The same data across four years says whether
     the district is industrialising or drifting to services -- which is the actual
     economic question. Visakhapatnam reads industry 33.4 -> 36.7 while services
     fall 63.1 -> 59.9; a single-year ring cannot show that.

     Colour: the three hues are validated (OKLab, dark + light surfaces) for the
     lightness band, chroma floor, CVD separation and contrast. Tritan separation
     sits at 7.1 -- inside the 6-8 floor band -- which is permitted ONLY with a
     secondary encoding, so every band is DIRECT-LABELLED. The labels are not
     decoration; remove them and the palette is no longer legal. The light surface
     also returns a contrast WARN, which the same labels answer.

     ribbon({series:{agri:[{label,pct}],industry:[...],services:[...]}}) */
  var RIBBON = [
    { key: 'agri', label: 'Agriculture', color: '#BF8A2B' },
    { key: 'industry', label: 'Industry', color: '#2B93BF' },
    { key: 'services', label: 'Services', color: '#6FA817' }
  ];

  function compositionRibbon(o) {
    o = o || {};
    var src = o.series || {};
    var rows = RIBBON.map(function (r) {
      var pts = (src[r.key] || []).map(function (p) {
        return { label: (p && (p.label || p.year)) || '', pct: num(p && (p.pct_of_district !== undefined ? p.pct_of_district : p.pct)) };
      }).filter(function (p) { return p.pct !== null; });
      return { def: r, pts: pts };
    }).filter(function (r) { return r.pts.length > 1; });

    if (rows.length < 2) {
      return empty(o.emptyReason || 'The sector split over time is not published for this district.');
    }

    var n = Math.min.apply(null, rows.map(function (r) { return r.pts.length; }));
    var W = 720, H = 240, L = 8, R = 132, T = 16, B = 30;   // R leaves room for labels
    var plotW = W - L - R, plotH = H - T - B;
    var x = function (i) { return L + (n === 1 ? plotW / 2 : (plotW * i) / (n - 1)); };
    var y = function (v) { return T + plotH - (plotH * v) / 100; };

    /* stack bottom-up, and keep a 2px surface gap between adjacent fills so the
       boundary is a real edge rather than two colours touching */
    var GAP = 2;
    var base = [], i;
    for (i = 0; i < n; i++) base.push(0);

    var bands = '', legend = '', labels = '';
    rows.forEach(function (r, ri) {
      var top = [], bot = [];
      for (i = 0; i < n; i++) {
        bot.push(base[i]);
        base[i] += r.pts[i].pct;
        top.push(base[i]);
      }
      var d = 'M' + x(0) + ',' + (y(top[0]) + (ri === rows.length - 1 ? 0 : GAP / 2));
      for (i = 1; i < n; i++) d += 'L' + x(i) + ',' + (y(top[i]) + (ri === rows.length - 1 ? 0 : GAP / 2));
      for (i = n - 1; i >= 0; i--) d += 'L' + x(i) + ',' + (y(bot[i]) - (ri === 0 ? 0 : GAP / 2));
      d += 'Z';
      bands += '<path d="' + d + '" fill="' + r.def.color + '" fill-opacity=".92"></path>';

      /* direct label at the latest year — required, see the colour note above */
      var last = r.pts[n - 1].pct, mid = (top[n - 1] + bot[n - 1]) / 2;
      labels += '<g transform="translate(' + (x(n - 1) + 10) + ',' + y(mid) + ')">' +
        '<rect x="0" y="-9" width="8" height="8" rx="2" fill="' + r.def.color + '"></rect>' +
        '<text x="13" y="-2" class="d-rb-lbl">' + esc(r.def.label) + '</text>' +
        '<text x="13" y="12" class="d-rb-val">' + fmtPct(last) + '</text></g>';

      legend += '<span class="d-rb-key"><i style="background:' + r.def.color + '"></i>' +
        esc(r.def.label) + '</span>';
    });

    /* recessive year axis */
    var axis = '';
    for (i = 0; i < n; i++) {
      axis += '<text x="' + x(i) + '" y="' + (H - 10) + '" class="d-rb-ax" ' +
        'text-anchor="' + (i === 0 ? 'start' : i === n - 1 ? 'end' : 'middle') + '">' +
        esc(rows[0].pts[i].label) + '</text>';
    }

    var first = rows.map(function (r) { return r.def.label + ' ' + fmtPct(r.pts[0].pct); }).join(', ');
    var lastAll = rows.map(function (r) { return r.def.label + ' ' + fmtPct(r.pts[n - 1].pct); }).join(', ');

    return '<figure class="d-ribbon">' +
      '<div class="d-rb-keys">' + legend + '</div>' +
      '<svg viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="xMidYMid meet" role="img" ' +
      'aria-label="Share of district output by sector group, ' + esc(rows[0].pts[0].label) +
      ' to ' + esc(rows[0].pts[n - 1].label) + '. ' + esc(first) + ' changing to ' + esc(lastAll) + '.">' +
      bands + labels + axis + '</svg></figure>';
  }

  /* ------------------------------------------------------------- muiChart */

  /* Emits a placeholder that mui-charts.js turns into a real MUI X chart after
     the panel paints. Templates stay plain string-builders and know nothing about
     React. If the bundle never loads the placeholder simply stays empty, so a
     chart is always additive -- never the reason a panel breaks.

     type: 'bar' | 'line' | 'pie' | 'spark'   props: the MUI component's props */
  function muiChart(type, props, o) {
    o = o || {};
    var spec = JSON.stringify({ type: type, props: props || {} });
    return '<div class="d-mui' + (o.className ? ' ' + esc(o.className) : '') + '"' +
      (o.height ? ' style="height:' + (+o.height) + 'px"' : '') +
      ' data-mui-chart="' + esc(spec) + '"' +
      (o.label ? ' role="img" aria-label="' + esc(o.label) + '"' : '') + '></div>';
  }

  /* A stat card's number says where a district is; the sparkline says which way it
     is going. Same footprint, and the series was already loaded. */
  function muiSpark(points, o) {
    o = o || {};
    var data = (points || []).map(function (p) {
      return num(p && (p.value !== undefined ? p.value : p));
    }).filter(function (v) { return v !== null; });
    if (data.length < 2) return '';

    /* A sparkline shows SHAPE, not magnitude. Left on MUI's default zero-based
       axis these series (GDDP 1.10L -> 1.61L crore) sit in the top sixth of the
       plot and the area fill swamps them into a solid block. Framing the axis on
       the data's own range, with a little padding, is what makes the trend
       legible -- and it is honest because the figures themselves are printed on
       the stat card directly above. */
    var lo = Math.min.apply(null, data), hi = Math.max.apply(null, data);
    var pad = (hi - lo) * 0.18 || Math.abs(hi * 0.05) || 1;

    return muiChart('spark', {
      data: data,
      height: o.height || 44,
      showHighlight: true,
      showTooltip: true,
      curve: 'linear',
      area: o.area !== false,
      color: o.color || '#6FA817',
      yAxis: { min: lo - pad, max: hi + pad },
      margin: { top: 4, bottom: 4, left: 0, right: 0 }
    }, { height: o.height || 44, label: o.label || '', className: 'd-mui-spark' });
  }

  /* The two-sparkline row that sits under a district's four stat cards. Factored
     out of tpl-d1 so d2/d3/d4 render it identically rather than four near-copies.
     Returns '' when neither series has enough points, so a caller can append it
     unconditionally. */
  function sparkRow(gddpSeries, pciSeries) {
    var sg = muiSpark(gddpSeries, { label: 'District GDDP trend', color: '#6FA817' });
    var sp = muiSpark(pciSeries, { label: 'Per-capita income trend', color: '#2B93BF' });
    if (!sg && !sp) return '';
    return '<div class="d-sparkrow">' +
      (sg ? '<div><span class="d-spark-l">District GDDP</span>' + sg + '</div>' : '') +
      (sp ? '<div><span class="d-spark-l">Per-capita income</span>' + sp + '</div>' : '') +
      '</div>';
  }

  /* ----------------------------------------------------- mandalOwnSection */

  /* Renders a mandal's OWN extracted economics — GMDP, per-capita, population,
     literacy, and its top sectors — from node.own (see enrichMandal). Returns ''
     when node.own is null, so an M template can append it unconditionally and a
     mandal with no extractable figures simply shows its inherited context and no
     own-figures block. Shared by M1/M2/M3 so the three render identically. */
  function mandalOwnSection(node) {
    var own = node && node.own;
    if (!own) return '';

    var ly = '2025-26 (FAE)';
    var cards = [
      statCard({ label: 'Mandal GDDP', value: own.gmdp !== null ? fmtCr(own.gmdp) : null,
        sub: 'Gross Mandal Domestic Product · ' + ly }),
      statCard({ label: 'Per-capita income', value: own.pci !== null ? fmtRs(own.pci) : null,
        sub: ly }),
      statCard({ label: 'Population', value: own.population !== null ? grp(round(own.population, 0)) + ' persons' : null,
        sub: 'Mandal GVA statement' })
    ];
    var dem = own.demographics || {};
    if (num(dem.literacy_total) !== null) {
      cards.push(statCard({ label: 'Literacy', value: fmtPct(dem.literacy_total),
        sub: (num(dem.literacy_female) !== null && num(dem.literacy_male) !== null)
          ? 'F ' + fmtPct(dem.literacy_female) + ' · M ' + fmtPct(dem.literacy_male) : 'Total' }));
    }

    var out = statRowInternal(cards);

    /* tri-sector split, aggregated from the sub-rows' broad grouping */
    var agg = { agri: 0, industry: 0, services: 0 }, any = false;
    (own.sectors || []).forEach(function (s) {
      if (s.broad && agg[s.broad] !== undefined && s.pct !== null) { agg[s.broad] += s.pct; any = true; }
    });

    /* top 3 sectors by share, as the same dot plot the districts use */
    var top = (own.sectors || []).filter(function (s) { return s.pct !== null && s.pct > 0; })
      .sort(function (a, b) { return b.pct - a.pct; }).slice(0, 3);
    if (top.length) {
      out += '<div style="margin-top:16px">' + sectorDots(top.map(function (s) {
        return { name: s.name, pct: s.pct };
      }), {}) + '</div>';
      out += '<p class="d-src">' + esc(
        'The three largest sectors by share of this mandal’s GVA, ' + ly + '. ' +
        (own.sectors || []).length + ' sectors are published; totals, taxes and subsidies ' +
        'are excluded so these do not double-count.') + '</p>';
    }
    if (any) {
      out += '<p class="d-src">' + esc('Broad split — agriculture & allied ' + fmtPct(agg.agri) +
        ', industry ' + fmtPct(agg.industry) + ', services ' + fmtPct(agg.services) + '.') + '</p>';
    }

    return section({
      title: 'This mandal’s own economy',
      note: 'From the mandal GVA statement — measured, not inherited from the constituency',
      aside: (own.rank !== null && own.rank_total !== null)
        ? rankBadge({ rank: own.rank, total: own.rank_total, basis: 'GDDP in ' + (node.constituency || 'constituency') })
        : '',
      body: out,
      wide: true
    });
  }

  /* statRow is exported below as an inline arrow; alias it here so builders above
     can call it before the export object is defined. */
  function statRowInternal(cards) {
    var s = (cards || []).filter(Boolean).join('');
    return s ? '<div class="d-stats">' + s + '</div>' : '';
  }

  function sourceNote(text) {
    if (!text) return '';
    return '<p class="d-src">' + esc(text) + '</p>';
  }

  function narrative(htmlString) {
    var clean = sanitise(htmlString);
    if (!clean.replace(/<[^>]*>/g, '').trim()) {
      return empty('No narrative text was published for this place.');
    }
    return '<div class="d-narr">' + clean + '</div>';
  }

  /* ------------------------------------------------------------- statCard */

  /**
   * statCard({label, value, sub, delta})
   * value may be a preformatted string or a number. If value is absent the
   * card is replaced by an empty state — never a placeholder figure.
   */
  function statCard(o) {
    o = o || {};
    var v = o.value;
    if (v === null || v === undefined || v === '' || (typeof v === 'number' && !isFinite(v))) {
      return empty((o.label ? esc(o.label) + ': ' : '') + 'figure not published.');
    }
    var down = typeof o.delta === 'string' && /^-|\bdown\b|\bfall/i.test(o.delta.trim());
    return '<div class="d-stat">' +
      (o.label ? '<span class="d-stat-l">' + esc(o.label) + '</span>' : '') +
      '<span class="d-stat-v">' + esc(v) + '</span>' +
      (o.sub ? '<span class="d-stat-s">' + esc(o.sub) + '</span>' : '') +
      (o.delta ? '<span class="d-stat-d' + (down ? ' is-down' : '') + '">' + esc(o.delta) + '</span>' : '') +
      '</div>';
  }

  /* ----------------------------------------------------------- sectorDonut */

  var SECTOR_LABEL = { agri: 'Agriculture & allied', industry: 'Industry', services: 'Services' };
  /* Portal-supplied sector colours (share_current[].colorHex). Used only as a
     fallback when the caller passes bare shares with no colours attached.
     These are the portal's own values, verified across all 175 harvested records —
     do not substitute look-alikes. #F5B400 in particular belongs to whole-economy
     GCDP, not to Industry, and an earlier draft shipped it here by mistake. */
  /* The validated trio, not the AP portal's #16A34A / #FF8A00 / #C93A2C, whose
     agri-vs-industry pair is ΔE 3.9 for protanopia — see sectorHue(). Keep the
     donut on the same hues as every other sector chart so a colour means one
     thing across the whole panel. */
  var SECTOR_COLOR = { agri: '#6FA817', industry: '#2B93BF', services: '#BF8A2B' };

  /**
   * sectorDonut({shares, emphasis, colors, title, centerLabel})
   * shares = {agri, industry, services} in percent.
   * emphasis = key to explode/highlight.
   */
  function sectorDonut(o) {
    o = o || {};
    var shares = o.shares || {};
    var colors = o.colors || {};
    var keys = ['agri', 'industry', 'services'].filter(function (k) {
      return num(shares[k]) !== null;
    });
    // allow arbitrary extra keys too
    Object.keys(shares).forEach(function (k) {
      if (keys.indexOf(k) === -1 && num(shares[k]) !== null) keys.push(k);
    });
    if (!keys.length) {
      return empty('Sector shares are not published for this place.');
    }
    var total = keys.reduce(function (a, k) { return a + num(shares[k]); }, 0);
    if (total <= 0) return empty('Sector shares are not published for this place.');

    var emph = o.emphasis && num(shares[o.emphasis]) !== null ? o.emphasis : null;

    // circumference 100 => dasharray values are straight percentages
    var R = 15.9155, CX = 21, CY = 21;
    var segs = '', legend = '', offset = 25; // start at 12 o'clock
    var ariaBits = [];

    keys.forEach(function (k) {
      var pct = num(shares[k]) / total * 100;
      var label = SECTOR_LABEL[k] || k;
      var col = hex(colors[k], SECTOR_COLOR[k] || 'var(--label-3)');
      var on = !emph || emph === k;
      var w = (emph === k) ? 6.4 : 4.6;
      segs += '<circle class="d-seg' + (on ? '' : ' is-dim') + '"' +
        ' cx="' + CX + '" cy="' + CY + '" r="' + R + '"' +
        ' fill="none" stroke="' + esc(col) + '" stroke-width="' + w + '"' +
        ' stroke-dasharray="' + round(pct, 3) + ' ' + round(100 - pct, 3) + '"' +
        ' stroke-dashoffset="' + round(offset, 3) + '"></circle>';
      offset -= pct;

      legend += '<li' + (emph === k ? ' class="is-emph"' : '') + '>' +
        '<span class="d-dot" style="background:' + esc(col) + '"></span>' +
        '<span class="d-lg-n">' + esc(label) + '</span>' +
        '<span class="d-lg-v">' + fmtPct(num(shares[k])) + '</span>' +
        '</li>';
      ariaBits.push(label + ' ' + fmtPct(num(shares[k])));
    });

    var centreVal = emph ? fmtPct(num(shares[emph])) : fmtPct(total, 0);
    var centreLbl = o.centerLabel || (emph ? (SECTOR_LABEL[emph] || emph) : 'of GCDP');

    var aria = (o.title ? o.title + '. ' : 'Sector shares. ') + ariaBits.join(', ') + '.';

    return '<div class="d-donut">' +
      '<svg class="d-donut-svg" viewBox="0 0 42 42" role="img" aria-label="' + esc(aria) + '">' +
        '<title>' + esc(aria) + '</title>' +
        '<circle cx="' + CX + '" cy="' + CY + '" r="' + R + '" fill="none" stroke="currentColor" stroke-opacity=".10" stroke-width="4.6"></circle>' +
        segs +
        '<text class="d-donut-c1" x="21" y="21.6" text-anchor="middle">' + esc(centreVal) + '</text>' +
        '<text class="d-donut-c2" x="21" y="25.6" text-anchor="middle">' + esc(centreLbl) + '</text>' +
      '</svg>' +
      '<ul class="d-legend">' + legend + '</ul>' +
      '</div>';
  }

  /* ---------------------------------------------------------- growthBullet */

  /**
   * growthBullet({rows, emphasis, baselineYear, targetYear})
   * rows = [{name, baseline, target, cagr, colorHex}]
   * Baseline is measured and renders solid; target is a plan and renders as an
   * outlined marker. They are never added together.
   */
  function growthBullet(o) {
    o = o || {};
    var rows = (o.rows || []).map(function (r) {
      return {
        name: r && r.name ? String(r.name) : '',
        baseline: num(r && r.baseline),
        target: num(r && r.target),
        cagr: num(r && r.cagr),
        colorHex: hex(r && r.colorHex, 'var(--green)')
      };
    }).filter(function (r) {
      return r.name && (r.baseline !== null || r.target !== null);
    });

    if (!rows.length) {
      return empty('No baseline or target figures are published for these sectors.');
    }

    var max = 0;
    rows.forEach(function (r) {
      if (r.baseline !== null) max = Math.max(max, r.baseline);
      if (r.target !== null) max = Math.max(max, r.target);
    });
    if (max <= 0) return empty('Baseline and target figures are zero or unpublished.');

    var by = o.baselineYear || '2023-24';
    var ty = o.targetYear || '2028-29';

    /* The bar scales horizontally only (preserveAspectRatio="none"), so no
       rounded corners live inside the SVG — they would stretch into ellipses.
       Rounding comes from the wrapping .d-bul-track, and the target marker is
       a vertical rule with a non-scaling stroke, which cannot distort. */
    var W = 1000, H = 14;

    var out = '<div class="d-bul">';
    rows.forEach(function (r) {
      var isE = o.emphasis && r.name.toLowerCase().indexOf(String(o.emphasis).toLowerCase()) === 0;
      var bw = r.baseline !== null ? (r.baseline / max) * W : 0;
      var tx = r.target !== null ? (r.target / max) * W : null;

      var parts = [];
      if (r.baseline !== null) parts.push('baseline ' + by + ' ' + fmtCr(r.baseline));
      if (r.target !== null) parts.push('target ' + ty + ' ' + fmtCr(r.target));
      if (r.cagr !== null) parts.push('CAGR ' + fmtPct(r.cagr) + ' a year');
      var aria = r.name + ': ' + parts.join(', ') + '.';

      out += '<div class="d-bul-row' + (isE ? ' is-emph' : '') + '">' +
        '<div class="d-bul-hd">' +
          '<span class="d-bul-n">' + esc(r.name) + '</span>' +
          (r.cagr !== null ? '<span class="d-bul-cagr">' + fmtPct(r.cagr) + ' CAGR</span>' : '') +
        '</div>' +
        '<div class="d-bul-track">' +
        '<svg class="d-bul-svg" viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="none"' +
        ' role="img" aria-label="' + esc(aria) + '">' +
          '<title>' + esc(aria) + '</title>';

      if (tx !== null && r.baseline !== null && tx > bw) {
        // The planned gap: same colour, washed out. Explicitly not an outturn.
        out += '<rect x="' + round(bw, 1) + '" y="0" width="' + round(tx - bw, 1) + '" height="' + H + '"' +
          ' fill="' + esc(r.colorHex) + '" fill-opacity="0.20"></rect>';
      }
      if (r.baseline !== null) {
        // Baseline = measured. Solid.
        out += '<rect x="0" y="0" width="' + round(bw, 1) + '" height="' + H + '"' +
          ' fill="' + esc(r.colorHex) + '"></rect>';
      }
      if (tx !== null) {
        // Target = plan. A dashed rule, never a solid fill.
        out += '<line x1="' + round(tx, 1) + '" y1="0" x2="' + round(tx, 1) + '" y2="' + H + '"' +
          ' stroke="' + esc(r.colorHex) + '" stroke-width="2" stroke-dasharray="3 2"' +
          ' vector-effect="non-scaling-stroke"></line>';
      }
      out += '</svg></div>' +
        '<div class="d-bul-ft">' +
          '<span>' + (r.baseline !== null ? 'Baseline ' + esc(by) + ' &middot; ' + fmtCr(r.baseline) : 'Baseline not published') + '</span>' +
          '<span>' + (r.target !== null ? 'Target ' + esc(ty) + ' &middot; ' + fmtCr(r.target) : 'Target not published') + '</span>' +
        '</div>' +
      '</div>';
    });

    out += '<div class="d-bul-key">' +
      '<span><i></i>Baseline ' + esc(by) + ' &mdash; measured</span>' +
      '<span><i class="d-k-g"></i>Planned gap</span>' +
      '<span><i class="d-k-t"></i>Target ' + esc(ty) + ' &mdash; a plan, not an outturn</span>' +
      '</div></div>';
    return out;
  }

  /* -------------------------------------------------------- compositionBars */

  /**
   * compositionBars({items, scale}) — items = [{name, pct, colorHex}]
   *
   * scale:'share' (default) draws each bar against a fixed 100% track, so the bar
   * width IS the share. scale:'relative' draws against the largest item.
   *
   * The default used to be relative-only, which made the largest bar full width
   * whatever its value — a 41% share rendered as a full bar under a heading that
   * said "share of GCDP". That reads as 100% and is not defensible in a
   * government-facing figure. Relative is still available, but a caller asking
   * for it is asserting the axis is a ranking, and must label it as one.
   */
  /* A series must wear the SAME colour in every chart on the page, so the hue is
     keyed off the sector name here rather than taken from whatever the source
     supplied. The AP portal ships #16A34A / #FF8A00 / #C93A2C, which measured at
     ΔE 3.9 for protanopia between the green and the orange -- far under the floor
     of 8. To roughly one man in twelve, agriculture and industry were the same
     colour. These three are validated on both surfaces; see compositionRibbon. */
  function sectorHue(name, fallback) {
    var k = String(name || '').toLowerCase();
    if (k.indexOf('agri') === 0 || k.indexOf('agriculture') > -1) return '#6FA817';
    if (k.indexOf('industr') > -1) return '#2B93BF';
    if (k.indexOf('service') > -1) return '#BF8A2B';
    return fallback || '#6FA817';
  }

  function compositionBars(o) {
    o = o || {};
    var items = (o.items || []).map(function (it) {
      return {
        name: it && it.name ? String(it.name) : '',
        pct: num(it && it.pct),
        colorHex: hex(it && it.colorHex, '')
      };
    }).filter(function (it) { return it.name && it.pct !== null; });

    if (!items.length) return empty('No sector composition figures are published for this place.');

    var peak = items.reduce(function (a, it) { return Math.max(a, it.pct); }, 0);
    if (peak <= 0) return empty('Sector composition figures are zero or unpublished.');

    /* share (default): the track is 100%, so width == the published percentage.
       relative: the track is the largest item, so width == rank position. */
    var relative = o.scale === 'relative';
    var max = relative ? peak : 100;

    /* Plotted as a real chart rather than three independent progress tracks: one
       shared axis with gridlines lets a reader compare the bars against each other
       and against 100%, which separate tracks never allowed. */
    var LEFT = 168, RIGHT = 56, TOP = 6, ROW = 38, BAR = 19;
    var W = 720, H = TOP + items.length * ROW + 30;
    var plotW = W - LEFT - RIGHT;
    var xa = function (v) { return LEFT + (plotW * Math.min(v, max)) / max; };

    var ticks = relative ? [0, max / 2, max] : [0, 25, 50, 75, 100];
    var grid = '', axis = '';
    ticks.forEach(function (t) {
      grid += '<line x1="' + xa(t) + '" y1="' + TOP + '" x2="' + xa(t) + '" y2="' +
        (TOP + items.length * ROW) + '" class="d-cb-grid"></line>';
      axis += '<text x="' + xa(t) + '" y="' + (H - 10) + '" class="d-cb-tick" ' +
        'text-anchor="' + (t === 0 ? 'start' : t === ticks[ticks.length - 1] ? 'end' : 'middle') +
        '">' + round(t, 0) + '%</text>';
    });

    var bars = '';
    items.forEach(function (it, i) {
      var y = TOP + i * ROW + (ROW - BAR) / 2;
      var w = Math.max(2, xa(it.pct) - LEFT);
      var fill = sectorHue(it.name, it.colorHex);
      bars +=
        '<g class="d-cb-row"><title>' + esc(it.name + ' — ' + fmtPct(it.pct)) + '</title>' +
        '<text x="' + (LEFT - 14) + '" y="' + (y + BAR / 2 + 4) + '" class="d-cb-cat" ' +
        'text-anchor="end">' + esc(it.name) + '</text>' +
        '<rect x="' + LEFT + '" y="' + y + '" width="' + plotW + '" height="' + BAR +
        '" rx="4" class="d-cb-track"></rect>' +
        '<rect x="' + LEFT + '" y="' + y + '" width="' + round(w, 1) + '" height="' + BAR +
        '" rx="4" fill="' + fill + '" class="d-cb-bar"></rect>' +
        '<text x="' + (LEFT + w + 9) + '" y="' + (y + BAR / 2 + 4) + '" class="d-cb-val">' +
        fmtPct(it.pct) + '</text></g>';
    });

    var out = '<figure class="d-comp"><svg viewBox="0 0 ' + W + ' ' + H + '" ' +
      'preserveAspectRatio="xMidYMid meet" role="img" aria-label="' +
      esc(items.map(function (it) { return it.name + ' ' + fmtPct(it.pct); }).join(', ')) + '">' +
      grid + bars + axis + '</svg>';
    return out + '</figure>';
  }

  /* ------------------------------------------------------------ thrustChips */

  function thrustChips(list) {
    var items = (list || []).map(function (t) {
      if (typeof t === 'string') return t;
      if (t && t.sectorName) return String(t.sectorName);
      if (t && t.name) return String(t.name);
      return '';
    }).filter(Boolean);
    if (!items.length) return empty('No thrust sectors are listed for this place.');
    return '<ul class="d-chips">' + items.map(function (t) {
      return '<li class="d-chip">' + esc(t) + '</li>';
    }).join('') + '</ul>';
  }

  /* -------------------------------------------------------------- drillList */

  /**
   * drillList({items, label, onpick})
   * items = strings or {name, sub}. onpick is the NAME of a global function;
   * it is called as onpick('<name>'). Omit onpick for a non-interactive list.
   */
  function drillList(o) {
    o = o || {};
    var items = (o.items || []).map(function (it) {
      if (typeof it === 'string') return { name: it };
      if (it && it.name) return { name: String(it.name), sub: it.sub };
      return null;
    }).filter(Boolean);

    if (!items.length) {
      return empty(o.emptyReason || 'No child areas are listed for this place.');
    }

    var fn = typeof o.onpick === 'string' && /^[A-Za-z_$][\w$.]*$/.test(o.onpick) ? o.onpick : null;

    var out = '';
    if (o.label) out += '<p class="d-drill-lbl">' + esc(o.label) + '</p>';
    out += '<ul class="d-drill">';
    items.forEach(function (it) {
      var inner = '<span class="d-drill-n">' + esc(it.name) + '</span>' +
        '<span class="d-drill-a">' + (it.sub ? esc(it.sub) : (fn ? '→' : '')) + '</span>';
      /* Guard the call site rather than the caller. A template names a handler it
         expects the page to provide; until integration defines it, clicking must do
         nothing rather than throw a ReferenceError at the user. This also keeps the
         templates free of any assumption about when wiring lands. */
      var call = 'if(typeof ' + fn + '===\'function\'){' + fn + '(this.dataset.name)}';
      out += '<li class="d-drill-i">' + (fn
        ? '<button type="button" onclick="' + esc(call) + '" data-name="' + esc(it.name) + '">' + inner + '</button>'
        : '<div>' + inner + '</div>') + '</li>';
    });
    return out + '</ul>';
  }

  /* -------------------------------------------------------------- rankStrip */

  /**
   * rankStrip({label, value, peers, unit})
   * peers = [{name, value}] INCLUDING this one; `value` identifies self by
   * matching name when {selfName} is given, otherwise by equal value.
   */
  /* ------------------------------------------------------------- sectorDots */

  /* A dot plot of the sectors that dominate a district: category on the left,
     a single dot placed by share on a shared axis, value and statewide rank on
     the right. Chosen over bars because a dot reads as a precise position rather
     than a filled quantity, so the GAP between #1 and #3 is what the eye catches
     -- which is the point when three sectors can be half the economy or a third
     of it. The shared axis makes those gaps comparable across districts.

     items: [{name, pct, rank}]   o.total: peer count for "rank X of N" */
  function sectorDots(items, o) {
    o = o || {};
    var rows = (items || []).map(function (it) {
      return {
        name: it && it.name ? String(it.name) : '',
        pct: num(it && it.pct),
        rank: num(it && it.rank)
      };
    }).filter(function (it) { return it.name && it.pct !== null; });

    if (!rows.length) return empty('No sector figures are published for this district.');

    var max = rows.reduce(function (a, r) { return Math.max(a, r.pct); }, 0);
    // all-zero shares would make every x() divide by zero and litter the SVG
    // with cx="NaN" — same guard compositionBars already carries
    if (max <= 0) return empty('Sector figures are zero or unpublished.');
    // round the axis up to a sensible ceiling so the top dot isn't jammed at the edge
    var ceil = max <= 10 ? Math.ceil(max / 2) * 2 : max <= 30 ? Math.ceil(max / 5) * 5
      : Math.ceil(max / 10) * 10;
    var total = num(o.total);

    var LEFT = 172, RIGHT = 92, TOP = 6, ROW = 40, R = 6;
    var W = 720, H = TOP + rows.length * ROW + 28;
    var plotW = W - LEFT - RIGHT;
    var x = function (v) { return LEFT + (plotW * Math.min(v, ceil)) / ceil; };

    var ticks = [0, ceil / 2, ceil];
    var grid = '', axis = '';
    ticks.forEach(function (t) {
      grid += '<line x1="' + x(t) + '" y1="' + TOP + '" x2="' + x(t) + '" y2="' +
        (TOP + rows.length * ROW) + '" class="d-cb-grid"></line>';
      axis += '<text x="' + x(t) + '" y="' + (H - 9) + '" class="d-cb-tick" text-anchor="' +
        (t === 0 ? 'start' : t === ceil ? 'end' : 'middle') + '">' + round(t, 0) + '%</text>';
    });

    var dots = '';
    rows.forEach(function (r, i) {
      var cy = TOP + i * ROW + ROW / 2;
      var cx = x(r.pct);
      var rankTxt = r.rank !== null ? (total ? 'rank ' + round(r.rank, 0) + ' of ' + round(total, 0)
        : 'rank ' + round(r.rank, 0)) : '';
      dots +=
        '<g class="d-sd-row"><title>' + esc(r.name + ' — ' + fmtPct(r.pct) +
        (rankTxt ? ' · ' + rankTxt + ' statewide' : '')) + '</title>' +
        // faint stem from the axis to the dot, so a low value still reads as a position
        '<line x1="' + LEFT + '" y1="' + cy + '" x2="' + cx + '" y2="' + cy +
        '" class="d-sd-stem"></line>' +
        '<text x="' + (LEFT - 14) + '" y="' + (cy + 4) + '" class="d-cb-cat" text-anchor="end">' +
        esc(r.name) + '</text>' +
        '<circle cx="' + round(cx, 1) + '" cy="' + cy + '" r="' + R + '" class="d-sd-dot"></circle>' +
        '<text x="' + (LEFT + plotW + 10) + '" y="' + (cy + 1) + '" class="d-cb-val">' +
        fmtPct(r.pct) + '</text>' +
        (rankTxt ? '<text x="' + (LEFT + plotW + 10) + '" y="' + (cy + 13) +
          '" class="d-sd-rank">' + esc(rankTxt) + '</text>' : '') +
        '</g>';
    });

    return '<figure class="d-comp"><svg viewBox="0 0 ' + W + ' ' + H + '" ' +
      'preserveAspectRatio="xMidYMid meet" role="img" aria-label="' +
      esc(rows.map(function (r) { return r.name + ' ' + fmtPct(r.pct); }).join(', ')) + '">' +
      grid + dots + axis + '</svg></figure>';
  }

  function rankStrip(o) {
    o = o || {};
    var peers = (o.peers || []).map(function (p) {
      return { name: p && p.name ? String(p.name) : '', value: num(p && p.value) };
    }).filter(function (p) { return p.name && p.value !== null; });

    if (peers.length < 2) {
      return empty('A peer comparison needs at least two places with published figures.');
    }
    var max = peers.reduce(function (a, p) { return Math.max(a, p.value); }, 0);
    if (max <= 0) return empty('Peer figures are zero or unpublished.');

    var sorted = peers.slice().sort(function (a, b) { return b.value - a.value; });
    var selfName = o.selfName || o.label;
    var selfVal = num(o.value);

    var out = '';
    if (o.label) out += '<p class="d-rank-lbl">' + esc(o.label) + '</p>';
    out += '<div class="d-rank">';
    sorted.forEach(function (p) {
      var self = (selfName && p.name === selfName) || (selfVal !== null && p.value === selfVal);
      var v = o.unit ? grp(round(p.value, 1)) + ' ' + o.unit : grp(round(p.value, 1));
      out += '<div class="d-rank-peer' + (self ? ' is-self' : '') + '">' +
        '<span class="d-rank-n">' + esc(p.name) + '</span>' +
        '<span class="d-rank-t" role="img" aria-label="' + esc(p.name + ' ' + v) + '">' +
          '<span class="d-rank-f" style="width:' + round(p.value / max * 100, 2) + '%"></span>' +
        '</span>' +
        '<span class="d-rank-v">' + esc(v) + '</span>' +
      '</div>';
    });
    return out + '</div>';
  }

  /* ------------------------------------------------------------------ export */

  /* ------------------------------------------------------------- brief ----
     A short written summary — the important highlights of the selected place,
     rendered above the archetype template at every level. Sentences are built
     only from fields that are actually present, each figure carries its year
     and estimate class, and the two share semantics are never conflated:
     pct_of_district is a sector's slice of THIS economy; pct_of_state_sector is
     this district's slice of AP's total FOR THAT SECTOR (~7x apart). A target
     is always named as a plan, never as a measurement. */
  var SECTOR_WORD = { agri: 'agriculture', industry: 'industry', services: 'services' };

  /* The highlights read as one woven paragraph, not a bullet list. Each
     builder contributes standalone sentences; joined with spaces they flow as
     prose. Everything else — only render what exists, label every figure —
     is unchanged. */
  function briefCard(kicker, lines) {
    lines = (lines || []).filter(Boolean);
    if (!lines.length) return '';
    return '<div class="d-sec d-brief"><div class="d-brief-k">' + esc(kicker) + '</div>' +
      '<p class="d-brief-p">' + lines.join(' ') + '</p></div>';
  }

  function shareSentence(shares, of) {
    if (!shares) return '';
    var ord = ['agri', 'industry', 'services'].filter(function (k) { return num(shares[k]) !== null; })
      .sort(function (a, b) { return shares[b] - shares[a]; });
    if (ord.length < 3) return '';
    return cap(SECTOR_WORD[ord[0]]) + ' carries the largest share of ' + of +
      ' at <b>' + fmtPct(shares[ord[0]]) + '</b>, ahead of ' +
      SECTOR_WORD[ord[1]] + ' (' + fmtPct(shares[ord[1]]) + ') and ' +
      SECTOR_WORD[ord[2]] + ' (' + fmtPct(shares[ord[2]]) + ').';
  }

  function cap(s) { return s ? s.charAt(0).toUpperCase() + s.slice(1) : s; }

  /** 1 -> "1st". Used for a rank read out inside a sentence. */
  function ordinal(n) {
    var v = num(n);
    if (v === null) return '';
    v = Math.round(v);
    var sfx = ['th', 'st', 'nd', 'rd'], m = v % 100;
    return v + (sfx[(m - 20) % 10] || sfx[m] || sfx[0]);
  }

  function briefDistrict(n) {
    var L = [];
    if (n.gddp !== null) {
      // the contract says gddp_series is always at least []; guard anyway, so a
      // malformed record costs one sentence, not the whole card via the catch
      var series = Array.isArray(n.gddp_series) ? n.gddp_series : [];
      var lastPt = null, firstPt = null, i;
      for (i = series.length - 1; i >= 0; i--) if (series[i].value !== null) { lastPt = series[i]; break; }
      for (i = 0; i < series.length; i++) if (series[i].value !== null) { firstPt = series[i]; break; }
      var s = 'The district economy stands at <b>' + fmtCr(n.gddp) + '</b> GDDP' +
        (lastPt && lastPt.year ? ' for ' + esc(lastPt.year) : '');
      if (n.gddp_growth !== null) s += ', <b>' + fmtPct(n.gddp_growth) + '</b> over the previous year';
      if (firstPt && firstPt !== lastPt && firstPt.value !== null)
        s += ', up from ' + fmtCr(firstPt.value) + ' in ' + esc(firstPt.year);
      L.push(s + '.');
    }
    /* The rank sentence below reads both ranks together when they disagree, so
       the per-capita rank is only stated here when that sentence will not run —
       otherwise the same "#24 of 28" is printed twice, a line apart. */
    var ranksDiffer = n.gddp_rank !== null && n.pci_rank !== null &&
                      Math.abs(n.gddp_rank - n.pci_rank) >= 3;
    if (n.pci !== null) {
      var p = 'Per-capita income is <b>' + fmtRs(n.pci) + '</b>' +
        (n.pci_growth !== null ? ', ' + fmtPct(n.pci_growth) + ' over the previous year' : '');
      if (n.pci_rank !== null && !ranksDiffer) p += '; the district ranks <b>#' + n.pci_rank + '</b> of ' +
        (n.district_count || 28) + ' by per-capita income';
      L.push(p + '.');
    }
    /* Size and standing are different questions, and a district can sit far apart
       on the two: Kurnool is 15th of 28 by total income but 24th by per-capita.
       That gap is a population fact, so state it as one rather than leaving the
       reader to reconcile two ranks. Only written when both ranks exist and
       actually disagree. */
    if (n.gddp_rank !== null) {
      var tot = n.district_count || 28;
      var r = 'By total district income it stands <b>#' + n.gddp_rank + '</b> of ' + tot;
      if (ranksDiffer) {
        r += ', ' + (n.gddp_rank < n.pci_rank ? 'ahead of' : 'behind') + ' its #' +
             n.pci_rank + ' on per-capita income';
        if (n.population !== null) {
          r += ': ' + (n.population_rank !== null && n.population_rank <= 5
                ? 'this is the state\u2019s ' + ordinal(n.population_rank) + ' most populous district, '
                : 'the district holds ') +
               grp(Math.round(n.population / 100000 * 10) / 10) + ' lakh people';
        }
      } else if (n.population !== null) {
        // ranks agree, so there is no gap to explain; the head count still
        // belongs here rather than leaving a four-word sentence on its own
        r += ', with ' + grp(Math.round(n.population / 100000 * 10) / 10) + ' lakh people' +
             (n.population_rank !== null && n.population_rank <= 5
               ? ', the ' + ordinal(n.population_rank) + ' largest population in the state' : '');
      }
      L.push(r + '.');
    }

    /* How the growth got here. A single year-on-year figure hides a lot when the
       four published years are different vintages, and this page's whole
       discipline is that an estimate is only as firm as its class. Each figure is
       quoted with the year it belongs to, so nothing implies the series is one
       consistent measurement. */
    var gs = (Array.isArray(n.gddp_series) ? n.gddp_series : [])
      .filter(function (pt) { return pt.growth !== null && pt.label; });
    if (gs.length >= 3) {
      var gv = gs.map(function (pt) { return pt.growth; });
      var spread = Math.max.apply(null, gv) - Math.min.apply(null, gv);
      var runs = gs.map(function (pt) { return fmtPct(pt.growth) + ' in ' + esc(pt.label); });
      L.push((spread >= 8 ? 'Growth has been uneven across the published years: '
                          : 'Growth across the published years has run ') +
             runs.slice(0, -1).join(', ') + ' and ' + runs[runs.length - 1] +
             ', each year on its own estimate vintage.');
    }
    L.push(shareSentence(n.shares, 'the district economy'));
    if (n.sectors && n.sectors.length) {
      var ranked = n.sectors.filter(function (sec) { return sec.pct_of_state_sector !== null; })
        .sort(function (a, b) { return b.pct_of_state_sector - a.pct_of_state_sector; });
      if (ranked[0]) L.push('Statewide, its strongest position is <b>' + esc(ranked[0].name) + '</b>, <b>' +
        fmtPct(ranked[0].pct_of_state_sector) + '</b> of AP’s total for that sector' +
        (ranked[0].rank !== null ? ' (rank ' + ranked[0].rank + ' of ' + (n.district_count || 28) + ' districts)' : '') + '.');
      if (ranked[1]) L.push('It also holds ground in <b>' + esc(ranked[1].name) + '</b>, with ' +
        fmtPct(ranked[1].pct_of_state_sector) + ' of the state total' +
        (ranked[1].rank !== null ? ' (rank ' + ranked[1].rank + ')' : '') + '.');

      /* Which way the individual sectors moved in the latest year. The shares
         above say what the economy is made of; this says what is changing, and
         a share can hold steady while the sector behind it swings hard.
         `growth` is the published year-on-year figure, so no arithmetic here. */
      var moved = n.sectors.filter(function (sec) { return sec.growth !== null; })
        .sort(function (a, b) { return b.growth - a.growth; });
      if (moved.length >= 2) {
        var up = moved[0], down = moved[moved.length - 1], mv = '';
        if (up.growth > 0) {
          mv = 'Across the ' + moved.length + ' sectors with a published movement, <b>' +
               esc(up.name) + '</b> grew fastest at <b>' + fmtPct(up.growth) + '</b>';
          if (down.growth < 0) mv += ', while <b>' + esc(down.name) + '</b> fell ' +
               fmtPct(Math.abs(down.growth));
          L.push(mv + '.');
        } else if (down.growth < 0) {
          L.push('No sector grew in the latest year; the steepest fall was <b>' +
                 esc(down.name) + '</b>, down ' + fmtPct(Math.abs(down.growth)) + '.');
        }
      }
    }
    return briefCard('District highlights', L);
  }

  function briefConstituency(n) {
    var L = [];
    if (n.gcdp_baseline !== null) {
      var s = 'GCDP was <b>' + fmtCr(n.gcdp_baseline) + '</b> in ' + esc(n.year_baseline);
      if (n.gcdp_target !== null) {
        s += '; the Swarna Andhra plan targets <b>' + fmtCr(n.gcdp_target) + '</b> by ' +
          esc(n.year_target) + ' (a plan, not a measurement)' +
          (n.cagr !== null ? ', implying <b>' + fmtPct(n.cagr) + '</b> a year' : '');
      }
      L.push(s + '.');
    }
    if (n.population !== null) {
      var d = 'Population <b>' + grp(n.population) + '</b>' +
        (n.population_note ? ' (' + esc(n.population_note) + ')' : '');
      if (n.area_sqkm !== null) d += ' across ' + grp(n.area_sqkm) + ' sq km';
      if (n.mandals && n.mandals.length) d += ', spread over <b>' + n.mandals.length + '</b> mandals';
      L.push(d + '.');
    }
    /* Standing among its siblings, and how densely it is settled. Both are in
       the contract already and neither was being written: the rank tells a
       reader whether this constituency carries the district or trails it, and
       density separates an urban seat from a spread-out rural one far better
       than a head count on its own. peerRank returns null unless the self entry
       and at least two peers actually carry the key, so nothing is guessed. */
    var pr = peerRank(n.peers, n.name, 'gcdp_baseline');
    if (pr) {
      L.push('That places it <b>#' + pr.rank + '</b> of ' + pr.total +
             ' constituencies in ' + esc(n.district || 'the district') + ' by GCDP.');
    }
    if (n.density !== null) {
      L.push('Settlement runs at <b>' + grp(n.density) + '</b> people per sq km' +
             (n.density >= 1500 ? ', an urban density' :
              n.density <= 300 ? ', sparse by state standards' : '') + '.');
    }
    L.push(shareSentence(n.shares, 'GCDP (' + esc(n.year_baseline) + ')'));
    if (n.thrust && n.thrust.length) {
      var t = n.thrust.slice(0, 3).map(function (x) { return esc(x); });
      L.push('Planned thrust: <b>' + t.join('</b> · <b>') + '</b>' +
        (n.thrust.length > 3 ? ' and ' + (n.thrust.length - 3) + ' more' : '') + '.');
    }
    return briefCard('Constituency highlights', L);
  }

  function briefMandal(n) {
    var L = [];
    if (n.own) {
      if (n.own.gmdp !== null) {
        var s = 'The mandal’s own GVA statement puts GMDP at <b>' + fmtCr(n.own.gmdp) + '</b>';
        if (n.own.rank !== null && n.own.rank_total !== null)
          s += ', <b>#' + n.own.rank + '</b> of ' + n.own.rank_total + ' mandals in ' +
            esc(n.constituency) + ' by GMDP';
        L.push(s + '.');
      }
      if (n.own.pci !== null || n.own.population !== null) {
        var bits = [];
        if (n.own.pci !== null) bits.push('per-capita income <b>' + fmtRs(n.own.pci) + '</b>');
        if (n.own.population !== null) bits.push('population <b>' + grp(n.own.population) + '</b>');
        L.push(cap(bits.join('; ')) + '.');
      }
      if (n.own.sectors && n.own.sectors.length) {
        var srt = n.own.sectors.slice().sort(function (a, b) { return b.pct - a.pct; });
        if (srt[0] && srt[0].pct !== null) {
          var sec = '<b>' + esc(srt[0].name) + '</b> is the largest slice of the mandal economy at <b>' +
            fmtPct(srt[0].pct) + '</b>';
          if (srt[1] && srt[1].pct !== null) sec += ', followed by ' + esc(srt[1].name) +
            ' at ' + fmtPct(srt[1].pct);
          L.push(sec + '.');
        }
      }
      var dem = n.own.demographics || {};
      if (num(dem.literacy_total) !== null) {
        L.push('Literacy stands at <b>' + fmtPct(dem.literacy_total) + '</b>' +
          (num(dem.literacy_female) !== null && num(dem.literacy_male) !== null
            ? ' (female ' + fmtPct(dem.literacy_female) + ', male ' + fmtPct(dem.literacy_male) + ')' : '') + '.');
      }
    } else {
      L.push('No mandal-level GVA statement could be extracted for ' + esc(n.name) +
        '; the figures below are the context it sits in.');
      if (n.inherited && n.inherited.gcdp_baseline !== null) {
        var c = esc(n.constituency) + ' constituency’s GCDP was <b>' + fmtCr(n.inherited.gcdp_baseline) +
          '</b> in ' + esc(n.inherited.year_baseline);
        if (n.inherited.gcdp_target !== null)
          c += ', with a ' + esc(n.inherited.year_target) + ' plan of ' + fmtCr(n.inherited.gcdp_target);
        L.push(c + '.');
      }
      if (n.inherited && n.inherited.thrust && n.inherited.thrust.length)
        L.push('Constituency thrust: <b>' + n.inherited.thrust.slice(0, 3).map(esc).join('</b> · <b>') + '</b>.');
    }
    return briefCard('Mandal highlights', L);
  }

  function brief(node, level) {
    if (!node) return '';
    try {
      if (level === 'district') return briefDistrict(node);
      if (level === 'constituency') return briefConstituency(node);
      if (level === 'mandal') return briefMandal(node);
    } catch (e) { /* a brief must never take the panel down with it */ }
    return '';
  }

  var DASH = {
    brief: brief,
    statCard: statCard,
    sectorDonut: sectorDonut,
    growthBullet: growthBullet,
    compositionBars: compositionBars,
    thrustChips: thrustChips,
    narrative: narrative,
    drillList: drillList,
    rankStrip: rankStrip,
    sectorDots: sectorDots,
    sourceNote: sourceNote,
    section: section,
    peerRank: peerRank,
    placeCrumb: placeCrumb,
    rankBadge: rankBadge,
    mandalOwnSection: mandalOwnSection,
    empty: empty,
    fmtCr: fmtCr,
    fmtRs: fmtRs,
    fmtPct: fmtPct,
    esc: esc,
    // helpers templates may find useful; not part of the binding contract
    num: num,
    grp: grp,
    sanitise: sanitise,
    compositionRibbon: compositionRibbon,
    muiChart: muiChart,
    muiSpark: muiSpark,
    sparkRow: sparkRow,
    statRow: function (cards) {
      var s = (cards || []).filter(Boolean).join('');
      return s ? '<div class="d-stats">' + s + '</div>' : '';
    },
    SOURCE_APC: 'Source: AP Assembly Constituencies portal. GCDP baseline 2023-24; target 2028-29 (Swarna Andhra Vision 2029 plan).',
    SOURCE_DIST: 'Source: AP district workbook. District figures are 2025-26 (First Advance Estimates).'
  };

  global.DASH = DASH;
  global.DASH_TPL = global.DASH_TPL || {};
})(typeof window !== 'undefined' ? window : this);
