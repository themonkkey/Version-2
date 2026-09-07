"""Head-to-head Gemini model bakeoff on the gold benchmark.

Retrieves ONCE per prompt (same context fed to every candidate), then answers with
each Gemini model and grades:
  numeric    -> exact figure present in the answer (target / target_alt)
  conceptual -> claude CLI judge, same rubric as run_bench.py

Usage:  python bench_gemini_models.py [n_numeric] [n_concept]
Models come from BENCH_MODELS (comma-separated), default the three candidates.
"""
import st_stub  # noqa: F401  (must precede app import)
import app
import sys, json, re, math, time, os, random, datetime, subprocess, pickle, itertools

# Cohere trial keys: rotate + cache query vectors to disk (same scheme as run_bench.py —
# each trial key is 1000 calls/month, the census alone is ~400 queries).
import embeddings as _emb
if _emb.provider() == "cohere":
    _CK = [k.strip() for k in os.environ.get("COHERE_API_KEYS", "").split(",") if k.strip()] \
          or [os.environ.get("COHERE_API_KEY", "")]
    _cyc = itertools.cycle(_CK)
    _QC_PATH = "query_emb_cache.pkl"
    try:
        _QC = pickle.load(open(_QC_PATH, "rb"))
    except Exception:
        _QC = {}

    def _embed_query_rr(text):
        if text in _QC:
            return _QC[text]
        last = None
        for _ in range(len(_CK)):
            try:
                v = _emb.embed([text], is_query=True, api_key=next(_cyc))[0]
                _QC[text] = v
                pickle.dump(_QC, open(_QC_PATH, "wb"))
                return v
            except RuntimeError as e:
                last = e
                if "429" in str(e):
                    continue
                raise
        raise RuntimeError(f"all Cohere keys quota/rate limited: {last}")
    _emb.embed_query = _embed_query_rr

MODELS = [m.strip() for m in os.environ.get(
    "BENCH_MODELS", "gemini-3.5-flash-lite,gemini-3.5-flash,gemini-2.5-flash-lite"
).split(",") if m.strip()]
N_NUM = int(sys.argv[1]) if len(sys.argv) > 1 else 40
N_CON = int(sys.argv[2]) if len(sys.argv) > 2 else 20
N_CEN = int(sys.argv[3]) if len(sys.argv) > 3 else 0  # retrieval census size (no LLM)
JUDGE_MODEL = os.environ.get("JUDGE_MODEL", "haiku")
STAMP = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
LOG = f"gemini_bakeoff_{STAMP}.jsonl"


def norm(s):
    return re.sub(r"[,\s₹]", "", str(s)).lower()


def wilson(k, n, z=1.96):
    if n == 0: return (0.0, 0.0, 0.0)
    p = k / n; d = 1 + z*z/n
    c = (p + z*z/(2*n)) / d
    h = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / d
    return (p, max(0, c-h), min(1, c+h))


def retrieve_for(q):
    df = app.detect_district(q)
    for attempt in range(6):
        try:
            return df, app.retrieve(q, INDEX, district_folder=df)
        except RuntimeError as e:
            if "429" in str(e) and attempt < 5:
                time.sleep(20); continue
            raise


def answer_with(model, q, block):
    # "openrouter:google/gemini-3.6-flash" benches through OpenRouter; a bare name
    # goes direct to Google, so both routes share one harness.
    if model.startswith("openrouter:"):
        os.environ["LLM_PROVIDER"] = "openrouter"
        os.environ["OPENROUTER_MODEL"] = model.split(":", 1)[1]
    else:
        os.environ["LLM_PROVIDER"] = "gemini"
        os.environ["GEMINI_MODEL"] = model
    messages = [{"role": "system", "content": app.SYSTEM_PROMPT},
                {"role": "user",
                 "content": f"CONTEXT:\n{block}\n\nQUESTION: {q}\n\n"
                            f"Answer, citing the source file:"}]
    t0 = time.time()
    ans = app.call_llm(messages).strip()
    return ans, time.time() - t0


def judge(prompt, reference, answer):
    j = (f'You are grading a chatbot answer for a government economics assistant.\n'
         f'Question: "{prompt}"\n'
         f'Reference key points (ground truth): {reference}\n'
         f'Answer to grade: "{answer[:4000]}"\n'
         f'Grade correctness against the reference. Respond ONLY with minified JSON: '
         f'{{"verdict":"Correct|Partial|Incorrect",'
         f'"failure_point":"none|missing_content|not_retrieved|not_used|incomplete|wrong_specificity|fabrication",'
         f'"reason":"<12 words"}}')
    try:
        out = subprocess.run(["claude", "-p", "--model", JUDGE_MODEL], input=j,
                             capture_output=True, text=True, timeout=90).stdout
        m = re.search(r"\{.*\}", out, re.DOTALL)
        return json.loads(m.group(0)) if m else {"verdict": "Incorrect", "failure_point": "parse_error"}
    except Exception as e:
        return {"verdict": "Incorrect", "failure_point": "judge_error", "reason": str(e)[:40]}


def logline(obj):
    with open(LOG, "a") as f:
        f.write(json.dumps(obj) + "\n")


if __name__ == "__main__":
    INDEX = app.load_index()
    gold = [json.loads(l) for l in open("gold_prompts.jsonl")]
    numeric = [g for g in gold if g["grade"] == "numeric"]
    concept = [g for g in gold if g["grade"] == "judge"]

    # stratified numeric sample so one metric doesn't dominate
    rnd = random.Random(7)
    num_sample = []
    if N_NUM > 0:
        by_m = {}
        for g in numeric:
            by_m.setdefault(g["metric"], []).append(g)
        per = max(1, N_NUM // len(by_m))
        for m, qs in sorted(by_m.items()):
            num_sample.extend(rnd.sample(qs, min(per, len(qs))))
        num_sample = num_sample[:N_NUM]
    con_sample = rnd.sample(concept, min(N_CON, len(concept)))
    sample = [("numeric", g) for g in num_sample] + [("concept", g) for g in con_sample]

    print(f"Models: {MODELS}")
    print(f"Sample: {len(num_sample)} numeric + {len(con_sample)} conceptual, census={N_CEN}. "
          f"Judge={JUDGE_MODEL}. Log -> {LOG}", flush=True)

    # ---- retrieval census: figure-in-context, no LLM ----
    if N_CEN > 0:
        cen = numeric if N_CEN >= len(numeric) else rnd.sample(numeric, N_CEN)
        cen_rows = []
        for i, g in enumerate(cen):
            df, hits = retrieve_for(g["prompt"])
            block = app.build_context_block(hits, query=g["prompt"], district_folder=df)
            hit = (norm(g["target"]) in norm(block) or norm(g.get("target_alt", "\x00")) in norm(block))
            logline({"id": g["id"], "kind": "census", "metric": g["metric"], "hit": bool(hit)})
            cen_rows.append((g["metric"], hit))
            if (i + 1) % 50 == 0:
                print(f"  census {i+1}/{len(cen)}", flush=True)
            time.sleep(0.4)
        by = {}
        for m, h in cen_rows:
            by.setdefault(m, []).append(h)
        print("\n===== RETRIEVAL CENSUS (figure in LLM context) =====")
        for m in sorted(by):
            k, n = sum(by[m]), len(by[m]); p, lo, hi = wilson(k, n)
            print(f"  {m:22s} {k:3d}/{n:3d} = {p*100:5.1f}%  CI[{lo*100:4.1f},{hi*100:4.1f}]")
        k = sum(h for _, h in cen_rows); n = len(cen_rows); p, lo, hi = wilson(k, n)
        print(f"  {'OVERALL':22s} {k:3d}/{n:3d} = {p*100:5.1f}%  CI[{lo*100:4.1f},{hi*100:4.1f}]", flush=True)

    rows = []
    for i, (kind, g) in enumerate(sample):
        df, hits = retrieve_for(g["prompt"])
        block = app.build_context_block(hits, query=g["prompt"], district_folder=df)
        # retrieval ceiling: is the figure even in the context each model sees?
        ctx_hit = (kind == "numeric" and
                   (norm(g["target"]) in norm(block) or norm(g.get("target_alt", "\x00")) in norm(block)))
        for model in MODELS:
            try:
                ans, dt = answer_with(model, g["prompt"], block)
                err = None
            except Exception as e:
                ans, dt, err = "", 0.0, str(e)[:120]
            if kind == "numeric":
                hit = bool(ans) and (norm(g["target"]) in norm(ans)
                                     or norm(g.get("target_alt", "\x00")) in norm(ans))
                verdict = None
            else:
                jv = judge(g["prompt"], g["reference"], ans) if ans else {"verdict": "Incorrect", "failure_point": "api_error"}
                verdict = jv.get("verdict", "Incorrect")
                hit = verdict == "Correct"
            rec = {"id": g["id"], "kind": kind, "metric": g.get("metric"), "model": model,
                   "hit": bool(hit), "verdict": verdict, "ctx_hit": bool(ctx_hit),
                   "latency_s": round(dt, 2), "error": err, "answer": ans}
            if kind == "concept":
                rec["failure_point"] = jv.get("failure_point")
                rec["judge_reason"] = jv.get("reason")
            logline(rec); rows.append(rec)
            time.sleep(1.0)
        done = "".join("Y" if r["hit"] else "n" for r in rows[-len(MODELS):])
        print(f"  [{i+1}/{len(sample)}] {kind:7s} {g.get('metric') or 'concept':16s} {done}", flush=True)
        time.sleep(0.7)  # Cohere trial pacing

    print("\n===== RESULTS =====")
    for model in MODELS:
        mr = [r for r in rows if r["model"] == model]
        for kind in ("numeric", "concept"):
            kr = [r for r in mr if r["kind"] == kind]
            if not kr: continue
            k, n = sum(r["hit"] for r in kr), len(kr)
            p, lo, hi = wilson(k, n)
            print(f"  {model:24s} {kind:8s} {k:3d}/{n:3d} = {p*100:5.1f}%  CI[{lo*100:4.1f},{hi*100:4.1f}]")
        lat = sorted(r["latency_s"] for r in mr if r["latency_s"] > 0)
        if lat:
            print(f"  {model:24s} latency  median {lat[len(lat)//2]:.1f}s  p90 {lat[int(len(lat)*0.9)]:.1f}s")
        errs = sum(1 for r in mr if r["error"])
        if errs:
            print(f"  {model:24s} API errors: {errs}")
    nr = [r for r in rows if r["kind"] == "numeric" and r["model"] == MODELS[0]]
    if nr:
        k = sum(r["ctx_hit"] for r in nr)
        print(f"\n  retrieval ceiling (figure in context): {k}/{len(nr)} = {k/len(nr)*100:.1f}%")
    print(f"\nLog -> {LOG}")
