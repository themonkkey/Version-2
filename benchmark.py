"""Accuracy benchmark for the Swarna Andhra chatbot.

Auto-generates questions whose answers are known exactly (from
structured_district_data.csv), runs them through the LIVE pipeline
(detect_district -> retrieve -> build_context_block -> call_llm), and grades:

  1. Retrieval accuracy  : is the ground-truth figure present in the retrieved
                           context at all? (no LLM -> fast, large sample)
  2. End-to-end accuracy : does the final answer state the correct figure?
                           (LLM -> rate-limited, smaller sample)

Reports each as a proportion with a 95% Wilson score interval, broken by metric.
"""
import sys, types, csv, math, random, time, re

# ---- stub Streamlit so importing app.py does not launch the UI ----
class _Ctx:
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def __getattr__(self, k): return lambda *a, **kw: False
class _SS(dict):
    def __getattr__(self, k): return self.get(k)
    def __setattr__(self, k, v): self[k] = v
_st = types.ModuleType("streamlit")
def _noop(*a, **k): return None
def _cm(*a, **k): return _Ctx()
for name in ("set_page_config","markdown","error","write","caption","divider",
             "rerun","stop","title","subheader","header","info","warning","success"):
    setattr(_st, name, _noop)
_st.session_state = _SS(messages=[], pending=None)
_st.columns = lambda n, *a, **k: [_Ctx() for _ in range(n if isinstance(n, int) else len(n))]
_st.button = lambda *a, **k: False
_st.chat_input = lambda *a, **k: None
_st.chat_message = _cm; _st.spinner = _cm; _st.expander = _cm; _st.container = _cm
_st.cache_resource = lambda f=None, **k: (f if callable(f) else (lambda g: g))
_st.cache_data = _st.cache_resource
sys.modules["streamlit"] = _st

import app

random.seed(7)
CSV = "structured_district_data.csv"
LATEST = "2025-26 (FAE)"
SKIP_DISTRICTS = {"Andhra Pradesh PCI"}

# metrics whose figures are large + specific (low false-match risk)
METRICS = {
    "Gross District Domestic Product (GDDP)": ("GDDP",         "What is the GDDP of {d} for {y}?"),
    "Per Capita Income (Rs.)":                ("Per capita",   "What is the per capita income of {d} in {y}?"),
    "AGRICULTURE & ALLIED SECTOR":            ("Agri sector",  "What is the agriculture and allied sector value of {d} in {y}?"),
    "Industry Sector (aggregate)":            ("Industry",     "What is the industry sector value of {d} in {y}?"),
    "Services Sector (aggregate)":            ("Services",     "What is the services sector value of {d} in {y}?"),
}

def norm(s):
    return re.sub(r"[,\s₹]", "", str(s)).lower()

def build_pool():
    pool = []
    for r in csv.DictReader(open(CSV)):
        d = r["district"].strip()
        if d in SKIP_DISTRICTS or r["year"] != LATEST:
            continue
        m = METRICS.get(r["sector"].strip())
        if not m:
            continue
        try:
            val = float(r["value_rs_cr"])
        except (ValueError, TypeError):
            continue
        if val < 1000:
            continue
        target = str(int(round(val)))
        dname = d.title().replace("Sps ", "").replace("Ysr ", "")  # nicer display; alias match is substring
        q = m[1].format(d=d.title(), y="2025-26")
        pool.append({"q": q, "target": target, "metric": m[0], "district": d.title()})
    return pool

def wilson(k, n, z=1.96):
    if n == 0: return (0.0, 0.0, 0.0)
    p = k / n
    denom = 1 + z*z/n
    centre = (p + z*z/(2*n)) / denom
    half = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / denom
    return (p, max(0, centre-half), min(1, centre+half))

def answer_context(q):
    """Run the retrieval half of the pipeline; return (context_text, hits)."""
    df = app.detect_district(q)
    hits = app.retrieve(q, INDEX, district_folder=df)
    ctx = "\n".join(h.get("text", "") for h in hits)
    return ctx, hits

def ask_llm(q, hits):
    # mirror the real app: trimmed context block, not raw hit text
    block = app.build_context_block(hits)
    msgs = [{"role": "system", "content": app.SYSTEM_PROMPT},
            {"role": "user", "content": f"CONTEXT:\n{block}\n\nQUESTION: {q}"}]
    return app.call_llm(msgs)

def report(title, results):
    print(f"\n===== {title} =====")
    by = {}
    for r in results:
        by.setdefault(r["metric"], []).append(r["hit"])
    tot_k = sum(r["hit"] for r in results); tot_n = len(results)
    for metric in sorted(by):
        v = by[metric]; k, n = sum(v), len(v)
        p, lo, hi = wilson(k, n)
        print(f"  {metric:12s}  {k:2d}/{n:2d}  = {p*100:5.1f}%   95% CI [{lo*100:4.1f}, {hi*100:4.1f}]")
    p, lo, hi = wilson(tot_k, tot_n)
    print(f"  {'OVERALL':12s}  {tot_k:2d}/{tot_n:2d}  = {p*100:5.1f}%   95% CI [{lo*100:4.1f}, {hi*100:4.1f}]")

if __name__ == "__main__":
    print("Loading index...")
    INDEX = app.load_index()
    app.load_index = lambda: INDEX  # in case
    pool = build_pool()
    random.shuffle(pool)
    print(f"Generated {len(pool)} verifiable questions.")

    N_RETR = min(80, len(pool))
    N_E2E = int(sys.argv[1]) if len(sys.argv) > 1 else 24

    # ---- 1. retrieval accuracy (no LLM) ----
    retr_results = []
    hits_cache = {}
    for item in pool[:N_RETR]:
        ctx, hits = answer_context(item["q"])
        hits_cache[item["q"]] = hits
        hit = norm(item["target"]) in norm(ctx)
        retr_results.append({**item, "hit": hit})
    report(f"RETRIEVAL accuracy (n={N_RETR}) — figure present in retrieved context", retr_results)

    # ---- 2. end-to-end accuracy (LLM, rate-limited) ----
    print(f"\nRunning end-to-end on {N_E2E} questions (LLM, throttled)...")
    e2e_results = []
    for i, item in enumerate(pool[:N_E2E]):
        hits = hits_cache.get(item["q"]) or answer_context(item["q"])[1]
        try:
            ans = ask_llm(item["q"], hits)
        except Exception as e:
            ans = f"__ERROR__ {e}"
        hit = norm(item["target"]) in norm(ans)
        e2e_results.append({**item, "hit": hit, "ans": ans})
        print(f"  [{i+1}/{N_E2E}] {'OK ' if hit else 'MISS'} {item['metric']:11s} {item['district'][:16]:16s} want {item['target']}")
        time.sleep(40)  # respect Groq free-tier tokens-per-minute cap
    report(f"END-TO-END accuracy (n={N_E2E}) — correct figure in final answer", e2e_results)

    # show the misses for inspection
    print("\n--- end-to-end MISSES ---")
    for r in e2e_results:
        if not r["hit"]:
            print(f"  Q: {r['q']}\n     want {r['target']} | got: {r['ans'][:160]}...\n")
