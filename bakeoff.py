"""Head-to-head comparison of answering models on ONE shared retrieval.

Why a separate script from run_bench.py: this holds retrieval fixed and varies only the
answering LLM, so the comparison is paired -- every model sees byte-identical context for
every prompt. That is what makes a 30-prompt sample informative; unpaired, it would not be.

Usage:
    venv/bin/python bakeoff.py <provider> [n] [--judge MODEL]
    venv/bin/python bakeoff.py report

    provider : groq | gemini | haiku | sonnet | opus | anthropic
    n        : prompt count (default 30), stratified 2/3 numeric + 1/3 conceptual

Answers are cached to bakeoff_<provider>.jsonl, so providers can be run hours apart
(e.g. while a subscription limit resets) and compared later with `report`.

QUOTA GUARD -- the reason this file exists in its current form. On 2026-07-30 a
certification run reported Groq at 13.3%. It was measured nothing: 64 answers were HTTP 429
rate-limit strings and 40 judge calls returned "You've hit your session limit". Both were
scored as wrong answers. Quota exhaustion must abort the run loudly, never be graded.
"""
import st_stub  # noqa: F401  (must precede app import)
import app
import sys, json, re, time, os, random, subprocess

import embeddings as _emb
_emb.embed_query = lambda text: _emb.embed([text], is_query=True)[0]

GOLD = "gold_prompts.jsonl"
SEED = 3  # fixed so every provider gets the SAME prompts

# Any of these appearing in a model or judge response means we measured quota, not quality.
QUOTA_MARKERS = (
    "session limit", "rate_limit", "rate limit", "resource_exhausted",
    "429", "quota", "insufficient_quota", "__error__", "overloaded",
)

# Not all quota errors are equal, and conflating them wasted six API keys on 2026-07-30.
# PER-MINUTE quota refills in seconds -> wait and retry.
#   Gemini free tier: quotaId=GenerateRequestsPerMinutePerProjectPerModel-FreeTier,
#   5 req/min, retryDelay 30s.
# PER-DAY quota does not refill for hours -> abort, the run cannot continue today.
#   Groq free tier: "tokens per day (TPD): Limit 100000".
PER_MINUTE_MARKERS = ("perminute", "per minute", "per-minute", "requestsperminute")
PER_DAY_MARKERS = ("perday", "per day", "per-day", "tpd", "rpd", "tokens per day")


class QuotaExhausted(RuntimeError):
    """Raised instead of grading a response that is actually a quota message."""


def guard(text, where):
    low = (text or "").lower()
    for m in QUOTA_MARKERS:
        if m in low:
            raise QuotaExhausted(f"{where}: {(text or '')[:160]}")
    if not (text or "").strip():
        raise QuotaExhausted(f"{where}: empty response")
    return text


def norm(s):
    return re.sub(r"[^a-z0-9.]", "", str(s).lower())


# ---------------------------------------------------------------- prompts
def load_prompts(n):
    gold = [json.loads(l) for l in open(GOLD)]
    numeric = [g for g in gold if g["grade"] == "numeric"]
    concept = [g for g in gold if g["grade"] != "numeric"]
    rnd = random.Random(SEED)
    n_con = min(len(concept), n // 3)
    sample = (rnd.sample(numeric, min(n - n_con, len(numeric)))
              + rnd.sample(concept, n_con))
    rnd.shuffle(sample)
    return sample


# ---------------------------------------------------------------- retrieval (shared)
RETR_CACHE = "bakeoff_retrieval.jsonl"


def build_retrieval(sample, index):
    """Retrieve once per prompt and cache. Every provider replays this identical context."""
    cached = {}
    if os.path.exists(RETR_CACHE):
        for line in open(RETR_CACHE):
            r = json.loads(line)
            cached[r["prompt"]] = r
    out, fh = [], open(RETR_CACHE, "a")
    for g in sample:
        if g["prompt"] in cached:
            out.append(cached[g["prompt"]])
            continue
        df = app.detect_district(g["prompt"])
        hits = app.retrieve(g["prompt"], index, district_folder=df)
        rec = {"prompt": g["prompt"],
               "district_detected": df,
               "block": app.build_context_block(hits),
               "ctx": "\n".join(h.get("text", "") for h in hits),
               "sources": [h["source"] for h in hits][:8]}
        fh.write(json.dumps(rec) + "\n"); fh.flush()
        out.append(rec)
        print(f"  retrieved {len(out)}/{len(sample)}", end="\r")
    fh.close()
    print(f"  retrieved {len(out)}/{len(sample)}   ")
    return out


# ---------------------------------------------------------------- answering
CLI_MODELS = {"haiku", "sonnet", "opus"}

# Spare API keys, comma-separated, e.g. GEMINI_API_KEYS=key1,key2,key3.
# Per-day quota is scoped per project, so keys from different projects have independent
# buckets -- rotating lets one run span more than one key's 20/day allowance.
_KEY_POOL = {}


def _next_key(provider):
    """Advance <PROVIDER>_API_KEY to the next unused spare. False when none are left."""
    var = f"{provider.upper()}_API_KEY"
    if provider not in _KEY_POOL:
        pool = [k.strip() for k in os.environ.get(var + "S", "").split(",") if k.strip()]
        cur = os.environ.get(var, "")
        if cur and cur not in pool:
            pool.insert(0, cur)
        _KEY_POOL[provider] = {"pool": pool, "i": 0}
    st = _KEY_POOL[provider]
    st["i"] += 1
    if st["i"] >= len(st["pool"]):
        return False
    os.environ[var] = st["pool"][st["i"]]
    print(f"      -> key {st['i'] + 1}/{len(st['pool'])}")
    return True


def answer(provider, question, block):
    prompt = (f"CONTEXT:\n{block}\n\nQUESTION: {question}\n\n"
              f"Answer, citing the source file:")
    if provider in CLI_MODELS:
        r = subprocess.run(["claude", "-p", "--model", provider],
                           input=f"{app.SYSTEM_PROMPT}\n\n{prompt}",
                           capture_output=True, text=True, timeout=180)
        return guard((r.stdout or r.stderr).strip(), f"bot({provider})")
    os.environ["LLM_PROVIDER"] = provider
    msgs = [{"role": "system", "content": app.SYSTEM_PROMPT},
            {"role": "user", "content": prompt}]
    # 503/UNAVAILABLE is transient server load, NOT quota -- retry it rather than aborting
    # the run or (worse) grading the error string as a wrong answer.
    TRANSIENT = ("503", "unavailable", "high demand", "internal error", "500", "timeout")
    for attempt in range(6):
        try:
            return guard(app.call_llm(msgs).strip(), f"bot({provider})")
        except QuotaExhausted:
            raise
        except Exception as e:
            low = str(e).lower()
            # SDKs raise on 429 rather than returning text, so the string guard above
            # never sees it. Re-classify quota errors here.
            if any(m in low for m in QUOTA_MARKERS):
                per_day = any(m in low for m in PER_DAY_MARKERS)
                per_min = any(m in low for m in PER_MINUTE_MARKERS)
                # honour the server's own retryDelay when it gives one
                m = re.search(r"retrydelay['\"]?:\s*['\"]?(\d+)s", low)
                wait = int(m.group(1)) + 5 if m else 35
                if per_min and not per_day and attempt < 5:
                    print(f"      per-minute quota, waiting {wait}s "
                          f"(attempt {attempt + 1}/6)")
                    time.sleep(wait)
                    continue
                # Per-day quota is per PROJECT, so a key from another project has its own
                # bucket. Rotate through any spares before giving up.
                if per_day and _next_key(provider):
                    print(f"      per-day quota exhausted, rotating to next key")
                    continue
                raise QuotaExhausted(f"bot({provider}): {str(e)[:200]}") from None
            if any(m in low for m in TRANSIENT) and attempt < 5:
                wait = 5 * (2 ** attempt)
                print(f"      transient ({str(e)[:60]}...) retry in {wait}s")
                time.sleep(wait)
                continue
            raise


def judge(question, reference, ans, model):
    j = (f'You are grading a chatbot answer for a government economics assistant.\n'
         f'Question: "{question}"\n'
         f'Reference key points (ground truth): {reference}\n'
         f'Answer to grade: "{ans[:1200]}"\n'
         f'Grade correctness against the reference. Respond ONLY with minified JSON: '
         f'{{"verdict":"Correct|Partial|Incorrect",'
         f'"failure_point":"none|missing_content|not_used|incomplete|wrong_specificity|fabrication",'
         f'"reason":"<12 words"}}')
    out = subprocess.run(["claude", "-p", "--model", model], input=j,
                         capture_output=True, text=True, timeout=120).stdout
    guard(out, f"judge({model})")
    m = re.search(r"\{.*\}", out, re.DOTALL)
    if not m:
        # Not a quota problem and not JSON -- surface it rather than scoring it wrong.
        raise RuntimeError(f"judge returned non-JSON: {out[:200]}")
    return json.loads(m.group(0))


# ---------------------------------------------------------------- run
def run(provider, n, judge_model, label=None):
    # label separates result files when several models share one provider
    # (e.g. gemini-3.6-flash vs gemini-2.0-flash both route through provider "gemini").
    label = label or provider
    index = app.load_index()
    sample = load_prompts(n)
    model = os.environ.get(f"{provider.upper()}_MODEL", "")
    print(f"\n[bakeoff] provider={provider} label={label} model={model or '(default)'}")
    print(f"[bakeoff] n={len(sample)}  judge={judge_model}")
    print(f"[bakeoff] embeddings = {_emb.model_id()}")
    retr = {r["prompt"]: r for r in build_retrieval(sample, index)}

    path = f"bakeoff_{label}.jsonl"
    done = set()
    if os.path.exists(path):
        done = {json.loads(l)["prompt"] for l in open(path)}
        print(f"[bakeoff] resuming, {len(done)} already done")

    fh = open(path, "a")
    ok = tot = 0
    for i, g in enumerate(sample, 1):
        if g["prompt"] in done:
            continue
        r = retr[g["prompt"]]
        try:
            ans = answer(provider, g["prompt"], r["block"])
            if g["grade"] == "numeric":
                hit = (norm(g["target"]) in norm(ans)
                       or norm(g.get("target_alt", "\x00")) in norm(ans))
                fail = "none" if hit else "generation_miss"
            elif judge_model == "defer":
                # Conceptual grading is deferred to an in-session judge (see grade_pending).
                # hit=None is explicitly NOT False -- ungraded must never count as wrong.
                hit, fail = None, "pending_judge"
            else:
                jv = judge(g["prompt"], g["reference"], ans, judge_model)
                hit = jv.get("verdict") == "Correct"
                fail = jv.get("failure_point", "unknown")
        except QuotaExhausted as e:
            print(f"\n  !! QUOTA EXHAUSTED at prompt {i}: {e}")
            print(f"  !! {ok}/{tot} graded so far, saved to {path}.")
            print(f"  !! Re-run the same command later; it resumes.")
            fh.close()
            sys.exit(2)
        # retrieved: was the target figure even present in the context?
        retrieved = (g["grade"] == "numeric"
                     and (norm(g["target"]) in norm(r["ctx"])
                          or norm(g.get("target_alt", "\x00")) in norm(r["ctx"])))
        rec = {"prompt": g["prompt"], "provider": provider, "label": label,
               "model": model, "grade": g["grade"],
               "category": g.get("category"), "metric": g.get("metric"),
               "district": g.get("district"), "target": g.get("target"),
               "reference": g.get("reference"),
               "answer": ans, "hit": hit, "failure": fail,
               "retrieved": retrieved}
        fh.write(json.dumps(rec) + "\n"); fh.flush()
        if hit is not None:
            ok += bool(hit); tot += 1
        mark = "OK " if hit else ("...." if hit is None else "X  ")
        print(f"  [{i}/{len(sample)}] {mark} {fail:18s} "
              f"{str(g.get('metric'))[:14]:14s} {str(g.get('district') or '')[:14]}")
    fh.close()
    print(f"\n[bakeoff] {provider}: {ok}/{tot} on newly-run prompts. Full tally: bakeoff.py report")


# ---------------------------------------------------------------- report
def wilson(k, n):
    if n == 0:
        return (0.0, 0.0)
    z, p = 1.96, k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return (max(0, c - h) * 100, min(1, c + h) * 100)


def mcnemar(a, b):
    """Exact binomial McNemar on paired outcomes. Returns (b01, b10, p)."""
    from math import comb
    keys = set(a) & set(b)
    b01 = sum(1 for k in keys if not a[k] and b[k])
    b10 = sum(1 for k in keys if a[k] and not b[k])
    n = b01 + b10
    if n == 0:
        return b01, b10, 1.0
    lo = min(b01, b10)
    p = min(1.0, 2 * sum(comb(n, i) for i in range(lo + 1)) / (2 ** n))
    return b01, b10, p


def report():
    files = sorted(f for f in os.listdir(".")
                   if f.startswith("bakeoff_") and f.endswith(".jsonl")
                   and f != "bakeoff_retrieval.jsonl")
    if not files:
        print("No provider results yet.")
        return
    data = {}
    for f in files:
        prov = f[len("bakeoff_"):-len(".jsonl")]
        data[prov] = {json.loads(l)["prompt"]: json.loads(l) for l in open(f)}

    print("\n===== BAKE-OFF (shared retrieval, paired prompts) =====")
    hdr = f"  {'provider':12s} {'overall':>14s} {'numeric':>12s} {'conceptual':>12s}"
    print(hdr); print("  " + "-" * (len(hdr) - 2))
    pending_total = 0
    for prov, rows in data.items():
        allv = list(rows.values())
        pending = [r for r in allv if r["hit"] is None]
        pending_total += len(pending)
        v = [r for r in allv if r["hit"] is not None]   # ungraded != wrong
        num = [r for r in v if r["grade"] == "numeric"]
        con = [r for r in v if r["grade"] != "numeric"]
        k, n = sum(r["hit"] for r in v), len(v)
        lo, hi = wilson(k, n)
        def frac(rs):
            return f"{sum(r['hit'] for r in rs)}/{len(rs)}" if rs else "-"
        note = f"  ({len(pending)} awaiting judge)" if pending else ""
        print(f"  {prov:12s} {k:3d}/{n:<3d} {100*k/max(n,1):5.1f}% "
              f"{frac(num):>12s} {frac(con):>12s}   CI[{lo:.0f},{hi:.0f}]{note}")
    if pending_total:
        print(f"\n  {pending_total} conceptual answers are ungraded and EXCLUDED above.")
        print("  Overall numbers are numeric-only until they are judged.")

    provs = list(data)
    if len(provs) > 1:
        print("\n  Paired comparisons (exact McNemar):")
        for i in range(len(provs)):
            for j in range(i + 1, len(provs)):
                a, b = provs[i], provs[j]
                ha = {p: r["hit"] for p, r in data[a].items() if r["hit"] is not None}
                hb = {p: r["hit"] for p, r in data[b].items() if r["hit"] is not None}
                b01, b10, p = mcnemar(ha, hb)
                shared = len(set(ha) & set(hb))
                verdict = "significant" if p < 0.05 else "not significant"
                print(f"    {a:8s} vs {b:8s}  n={shared:3d}  "
                      f"{b} only:{b01:2d}  {a} only:{b10:2d}  p={p:.3f}  ({verdict})")
        print("\n  Note: with n=30 only large gaps reach significance. A non-significant")
        print("  result means 'not shown to differ', not 'shown to be equal'.")
    print()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "report":
        report(); sys.exit(0)
    prov = sys.argv[1] if len(sys.argv) > 1 else "groq"
    n = int(sys.argv[2]) if len(sys.argv) > 2 and not sys.argv[2].startswith("-") else 30
    jm = sys.argv[sys.argv.index("--judge") + 1] if "--judge" in sys.argv else "haiku"
    lb = sys.argv[sys.argv.index("--label") + 1] if "--label" in sys.argv else None
    run(prov, n, jm, lb)
