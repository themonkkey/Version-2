/* ── GVA calculator chassis engine ──────────────────────────────────────
   Wires one physical-calculator shell (markup in index.html, styles in
   chassis.css) around a sector's existing form and calculation. The sector
   engines themselves are untouched: each publishes its stage figures on
   window.__gvaStages_<px> and is reachable through window.__gvaCompute_<px>.

   Fit contract: nothing ever scrolls, inside or outside the shell, and the
   text stays at full size. A step whose content is taller than the face
   plate is split into PAGES at natural block boundaries, and the NEXT /
   BACK keys walk pages before they walk steps. Only a mild scale (never
   below 0.8) is used to absorb small overflows; anything larger paginates. */
(function(){
  'use strict';

  var slowOK = !matchMedia('(prefers-reduced-motion: reduce)').matches;

  function fmt(n){
    if(!isFinite(n)) return '–';
    /* Indian grouping to match the rest of the page (12,34,567 not 1,234,567) */
    var neg = n < 0; n = Math.abs(Math.round(n));
    var s = String(n);
    var last3 = s.slice(-3), rest = s.slice(0, -3);
    if(rest) last3 = ',' + last3;
    rest = rest.replace(/\B(?=(\d{2})+(?!\d))/g, ',');
    return (neg ? '−' : '') + rest + last3;
  }

  window.makeGvaChassis = function(cfg){
    var px = cfg.prefix;
    function $(suffix){ return document.getElementById(px + '_' + suffix); }
    var host = $('shell');
    if(!host) return null;

    var lcd = $('lcd'), lcdLab = $('lcdlab'), lcdNum = $('lcdnum'),
        lcdOp = $('lcdop'), lcdStep = $('lcdstep'), lcdTot = $('lcdtot'),
        lamps = $('lamps'), back = $('back'), next = $('next'), ac = $('ac'),
        calcBtn = document.getElementById(cfg.calcId),
        sampleBtn = document.getElementById(cfg.sampleId),
        clearBtn = document.getElementById(cfg.clearId);

    var N = cfg.labels.length;
    var step = 0, page = 0, fromCalc = false;
    var face = host.querySelector('.gvac-face');

    if(lcdTot) lcdTot.textContent = N;
    if(lamps){
      lamps.innerHTML = '';
      for(var i = 0; i < N; i++) lamps.appendChild(document.createElement('b'));
    }

    /* page dots between the face and the keypad */
    var dots = document.createElement('div');
    dots.className = 'gvac-pages';
    var well = host.querySelector('.gvac-well');
    if(well) well.parentNode.insertBefore(dots, well.nextSibling);

    host.querySelectorAll('.gvac-step').forEach(function(st){
      var w = document.createElement('div');
      w.className = 'gvac-fit';
      while(st.firstChild) w.appendChild(st.firstChild);
      st.appendChild(w);
    });

    function stages(){
      var s = cfg.compute();
      return (s && s.length === N) ? s : [];
    }

    var lcdAnim = 0;
    function lcdTo(target, dur){
      if(!lcdNum) return;
      var mine = ++lcdAnim;
      if(!slowOK){ lcdNum.textContent = fmt(target); return; }
      dur = dur || 700;
      var start = parseFloat(lcdNum.textContent.replace(/−/g, '-').replace(/[^\d.-]/g, '')) || 0;
      var t0 = performance.now();
      (function f(t){
        if(mine !== lcdAnim) return;
        var p = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - p, 3);
        lcdNum.textContent = fmt(start + (target - start) * e);
        if(p < 1) requestAnimationFrame(f);
      })(t0);
      /* rAF is suspended in a hidden tab; make sure the target still lands */
      setTimeout(function(){ if(mine === lcdAnim) lcdNum.textContent = fmt(target); }, dur + 80);
    }

    /* ── fit engine ─────────────────────────────────────────────────────
       atoms(): partitions a step's content into leaf blocks in document
       order — a block that fits is an atom; a taller container is kept (its
       heading repeats on every page it spans) and its children partition
       instead. buildPages() then packs atoms into face-sized pages. */
    var MILD = .8;    // smallest acceptable text scale before paginating

    function resetStep(w){
      w.style.transform = ''; w.style.width = ''; w.style.height = '';
      w.querySelectorAll('[data-gvacpage]').forEach(function(el){
        el.style.display = ''; el.removeAttribute('data-gvacpage');
      });
      w.__pages = null; w.__containers = null; w.__sticky = null;
    }

    function collectAtoms(el, avail, out, containers){
      Array.prototype.forEach.call(el.children, function(c){
        if(c.hidden) return;
        var h = c.getBoundingClientRect().height;
        if(!h) return;                          // display:none (is-off crop panels etc.)
        if(h <= avail * .82 || !c.children.length ||
           c.matches('table,.gva-scroll,.fc-srow,.cf,.gvac-head,.fc-shead,.cr-pick,.cr-nav,.fc-samplenote')){
          out.push(c);
        } else {
          containers.push({el: c, atoms: []});
          var mark = containers[containers.length - 1];
          var before = out.length;
          collectAtoms(c, avail, out, containers);
          mark.atoms = out.slice(before);
        }
      });
    }

    /* Blocks that must stay on screen on every page: the instruction line and
       the column header that names the units. Paging them away leaves a reader
       on page 2 typing numbers into unlabelled boxes. */
    var STICKY = '.calc-hint,.fc-shead,.cap-shead,.gvac-sticky';

    function buildPages(w, avail){
      var all = [], containers = [];
      collectAtoms(w, avail, all, containers);
      var sticky = [], atoms = [];
      all.forEach(function(a){ (a.matches(STICKY) ? sticky : atoms).push(a); });
      var hOf = function(a){ return a.getBoundingClientRect().height + 10; };
      /* Charge a page for what it will actually carry: the hint, plus the one
         section header that pins over its rows - not every header in the step,
         which in livestock would be a dozen. */
      var reserved = sticky.reduce(function(n, a){
        return a.matches('.calc-hint') ? n + hOf(a) : n;
      }, 0) + sticky.reduce(function(mx, a){
        return a.matches('.calc-hint') ? mx : Math.max(mx, hOf(a));
      }, 0);
      /* On a very short face the prose hint would cost more than the rows it
         explains. The unit header is the part that must not page away, so drop
         the hint back to page one and keep the columns labelled. */
      if(reserved > avail * .38){
        sticky = sticky.filter(function(a){ return !a.matches('.calc-hint'); });
        atoms = all.filter(function(a){ return sticky.indexOf(a) === -1; });
        reserved = sticky.reduce(function(mx, a){ return Math.max(mx, hOf(a)); }, 0);
      }
      var pages = [], cur = [], used = 0;
      /* Pack to the room that is actually left. The old flat .78 haircut was
         applied on top of the 30px already taken off avail, and with sticky
         blocks charged as well it left a third of the face empty and paged one
         row at a time. fit() verifies afterwards and repacks tighter if a page
         still overspills, so budgeting close to the true height is safe. */
      var budget = Math.max((avail - reserved) * .95, avail * .3);
      atoms.forEach(function(a){
        var h = a.getBoundingClientRect().height + 10;
        if(cur.length && used + h > budget){ pages.push(cur); cur = []; used = 0; }
        cur.push(a); used += h;
      });
      if(cur.length) pages.push(cur);
      /* A page must not end on a section title: the reader gets a heading with
         nothing under it and has to press NEXT to find out what it introduced.
         Trailing titles travel to the page their rows are on. */
      for(var i = pages.length - 2; i >= 0; i--){
        while(pages[i].length &&
              pages[i][pages[i].length - 1].matches('h3,h4,summary,.gvac-head')){
          pages[i + 1].unshift(pages[i].pop());
        }
      }
      pages = pages.filter(function(pg){ return pg.length; });
      w.__pages = pages; w.__containers = containers; w.__sticky = sticky;
      return pages;
    }

    function renderPage(w, idx){
      var pages = w.__pages;
      if(!pages || pages.length < 2){ dots.innerHTML = ''; return; }
      /* A sticky header pins only over the rows it actually labels - its own
         siblings. Livestock has one header per section, and pinning them all
         filled the page with column headings and no rows. The instruction
         hint has no rows of its own, so it always pins. */
      var sticky = w.__sticky || [];
      var live = sticky.filter(function(a){
        if(a.matches('.calc-hint')) return true;
        return pages[idx].some(function(b){
          /* a section title is a sibling too - pinning on that alone printed
             SILK & HONEY with its column header and no rows beneath it */
          return b.parentNode === a.parentNode && !b.matches('h3,h4,summary,.fc-shead');
        });
      });
      var shown = pages[idx].concat(live);
      pages.forEach(function(pg){
        pg.forEach(function(a){
          a.setAttribute('data-gvacpage', '1');
          a.style.display = shown.indexOf(a) > -1 ? '' : 'none';
        });
      });
      sticky.forEach(function(a){
        a.setAttribute('data-gvacpage', '1');
        a.style.display = live.indexOf(a) > -1 ? '' : 'none';
      });
      /* a container none of whose atoms are on this page hides with them */
      (w.__containers || []).forEach(function(c){
        var any = c.atoms.some(function(a){ return shown.indexOf(a) > -1; });
        c.el.setAttribute('data-gvacpage', '1');
        c.el.style.display = any ? '' : 'none';
      });
      dots.innerHTML = pages.map(function(_, i){
        return '<b class="' + (i === idx ? 'on' : '') + '"></b>';
      }).join('');
      /* safety net: if a single atom is still taller than the face, squeeze
         just this page rather than let it scroll */
      var availH = face.clientHeight - 30;
      var h = w.scrollHeight;
      if(h > availH){
        var k = Math.max(availH / h, .75);
        w.style.transformOrigin = 'top left';
        w.style.transform = 'scale(' + k + ')';
        w.style.width = (100 / k) + '%';
        w.style.height = Math.floor(w.scrollHeight * k) + 'px';
      } else {
        w.style.transform = ''; w.style.width = ''; w.style.height = '';
      }
    }

    function fit(){
      if(!face || !face.clientHeight) return;
      var st = host.querySelector('.gvac-step.on');
      var w = st && st.querySelector('.gvac-fit');
      if(!w) return;
      resetStep(w);
      dots.innerHTML = '';
      var avail = face.clientHeight - 30;
      var h = w.scrollHeight;
      lastFitAt = Date.now();
      if(h <= avail) return;
      var k = avail / h;
      if(k >= MILD){                            // barely over: shrink a touch, no paging
        w.style.transformOrigin = 'top left';
        w.style.transform = 'scale(' + k + ')';
        w.style.width = (100 / k) + '%';
        h = w.scrollHeight;
        k = Math.min(avail / h, k);
        w.style.transform = 'scale(' + k + ')';
        w.style.height = Math.floor(h * k) + 'px';
        return;
      }
      buildPages(w, avail);
      page = Math.min(page, (w.__pages || [1]).length - 1);
      renderPage(w, page);
      /* Verify, do not assume. If a page still overspills - the usual cause is
         one atom that grew after it was measured - repack with a tighter
         budget rather than leave content sitting under the keypad. Two passes
         at most; renderPage's own squeeze catches whatever survives that. */
      for(var pass = 0; pass < 2 && w.scrollHeight > avail; pass++){
        buildPages(w, avail * (pass ? 0.66 : 0.8));
        page = Math.min(page, (w.__pages || [1]).length - 1);
        renderPage(w, page);
      }
      syncKeys();
      lastFitAt = Date.now();
    }

    function pageCount(){
      var st = host.querySelector('.gvac-step.on');
      var w = st && st.querySelector('.gvac-fit');
      return (w && w.__pages) ? w.__pages.length : 1;
    }

    function syncKeys(){
      var last = step === N - 1, pc = pageCount(), lastPage = page >= pc - 1;
      if(back) back.disabled = step === 0 && page === 0;
      if(next){
        next.disabled = last && lastPage;
        next.textContent = last ? 'DONE ✓'
          : (!lastPage ? 'NEXT ▸'
          : (step === N - 2 ? '= RESULT' : 'NEXT ▸'));
      }
    }

    function show(s, startPage){
      if(s < 0 || s >= N) return;
      var vals = stages();
      if(s === N - 1 && !fromCalc && calcBtn){
        fromCalc = true; calcBtn.click(); fromCalc = false;
        vals = stages();
      }
      step = s; page = 0;
      host.querySelectorAll('.gvac-step').forEach(function(p){
        p.classList.toggle('on', +p.dataset.s === s);
      });
      if(lamps) lamps.querySelectorAll('b').forEach(function(b, i){
        b.className = i === s ? 'on' : (i < s ? 'done' : '');
      });
      if(lcdLab) lcdLab.textContent = cfg.labels[s];
      if(lcdOp)  lcdOp.textContent  = cfg.ops[s];
      if(lcdStep) lcdStep.textContent = s + 1;
      if(lcd){ lcd.classList.remove('flash'); void lcd.offsetWidth; lcd.classList.add('flash'); }
      if(vals.length) lcdTo(vals[s], s === N - 1 ? 1000 : 700);
      fit();
      if(startPage === 'last'){
        page = pageCount() - 1;
        var st2 = host.querySelector('.gvac-step.on');
        renderPage(st2.querySelector('.gvac-fit'), page);
      }
      syncKeys();
      var r = host.getBoundingClientRect();
      if(r.top < 0) window.scrollBy({top: r.top - 90, behavior: slowOK ? 'smooth' : 'auto'});
    }

    function goNext(){
      var st = host.querySelector('.gvac-step.on');
      var w = st && st.querySelector('.gvac-fit');
      if(w && w.__pages && page < w.__pages.length - 1){
        page++; renderPage(w, page); syncKeys(); return;
      }
      show(step + 1);
    }
    function goBack(){
      var st = host.querySelector('.gvac-step.on');
      var w = st && st.querySelector('.gvac-fit');
      if(w && w.__pages && page > 0){
        page--; renderPage(w, page); syncKeys(); return;
      }
      if(step > 0) show(step - 1, 'last');
    }

    if(next) next.addEventListener('click', goNext);
    if(back) back.addEventListener('click', goBack);
    if(ac)   ac.addEventListener('click', function(){ show(0); });

    /* the real Calculate button (kept for the Enter key and the crops
       sub-wizard's "Ready, calculate") lands the chassis on the result step */
    if(calcBtn) calcBtn.addEventListener('click', function(){
      if(fromCalc) return;
      fromCalc = true; show(N - 1); fromCalc = false;
    });

    /* Refit when the page reflows underneath us. fit() measures once and, when
       it scales, writes an explicit height onto the wrapper - so any reflow
       that happens AFTER that measurement is not contained by it and the
       content spills out from under the keypad.
       Webfonts are the usual cause: Public Sans, Bodoni and the icon font all
       arrive asynchronously, and on a cold cache or a slow link they land
       after the first fit, growing every line of text. It looked fine on a
       warm cache and broken on someone else's laptop.
       document.fonts.ready covers that; the two delayed passes are a backstop
       for anything else that settles late (a slow stylesheet, an icon font on
       a very slow link). fit() is idempotent - it resets the wrapper before
       measuring - so running it again is free. */
    /* Rather than guess when the reflow lands, watch for it. fit() is wrapped so
       it records what it measured; a ResizeObserver re-runs it whenever the
       face or the content genuinely changes size, and the signature check
       stops the observer chasing fit()'s own writes round in a loop. This
       covers late fonts, late stylesheets, the reveal animation settling, a
       zoom change - anything - without naming any of them. */
    var lastSig = '';
    function fitGuarded(force){
      if(!face || !face.clientHeight) return;
      var st = host.querySelector('.gvac-step.on');
      var w = st && st.querySelector('.gvac-fit');
      if(!w) return;
      var sig = face.clientHeight + ':' + step + ':' + page;
      if(!force && sig === lastSig && w.__pages) return;   // nothing meaningful moved
      lastSig = sig;
      fit();
    }
    var refitT = null, lastFitAt = 0;
    function refitSoon(){ clearTimeout(refitT); refitT = setTimeout(function(){ fitGuarded(true); }, 80); }
    /* An observer that watches the content will also see fit()'s own writes.
       Ignoring anything that lands right after a fit breaks that loop while
       still catching a genuine change - those come from a click, far later. */
    function refitOnContent(){ if(Date.now() - lastFitAt > 200) refitSoon(); }

    try{
      if(document.fonts && document.fonts.ready) document.fonts.ready.then(refitSoon);
    }catch(e){}
    setTimeout(refitSoon, 700);
    setTimeout(refitSoon, 1800);

    try{
      if(window.ResizeObserver && face){
        var ro = new ResizeObserver(function(){ refitSoon(); });
        ro.observe(face);                        // the box the content must fit
        var wellEl = host.querySelector('.gvac-well');
        if(wellEl) ro.observe(wellEl);
        /* ...and the content itself. Watching only the container missed the
           case that actually shipped: pressing "Load sample figures" injects a
           tall banner, the face never changes size, so nothing refit and the
           extra height spilled out under the keypad. */
        var ro2 = new ResizeObserver(function(){ refitOnContent(); });
        host.querySelectorAll('.gvac-fit').forEach(function(el){ ro2.observe(el); });
      }
    }catch(e){}

    window.addEventListener('resize', function(){ fitGuarded(true); });
    window.addEventListener('hashchange', function(){ setTimeout(fit, 150); });
    if(face) face.addEventListener('toggle', function(){ setTimeout(fit, 0); }, true);
    host.addEventListener('click', function(e){
      if(e.target.closest('.cr-box, [data-cgo], .calc-add, summary, .gvac-chip')) setTimeout(fit, 60);
    });
    document.addEventListener('click', function(e){
      if(e.target.closest('.calc-tab')) setTimeout(fit, 60);
    });

    /* live LCD tick — the running figure of the CURRENT stage follows typing */
    var tickT = null;
    host.addEventListener('input', function(){
      if(sampleBtn) sampleBtn.classList.add('edited');
      clearTimeout(tickT);
      tickT = setTimeout(function(){
        var vals = stages();
        if(vals.length) lcdTo(vals[step], 300);
      }, 160);
    });

    /* sample / clear chips: their existing handlers (registered earlier)
       reset the data; the chassis follows by rewinding to step 1 */
    function rewind(edited){
      if(sampleBtn) sampleBtn.classList.toggle('edited', !!edited);
      show(0);
    }
    if(sampleBtn) sampleBtn.addEventListener('click', function(){ rewind(false); });
    if(clearBtn)  clearBtn.addEventListener('click',  function(){ rewind(true); });

    /* arrival: rise in and count the LCD up once actually on screen */
    var io = new IntersectionObserver(function(es, o){
      es.forEach(function(e){
        if(!e.isIntersecting) return;
        host.closest('.gvac-stage').classList.add('go');
        var vals = stages();
        if(vals.length) lcdTo(vals[step], 1100);
        fit();
        o.disconnect();
      });
    }, {threshold: .2});
    io.observe(host);

    show(0);
    return {show: show, get step(){ return step; }};
  };
})();
