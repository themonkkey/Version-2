/* enrich.js — the join between the two data sources, and the single contract
   every dashboard template codes against.

   WHY THIS FILE EXISTS
   There are two datasets and they were never joined:
     landing/assets/dashboard_index.json  — 12 fields per constituency, always present
     landing/assets/apc/<code>.json       — the rich portal payload, loaded on demand
   The first template pass had four agents each invent their own join, all four of
   which read fields that existed nowhere. Every template now codes against the
   ENRICHED NODE defined below and nothing else.

   THE ENRICHED NODE — the complete contract. Every key is always present; the
   value is null / [] / '' when unknown. A template must never read a key that is
   not on this list, and must never assume a value is non-null.

   {
     // --- identity (always populated)
     name            : string        display name, e.g. "Anantapur Urban"
     code            : number|null   portal constituency code
     district        : string        parent district key
     archetype       : 'C1'|'C2'|'C3'|'C4'
     why             : string        one-line reason the archetype was assigned

     // --- headline economics (from dashboard_index; baseline is measured, target is a plan)
     gcdp_baseline   : number|null   Rs crore, 2023-24
     gcdp_target     : number|null   Rs crore, 2028-29 — A PLAN, NOT A MEASUREMENT
     cagr            : number|null   percent a year, as published by the portal
     shares          : {agri,industry,services}|null   percent of GCDP, 2023-24

     // --- demographics
     population      : number|null
     population_note : string        provenance EXACTLY as the portal states it, or
                                     '' when the portal states none. Never invent this.
     area_sqkm       : number|null
     density         : number|null   people per sq km, null unless both inputs exist
     voters          : number|null
     voters_note     : string
     revenue_villages: number|null
     municipalities  : number|null
     municipal_wards : number|null

     // --- sector detail (null until the apc payload is attached)
     growth          : [{name, code, baseline, target, cagr, colorHex}] | []
                       PER-SECTOR ONLY. The portal's whole-economy TOTAL row is
                       removed and surfaced separately as gcdp_* above, so a
                       template can never plot the total on the same axis as its parts.
     share_colors    : {agri,industry,services} | null   portal colorHex per sector

     // --- prose (sanitised HTML, '' when absent)
     profile_html    : string
     economy_html    : string
     geography_html  : string

     // --- lists
     thrust          : [string]
     mandals         : [string]
     mlas            : [{name, from, to, party}]
     peers           : [{name, gcdp_baseline}]   sibling constituencies, same district,
                                                 including this one. [] if unknown.

     // --- provenance
     source          : string   attribution line for the whole record
     year_baseline   : '2023-24'
     year_target     : '2028-29'
     enriched        : boolean  true once the apc payload was attached
   }

   USAGE
     const node = DASH.enrich(indexRecord, name, apcPayloadOrNull, indexAll);
     document.querySelector('#panel').innerHTML = DASH_TPL[node.archetype](node);
   apcPayload may be null — every template must render acceptably without it.
*/
(function (global) {
  'use strict';

  var YEAR_BASELINE = '2023-24';
  var YEAR_TARGET = '2028-29';
  var SOURCE = 'AP Assembly Constituencies portal (apconstituencies.ap.gov.in)';

  var SECTOR_KEY = { AGRIC: 'agri', INDUSTRY: 'industry', SERVICE: 'services' };

  function num(v) {
    if (v === null || v === undefined || v === '') return null;
    if (typeof v === 'number') return isFinite(v) ? v : null;
    var m = String(v).replace(/,/g, '').match(/-?\d+(\.\d+)?/);
    return m ? parseFloat(m[0]) : null;
  }

  /* The portal writes provenance inside the value: "223693 (As per Census 2011)".
     Pull it out verbatim. 10 of 175 records state none — those get '', and a
     template must not fill that gap with an assumption. */
  function note(v) {
    if (!v) return '';
    var m = String(v).match(/\(([^)]+)\)/);
    return m ? m[1].trim() : '';
  }

  /* The portal returns author-entered HTML. Strip anything executable rather than
     trusting it — this is third-party content rendered into our page. */
  function clean(html) {
    if (!html) return '';
    return String(html)
      .replace(/<\s*(script|style|iframe|object|embed|link|meta)\b[\s\S]*?<\s*\/\s*\1\s*>/gi, '')
      .replace(/<\s*(script|style|iframe|object|embed|link|meta)\b[^>]*\/?>/gi, '')
      .replace(/\son\w+\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+)/gi, '')
      .replace(/(href|src)\s*=\s*(?:"\s*javascript:[^"]*"|'\s*javascript:[^']*')/gi, '$1="#"')
      .trim();
  }

  function first(o, keys) {
    for (var i = 0; i < keys.length; i++) {
      if (o && o[keys[i]] !== undefined && o[keys[i]] !== null && o[keys[i]] !== '') return o[keys[i]];
    }
    return null;
  }

  function enrich(rec, name, apc, indexAll) {
    rec = rec || {};
    apc = apc || null;

    var shares = rec.shares && typeof rec.shares === 'object' ? {
      agri: num(rec.shares.agri),
      industry: num(rec.shares.industry),
      services: num(rec.shares.services)
    } : null;

    var population = num(rec.population);
    var area = num(rec.area_sqkm);

    var node = {
      name: name || rec.name || '',
      code: num(rec.code),
      district: rec.district || '',
      archetype: rec.archetype || 'C4',
      why: rec.why || '',

      gcdp_baseline: num(rec.gcdp_baseline),
      gcdp_target: num(rec.gcdp_target),
      cagr: num(rec.cagr),
      shares: shares,

      population: population,
      population_note: '',
      area_sqkm: area,
      density: (population !== null && area) ? Math.round(population / area) : null,
      voters: null,
      voters_note: '',
      revenue_villages: null,
      municipalities: null,
      municipal_wards: null,

      growth: [],
      share_colors: null,

      profile_html: '',
      economy_html: '',
      geography_html: '',

      thrust: Array.isArray(rec.thrust) ? rec.thrust.slice() : [],
      mandals: Array.isArray(rec.mandals) ? rec.mandals.slice() : [],
      mlas: [],
      peers: [],

      source: SOURCE,
      year_baseline: YEAR_BASELINE,
      year_target: YEAR_TARGET,
      enriched: false
    };

    /* peers — sibling constituencies in the same district, this one included, so a
       template can show where the place sits without a second lookup */
    if (indexAll && indexAll.constituencies) {
      var sibs = [];
      for (var k in indexAll.constituencies) {
        if (!Object.prototype.hasOwnProperty.call(indexAll.constituencies, k)) continue;
        var c = indexAll.constituencies[k];
        if (c && c.district === node.district) {
          sibs.push({ name: k, gcdp_baseline: num(c.gcdp_baseline) });
        }
      }
      node.peers = sibs;
    }

    if (!apc) return node;

    var prof = apc.profile || {};
    node.population_note = note(prof.population);
    node.voters = num(prof.voterCount);
    node.voters_note = note(prof.voterCount);
    node.revenue_villages = num(prof.revenueVillages);
    node.municipalities = num(prof.municipalities);
    node.municipal_wards = num(prof.municipal_wards);

    if (node.population === null) node.population = num(prof.population);
    if (node.area_sqkm === null) node.area_sqkm = num(prof.area);
    if (node.density === null && node.population !== null && node.area_sqkm) {
      node.density = Math.round(node.population / node.area_sqkm);
    }

    node.profile_html = clean(prof.constituencyprofile_Text);
    node.geography_html = clean(prof.geography);

    var eco = Array.isArray(apc.economy_text) ? apc.economy_text[0] : apc.economy_text;
    if (eco) node.economy_html = clean(first(eco, ['economy_Text', 'gcdP_Growth_Text']));

    /* growth: drop the whole-economy TOTAL row. It is already carried as gcdp_*, and
       leaving it in the array is how a template ends up plotting the total on the
       same axis as its own components. */
    if (Array.isArray(apc.growth)) {
      node.growth = apc.growth
        .filter(function (g) { return g && g.sectorCode && g.sectorCode !== 'TOTAL'; })
        .map(function (g) {
          return {
            name: g.sectorName || '',
            code: g.sectorCode || '',
            baseline: num(g.baselineAmountCrore),
            target: num(g.targetAmountCrore),
            cagr: num(g.cagR_Pct),
            colorHex: typeof g.colorHex === 'string' ? g.colorHex : ''
          };
        });
    }

    var sc = apc.share_current;
    if (sc && Array.isArray(sc.items)) {
      var colors = {};
      sc.items.forEach(function (it) {
        var key = SECTOR_KEY[it && it.sectorCode];
        if (key && typeof it.colorHex === 'string') colors[key] = it.colorHex;
      });
      if (Object.keys(colors).length) node.share_colors = colors;

      /* prefer the portal's own shares when present — dashboard_index derives them */
      if (!node.shares) {
        var s = {};
        sc.items.forEach(function (it) {
          var key = SECTOR_KEY[it && it.sectorCode];
          if (key) s[key] = num(it.sharePct);
        });
        if (Object.keys(s).length) node.shares = s;
      }
    }

    if (Array.isArray(apc.mlas)) {
      node.mlas = apc.mlas.map(function (m) {
        return {
          name: m && m.name ? String(m.name) : '',
          from: num(m && m.termFrom),
          to: num(m && m.termTo),
          party: m && m.partyName ? String(m.partyName) : ''
        };
      }).filter(function (m) { return m.name; });
    }

    node.enriched = true;
    return node;
  }

  /* ------------------------------------------------------------ districts ---
     THE ENRICHED DISTRICT NODE — the contract for the D1-D4 templates.
     Built from dashboard_index.json .districts[key] plus dist/<key>.json.
     Every key is always present; null / [] / '' when unknown.

     {
       key, name, archetype ('D1'|'D2'|'D3'|'D4'), why,
       pci_rank        : number|null   1 = highest of 28
       district_count  : number        28

       // headline, latest year, measured (2025-26 First Advance Estimate)
       gddp            : number|null   Rs crore
       gddp_growth     : number|null   percent over previous year
       gddp_rank       : number|null
       pci             : number|null   Rs
       pci_growth      : number|null
       population      : number|null   PERSONS (workbook stores thousands; scaled here)

       // 4-year series, oldest first — the trajectory. Each point:
       //   {year, label, value, growth, rank, estimate}
       // estimate is 'TRE'|'SRE'|'FRE'|'FAE' — these are DIFFERENT vintages and a
       // chart must say so; only the last is the First Advance Estimate.
       gddp_series     : [point]
       pci_series      : [point]

       // sector aggregates, 4-year, each point:
       //   {year, value, pct_of_district, pct_of_state_sector}
       // pct_of_district      = share of THIS district's GDVA   <- the usual "share"
       // pct_of_state_sector  = this district's share of the STATE total for that
       //                        sector. Guntur agriculture is 14.04% of Guntur and
       //                        2.01% of AP's agriculture. NEVER label one as the
       //                        other; they differ by 7x.
       aggregates      : {agri:[point], industry:[point], services:[point]} | null
       shares          : {agri,industry,services}|null   latest pct_of_district

       // all 17-ish real sectors, latest year, sorted by pct_of_district desc.
       // Totals, taxes and subsidies are excluded, so these never double-count.
       sectors         : [{name, value, rank, growth, pct_of_district, pct_of_state_sector}]

       constituencies  : [string]   child constituency names
       peers           : [{key, name, gddp, pci, pci_rank}]   all 28, for ranking
       latest_year     : '2025-26 (FAE)'
       source          : string
       enriched        : boolean    true once dist/<key>.json was attached
     }
  */
  var DIST_LATEST = '2025-26 (FAE)';
  var DIST_SOURCE = 'AP district-wise GVA/GDDP workbook, 2025-26 First Advance Estimate';

  function estimateOf(year) {
    var m = String(year || '').match(/\(([A-Z]+)\)/);
    return m ? m[1] : '';
  }

  function pointsOf(series) {
    if (!Array.isArray(series)) return [];
    return series.map(function (p) {
      return {
        year: p && p.year ? String(p.year) : '',
        label: p && p.year ? String(p.year).replace(/\s*\(.*\)$/, '') : '',
        value: num(p && p.value),
        growth: num(p && p.growth),
        rank: num(p && p.rank),
        estimate: estimateOf(p && p.year)
      };
    });
  }

  function last(arr) {
    for (var i = arr.length - 1; i >= 0; i--) {
      if (arr[i] && arr[i].value !== null) return arr[i];
    }
    return null;
  }

  function enrichDistrict(rec, key, dist, indexAll) {
    rec = rec || {};
    dist = dist || null;

    var node = {
      key: key || rec.key || '',
      name: (dist && dist.name) || (key || '').replace(/_/g, ' '),
      archetype: rec.archetype || 'D2',
      why: rec.why || '',
      pci_rank: num(rec.pci_rank),
      district_count: indexAll && indexAll.districts ? Object.keys(indexAll.districts).length : 28,

      gddp: null, gddp_growth: null, gddp_rank: null,
      pci: null, pci_growth: null, population: null,
      gddp_series: [], pci_series: [],
      aggregates: null,
      shares: rec.shares && typeof rec.shares === 'object' ? {
        agri: num(rec.shares.agri),
        industry: num(rec.shares.industry),
        services: num(rec.shares.services)
      } : null,
      sectors: [],
      constituencies: Array.isArray(rec.constituencies) ? rec.constituencies.slice() : [],
      peers: [],
      latest_year: DIST_LATEST,
      source: DIST_SOURCE,
      enriched: false
    };

    if (indexAll && indexAll.districts) {
      for (var k in indexAll.districts) {
        if (!Object.prototype.hasOwnProperty.call(indexAll.districts, k)) continue;
        var p = indexAll.districts[k];
        node.peers.push({
          key: k,
          name: k.replace(/_/g, ' '),
          gddp: null,
          pci: null,
          pci_rank: num(p && p.pci_rank)
        });
      }
    }

    if (!dist) return node;

    node.gddp_series = pointsOf(dist.gddp);
    node.pci_series = pointsOf(dist.pci);

    var g = last(node.gddp_series);
    if (g) { node.gddp = g.value; node.gddp_growth = g.growth; node.gddp_rank = g.rank; }
    var p2 = last(node.pci_series);
    if (p2) { node.pci = p2.value; node.pci_growth = p2.growth; }

    /* the workbook stores population in thousands; store persons so a template
       never has to know the unit, and can never render "5,915 people" */
    var popPt = last(pointsOf(dist.population));
    if (popPt && popPt.value !== null) node.population = Math.round(popPt.value * 1000);

    if (dist.aggregates) {
      node.aggregates = {};
      ['agri', 'industry', 'services'].forEach(function (kk) {
        node.aggregates[kk] = (dist.aggregates[kk] || []).map(function (pt) {
          return {
            year: pt && pt.year ? String(pt.year) : '',
            label: pt && pt.year ? String(pt.year).replace(/\s*\(.*\)$/, '') : '',
            value: num(pt && pt.value),
            pct_of_district: num(pt && pt.pct_of_district),
            pct_of_state_sector: num(pt && pt.pct_of_state_sector)
          };
        });
      });
      var latestShares = {};
      ['agri', 'industry', 'services'].forEach(function (kk) {
        var l = node.aggregates[kk][node.aggregates[kk].length - 1];
        if (l && l.pct_of_district !== null) latestShares[kk] = l.pct_of_district;
      });
      if (Object.keys(latestShares).length === 3) node.shares = latestShares;
    }

    if (Array.isArray(dist.sectors)) {
      node.sectors = dist.sectors.map(function (s) {
        return {
          name: s && s.name ? String(s.name) : '',
          value: num(s && s.value),
          rank: num(s && s.rank),
          growth: num(s && s.growth),
          pct_of_district: num(s && s.pct_of_district),
          pct_of_state_sector: num(s && s.pct_of_state_sector)
        };
      }).filter(function (s) { return s.name; });
    }

    node.enriched = true;
    return node;
  }

  global.DASH = global.DASH || {};
  global.DASH.enrich = enrich;
  global.DASH.enrichDistrict = enrichDistrict;
  global.DASH.DISTRICT_KEYS = [
    'key', 'name', 'archetype', 'why', 'pci_rank', 'district_count',
    'gddp', 'gddp_growth', 'gddp_rank', 'pci', 'pci_growth', 'population',
    'gddp_series', 'pci_series', 'aggregates', 'shares', 'sectors',
    'constituencies', 'peers', 'latest_year', 'source', 'enriched'
  ];
  global.DASH.ENRICHED_KEYS = [
    'name', 'code', 'district', 'archetype', 'why',
    'gcdp_baseline', 'gcdp_target', 'cagr', 'shares',
    'population', 'population_note', 'area_sqkm', 'density',
    'voters', 'voters_note', 'revenue_villages', 'municipalities', 'municipal_wards',
    'growth', 'share_colors',
    'profile_html', 'economy_html', 'geography_html',
    'thrust', 'mandals', 'mlas', 'peers',
    'source', 'year_baseline', 'year_target', 'enriched'
  ];
})(typeof window !== 'undefined' ? window : globalThis);
