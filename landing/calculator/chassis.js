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
      w.__pages = null; w.__containers = null;
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

    function buildPages(w, avail){
      var atoms = [], containers = [];
      collectAtoms(w, avail, atoms, containers);
      var pages = [], cur = [], used = 0;
      var budget = avail * .78;                 // headroom for repeated headings and container padding
      atoms.forEach(function(a){
        var h = a.getBoundingClientRect().height + 10;
        if(cur.length && used + h > budget){ pages.push(cur); cur = []; used = 0; }
        cur.push(a); used += h;
      });
      if(cur.length) pages.push(cur);
      w.__pages = pages; w.__containers = containers;
      return pages;
    }

    function renderPage(w, idx){
      var pages = w.__pages;
      if(!pages || pages.length < 2){ dots.innerHTML = ''; return; }
      var shown = pages[idx];
      pages.forEach(function(pg){
        pg.forEach(function(a){
          a.setAttribute('data-gvacpage', '1');
          a.style.display = shown.indexOf(a) > -1 ? '' : 'none';
        });
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
      syncKeys();
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

    /* refit whenever the content's shape can change */
    window.addEventListener('resize', fit);
    window.addEventListener('hashchange', function(){ setTimeout(fit, 150); });
    if(face) face.addEventListener('toggle', function(){ setTimeout(fit, 0); }, true);
    host.addEventListener('click', function(e){
      if(e.target.closest('.cr-box, [data-cgo], .calc-add, summary')) setTimeout(fit, 60);
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
