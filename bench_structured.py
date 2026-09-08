"""A/B the precomputed-fact injection on comparison / trend / top-N questions.

The main gold set barely contains these -- its "comparison" prompts are conceptual
(GDDP vs NDDP), not district-vs-district -- so this measures the query shapes real
officers ask that the benchmark never covered. Ground truth is computed from the CSV,
so grading is exact-match, no judge needed.

Usage:  python bench_structured.py [model]
        INJECT=0 disables the fact block, for the before/after comparison.
"""
import st_stub  # noqa: F401
import app
import json, os, sys, time, math

MODEL = sys.argv[1] if len(sys.argv) > 1 else "gemini-3.1-flash-lite"
INJECT = os.environ.get("INJECT", "1") == "1"


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n; d = 1 + z*z/n
    c = (p + z*z/(2*n)) / d
    h = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / d
    return (p, max(0, c-h), min(1, c+h))


if __name__ == "__main__":
    os.environ["LLM_PROVIDER"] = "gemini"
    os.environ["GEMINI_MODEL"] = MODEL
    index = app.load_index()
    items = [json.loads(l) for l in open("gold_structured.jsonl")]
    print(f"model={MODEL} inject={INJECT} n={len(items)}", flush=True)

    rows = []
    for i, g in enumerate(items):
        q = g["prompt"]
        df = app.detect_district(q)
        hits = app.retrieve(q, index, district_folder=df)
        block = app.build_context_block(hits, query=q, district_folder=df)
        if not INJECT:
            # strip every VERIFIED block to reproduce the pre-injection behaviour
            block = "\n\n".join(p for p in block.split("\n\n")
                                if not p.lstrip().startswith("--- VERIFIED"))
        msgs = [{"role": "system", "content": app.SYSTEM_PROMPT},
                {"role": "user", "content": f"CONTEXT:\n{block}\n\nQUESTION: {q}"}]
        t0 = time.time()
        try:
            ans = app.call_llm(msgs)
        except Exception as e:
            ans = f"__ERROR__ {e}"
        hit = g["expect"].lower() in (ans or "").lower()
        rows.append({**g, "hit": hit, "latency": time.time() - t0, "answer": ans[:400]})
        print(f"  [{i+1}/{len(items)}] {'OK ' if hit else 'X  '} {g['kind']:11s} "
              f"expect {g['expect'][:22]}", flush=True)
        time.sleep(0.5)

    print("\n===== RESULTS =====")
    by = {}
    for r in rows:
        by.setdefault(r["kind"], []).append(r["hit"])
    for k, v in sorted(by.items()):
        n, c = len(v), sum(v); p, lo, hi = wilson(c, n)
        print(f"  {k:12s} {c:2d}/{n:2d} = {p*100:5.1f}%  CI[{lo*100:.0f},{hi*100:.0f}]")
    c, n = sum(r["hit"] for r in rows), len(rows); p, lo, hi = wilson(c, n)
    print(f"  {'OVERALL':12s} {c:2d}/{n:2d} = {p*100:5.1f}%  CI[{lo*100:.0f},{hi*100:.0f}]")
    tag = "inject" if INJECT else "baseline"
    with open(f"structured_{tag}_{MODEL}.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
