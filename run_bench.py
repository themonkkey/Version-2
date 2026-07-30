"""Run the gold benchmark against the LIVE pipeline, log everything, report
accuracy with 95% Wilson intervals and the error-type distribution.

Usage:  venv/bin/python run_bench.py [e2e_sample_size] [judge_model]
  e2e_sample_size : how many prompts to run end-to-end through the bot LLM
                    (Groq is throttled, ~40s each). Default 60.
  judge_model     : claude CLI model for grading conceptual answers. Default haiku.

Two layers:
  RETRIEVAL  (all numeric prompts, no bot-LLM)  -> is the figure retrieved at all?
  END-TO-END (a stratified sample, bot-LLM)     -> does the answer state it / is it correct?
Error taxonomy per item: correct | retrieval_miss | generation_miss (numeric)
                         or the judge's failure_point (conceptual).
"""
import st_stub  # noqa: F401  (must precede app import)
import app
import sys, json, re, math, time, subprocess, datetime, os, pickle, itertools

# ---- Cohere query embeddings: rotate across all trial keys + cache to disk ----
# (each trial key = 1000 calls/month; rotation multiplies quota, cache avoids re-spend)
import embeddings as _emb

# The key-rotating cache below is COHERE-SPECIFIC and its cache file holds Cohere vectors.
# Installing it under any other provider silently scores cached Cohere vectors against a
# different model's index -- no error, just near-random similarities. Guard on provider.
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
else:
    # local/other providers: embed directly, no key rotation, no cross-provider cache
    _emb.embed_query = lambda text: _emb.embed([text], is_query=True)[0]
print(f"[bench] embedding provider = {_emb.model_id()}")

GOLD = "gold_prompts.jsonl"
E2E_N = int(sys.argv[1]) if len(sys.argv) > 1 else 120
JUDGE_MODEL = sys.argv[2] if len(sys.argv) > 2 else "sonnet"
BOT_MODEL = sys.argv[3] if len(sys.argv) > 3 else "haiku"  # Claude model powering the chatbot
STAMP = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
LOG = f"bench_log_{STAMP}.jsonl"

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
    # Cohere trial key = 100 calls/min; back off on 429
    for attempt in range(6):
        try:
            hits = app.retrieve(q, INDEX, district_folder=df)
            break
        except RuntimeError as e:
            if "429" in str(e) and attempt < 5:
                time.sleep(20); continue
            raise
    ctx = "\n".join(h.get("text", "") for h in hits)
    return df, hits, ctx

def bot_answer(q, hits):
    """Answer via Claude (CLI) powering the chatbot — same system prompt + context
    the production app uses, just a different generation model."""
    block = app.build_context_block(hits)
    prompt = (f"{app.SYSTEM_PROMPT}\n\nCONTEXT:\n{block}\n\nQUESTION: {q}\n\n"
              f"Answer, citing the source file:")
    r = subprocess.run(["claude", "-p", "--model", BOT_MODEL], input=prompt,
                       capture_output=True, text=True, timeout=120)
    return (r.stdout or r.stderr).strip()

def judge(prompt, reference, answer, model):
    j = (f'You are grading a chatbot answer for a government economics assistant.\n'
         f'Question: "{prompt}"\n'
         f'Reference key points (ground truth): {reference}\n'
         f'Answer to grade: "{answer[:1200]}"\n'
         f'Grade correctness against the reference. Respond ONLY with minified JSON: '
         f'{{"verdict":"Correct|Partial|Incorrect",'
         f'"failure_point":"none|missing_content|not_retrieved|not_used|incomplete|wrong_specificity|fabrication",'
         f'"reason":"<12 words"}}')
    try:
        out = subprocess.run(["claude", "-p", "--model", model], input=j,
                             capture_output=True, text=True, timeout=90).stdout
        m = re.search(r"\{.*\}", out, re.DOTALL)
        return json.loads(m.group(0)) if m else {"verdict": "Incorrect", "failure_point": "parse_error", "reason": out[:40]}
    except Exception as e:
        return {"verdict": "Incorrect", "failure_point": "judge_error", "reason": str(e)[:40]}

def report(title, rows, key="hit"):
    print(f"\n===== {title} =====")
    by = {}
    for r in rows:
        by.setdefault(r["metric"], []).append(r[key])
    for m in sorted(by):
        v = by[m]; k, n = sum(v), len(v); p, lo, hi = wilson(k, n)
        print(f"  {m:22s} {k:3d}/{n:3d} = {p*100:5.1f}%  CI[{lo*100:4.1f},{hi*100:4.1f}]")
    k = sum(r[key] for r in rows); n = len(rows); p, lo, hi = wilson(k, n)
    print(f"  {'OVERALL':22s} {k:3d}/{n:3d} = {p*100:5.1f}%  CI[{lo*100:4.1f},{hi*100:4.1f}]")

def logline(obj):
    with open(LOG, "a") as f:
        f.write(json.dumps(obj) + "\n")

if __name__ == "__main__":
    INDEX = app.load_index()
    gold = [json.loads(l) for l in open(GOLD)]
    numeric = [g for g in gold if g["grade"] == "numeric"]
    concept = [g for g in gold if g["grade"] == "judge"]
    print(f"Gold: {len(gold)} ({len(numeric)} numeric, {len(concept)} conceptual). "
          f"e2e sample={E2E_N}, bot={BOT_MODEL}, judge={JUDGE_MODEL}\nLog -> {LOG}")

    CONCEPT_ONLY = os.environ.get("CONCEPT_ONLY") == "1"
    if CONCEPT_ONLY:
        print("CONCEPT_ONLY: skipping numeric census; running all conceptual through the bot.")
        sample = list(concept); n_num, n_con = 0, len(concept)
        e2e = []
        for i, g in enumerate(sample):
            df, hits, ctx = retrieve_for(g["prompt"])
            try:
                ans = bot_answer(g["prompt"], hits)
            except Exception as e:
                ans = f"__ERROR__ {e}"
            jv = judge(g["prompt"], g["reference"], ans, JUDGE_MODEL)
            verdict = jv.get("verdict", "Incorrect")
            correct = verdict == "Correct"
            err = "correct" if correct else jv.get("failure_point", jv.get("reason", "unknown"))
            rec = {**g, "phase": "e2e", "answer": ans, "verdict": verdict,
                   "error_type": err, "hit": bool(correct)}
            logline(rec); e2e.append(rec)
            print(f"  [{i+1}/{len(sample)}] {'OK ' if correct else 'X  '} {verdict:9s} {g['metric'][:16]:16s}")
            time.sleep(1)
        report(f"CONCEPTUAL end-to-end (n={len(e2e)}, bot={BOT_MODEL}, judge={JUDGE_MODEL})", e2e)
        dist = {}
        for r in e2e: dist[r["error_type"]] = dist.get(r["error_type"], 0) + 1
        print("\n===== verdict / error distribution =====")
        for k in sorted(dist, key=lambda x: -dist[x]):
            print(f"  {k:16s} {dist[k]:3d}")
        print(f"\nLog -> {LOG}")
        sys.exit(0)

    # ---------- 1. RETRIEVAL (stratified sample of numeric, to conserve quota) ----------
    import random as _rnd; _rnd.seed(5)
    CENSUS_N = int(os.environ.get("CENSUS_N", "200"))
    by_m = {}
    for g in numeric:
        by_m.setdefault(g["metric"], []).append(g)
    per = max(1, CENSUS_N // len(by_m))
    numeric_sample = []
    for m, qs in by_m.items():
        numeric_sample.extend(_rnd.sample(qs, min(per, len(qs))))
    retr = []
    for g in numeric_sample:
        df, hits, ctx = retrieve_for(g["prompt"])
        hit = (norm(g["target"]) in norm(ctx) or norm(g.get("target_alt","\x00")) in norm(ctx))
        rec = {**g, "phase": "retrieval", "district_detected": df,
               "sources": [h["source"] for h in hits][:8], "retrieved": hit, "hit": hit}
        logline(rec); retr.append(rec)
        time.sleep(0.7)  # stay under Cohere trial 100 calls/min
    report(f"RETRIEVAL accuracy (census, n={len(retr)})", retr)

    # ---------- 2. END-TO-END (stratified sample) ----------
    import random; random.seed(3)
    n_con = min(len(concept), E2E_N // 3)          # ~1/3 conceptual
    n_num = E2E_N - n_con
    sample = random.sample(numeric, min(n_num, len(numeric))) + random.sample(concept, n_con)
    random.shuffle(sample)
    print(f"\nEnd-to-end on {len(sample)} prompts ({n_num} numeric + {n_con} conceptual), throttled...")

    e2e = []
    for i, g in enumerate(sample):
        df, hits, ctx = retrieve_for(g["prompt"])
        retrieved = (g["grade"] == "numeric") and ((norm(g["target"]) in norm(ctx) or norm(g.get("target_alt","\x00")) in norm(ctx)))
        try:
            ans = bot_answer(g["prompt"], hits)
        except Exception as e:
            ans = f"__ERROR__ {e}"
        if g["grade"] == "numeric":
            answered = (norm(g["target"]) in norm(ans) or norm(g.get("target_alt","\x00")) in norm(ans))
            correct = answered
            err = "correct" if answered else ("generation_miss" if retrieved else "retrieval_miss")
            verdict = "Correct" if correct else "Incorrect"
        else:
            jv = judge(g["prompt"], g["reference"], ans, JUDGE_MODEL)
            verdict = jv.get("verdict", "Incorrect")
            correct = verdict == "Correct"
            err = "correct" if correct else jv.get("failure_point", "unknown")
        rec = {**g, "phase": "e2e", "district_detected": df,
               "sources": [h["source"] for h in hits][:8], "answer": ans,
               "retrieved": retrieved, "verdict": verdict, "error_type": err,
               "hit": bool(correct)}
        logline(rec); e2e.append(rec)
        print(f"  [{i+1}/{len(sample)}] {'OK ' if correct else 'X  '} {err:16s} {g['metric'][:14]:14s} {(g.get('district') or '')[:14]:14s}")
        time.sleep(1)  # Claude CLI has no Groq-style per-minute token cap

    report(f"END-TO-END accuracy (sample, n={len(e2e)})", e2e)

    # ---------- error-type distribution ----------
    print("\n===== ERROR-TYPE DISTRIBUTION (end-to-end) =====")
    dist = {}
    for r in e2e:
        dist[r["error_type"]] = dist.get(r["error_type"], 0) + 1
    for k in sorted(dist, key=lambda x: -dist[x]):
        print(f"  {k:18s} {dist[k]:3d}  ({dist[k]/len(e2e)*100:.1f}%)")
    print(f"\nFull per-prompt log written to {LOG}")
