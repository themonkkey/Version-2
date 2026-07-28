"""Self-improving loop to push conceptual/reasoning accuracy to 90%, using
Claude Code only (every agent is a `claude -p` call). No API keys, no Groq.

Agents:
  ANSWERER  (haiku, cheapest)  — the bot under optimization
  JUDGE     (sonnet)           — grades vs reference (validated ~= opus earlier)
  OPTIMIZER (opus)             — reads failures, rewrites the system prompt

Loops:
  OUTER  optimization rounds   — optimizer proposes a new prompt each round;
                                 keep the best on the TRAIN split; stop at 90%.
  INNER  self-refine (2-pass)  — answerer drafts, then critiques+rewrites its
                                 own answer; evaluated as a separate strategy.

Honest methodology: optimize on TRAIN, report the final number on held-out VAL
with a 95% Wilson interval. Everything logged to optimize_log_*.jsonl.
"""
import st_stub, app
import json, subprocess, re, math, sys, datetime
from concurrent.futures import ThreadPoolExecutor

DATA = json.load(open("concept_dataset.json"))
TRAIN, VAL = DATA["train"], DATA["val"]
ANSWER_MODEL, JUDGE_MODEL, OPT_MODEL = "haiku", "sonnet", "sonnet"  # sonnet optimizer = lighter on quota
MAX_ROUNDS = int(sys.argv[1]) if len(sys.argv) > 1 else 3
TARGET = 0.90
WORKERS = 5
STAMP = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
LOG = f"optimize_log_{STAMP}.jsonl"

BASE_PROMPT = app.SYSTEM_PROMPT  # start from the production system prompt

class SessionLimit(Exception):
    pass

def cli(model, prompt, timeout=180):
    try:
        r = subprocess.run(["claude", "-p", "--model", model], input=prompt,
                           capture_output=True, text=True, timeout=timeout)
        out = (r.stdout or r.stderr).strip()
        if "session limit" in out.lower() or "usage limit" in out.lower():
            raise SessionLimit(out[:80])
        return out
    except SessionLimit:
        raise
    except Exception as e:
        return f"__ERROR__ {e}"

def answer(sys_prompt, it, refine=False):
    p = (f"{sys_prompt}\n\nCONTEXT:\n{it['context']}\n\nQUESTION: {it['prompt']}\n\n"
         f"Answer, citing the source file:")
    a = cli(ANSWER_MODEL, p)
    if refine:
        crit = (f"Question: {it['prompt']}\n\nDraft answer:\n{a}\n\n"
                f"List briefly what the draft MISSES to be complete and correct, "
                f"then output ONLY a final improved answer that fixes those gaps.")
        a = cli(ANSWER_MODEL, crit)
    return a

def judge(it, ans):
    j = (f'Grade a chatbot answer for a government economics assistant.\n'
         f'Question: "{it["prompt"]}"\nReference key points: {it["reference"]}\n'
         f'Answer: "{ans[:1400]}"\n'
         f'Respond ONLY minified JSON: {{"verdict":"Correct|Partial|Incorrect","reason":"<12 words"}}')
    o = cli(JUDGE_MODEL, j)
    m = re.search(r"\{.*\}", o, re.DOTALL)
    try:
        return json.loads(m.group(0))
    except Exception:
        return {"verdict": "Incorrect", "reason": "parse_error"}

def logline(o):
    with open(LOG, "a") as f:
        f.write(json.dumps(o) + "\n")

def evaluate(sys_prompt, items, tag, refine=False):
    def one(it):
        a = answer(sys_prompt, it, refine)
        v = judge(it, a)
        rec = {"tag": tag, "id": it["id"], "metric": it["metric"],
               "verdict": v.get("verdict"), "reason": v.get("reason"),
               "answer": a[:500], "refine": refine}
        logline(rec)
        return {**it, **rec}
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        res = list(ex.map(one, items))
    correct = sum(r["verdict"] == "Correct" for r in res)
    return correct / len(res), res

def optimize(cur_prompt, fails):
    cases = json.dumps([{"question": x["prompt"], "reference": x["reference"],
                         "bot_answer": x["answer"][:350], "why_wrong": x["reason"]}
                        for x in fails[:12]], indent=1)
    p = (f"You are optimizing the SYSTEM PROMPT of a low-cost RAG chatbot for an Indian "
         f"government economics programme. It answers from retrieved CONTEXT.\n\n"
         f"CURRENT SYSTEM PROMPT:\n<<<\n{cur_prompt}\n>>>\n\n"
         f"These conceptual answers were graded wrong. Study the failure patterns:\n{cases}\n\n"
         f"Rewrite the system prompt so a small model answers these correctly. Emphasise: "
         f"enumerate ALL parts a question asks for; give complete, appropriately specific "
         f"answers; ground in and cite the context; distinguish corpus facts from general "
         f"knowledge. Keep it tight. Output ONLY the new system prompt, nothing else.")
    out = cli(OPT_MODEL, p)
    # strip echoed delimiters / code fences / labels
    out = re.sub(r"^```[a-z]*\n?|```$", "", out.strip())
    out = out.strip().lstrip("<").rstrip(">").strip()
    out = re.sub(r"^(new )?system prompt:\s*", "", out, flags=re.I).strip()
    return out

def wilson(k, n, z=1.96):
    if n == 0: return (0, 0, 0)
    p = k/n; d = 1 + z*z/n
    c = (p + z*z/(2*n))/d; h = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))/d
    return p, max(0, c-h), min(1, c+h)

def pct(x): return f"{x*100:.1f}%"

def _run():
    best_prompt, best_acc = BASE_PROMPT, -1
    acc, res = evaluate(BASE_PROMPT, TRAIN, "baseline")
    best_prompt, best_acc, best_res = BASE_PROMPT, acc, res
    print(f"[baseline] train acc = {pct(acc)}", flush=True)

    for r in range(MAX_ROUNDS):
        if best_acc >= TARGET:
            print(f"target reached on train ({pct(best_acc)}); stopping rounds.", flush=True)
            break
        fails = [x for x in best_res if x["verdict"] != "Correct"]
        cand = optimize(best_prompt, fails)
        if cand.startswith("__ERROR__") or len(cand) < 40:
            print(f"[round {r}] optimizer failed, skipping", flush=True); continue
        acc_c, res_c = evaluate(cand, TRAIN, f"round{r}")
        print(f"[round {r}] candidate train acc = {pct(acc_c)} (best {pct(best_acc)})", flush=True)
        if acc_c > best_acc:
            best_prompt, best_acc, best_res = cand, acc_c, res_c
            open("optimized_prompt.txt", "w").write(cand)

    # inner-loop strategy: self-refine two-pass with the best prompt (train)
    acc_ref, _ = evaluate(best_prompt, TRAIN, "train_refine", refine=True)
    print(f"[self-refine] train acc = {pct(acc_ref)}", flush=True)
    use_refine = acc_ref > best_acc

    # ---- final held-out validation ----
    print("\n=== HELD-OUT VALIDATION ===", flush=True)
    for refine in ([False, True] if True else [use_refine]):
        va, vres = evaluate(best_prompt, VAL, f"val{'_refine' if refine else ''}", refine=refine)
        k = sum(x["verdict"] == "Correct" for x in vres); n = len(vres)
        p, lo, hi = wilson(k, n)
        by = {}
        for x in vres:
            by.setdefault(x["metric"], [0, 0])
            by[x["metric"]][0] += x["verdict"] == "Correct"; by[x["metric"]][1] += 1
        print(f"\n-- validation {'(self-refine 2-pass)' if refine else '(single-pass)'} --", flush=True)
        for m in sorted(by):
            c, t = by[m]; pp, ll, hh = wilson(c, t)
            print(f"  {m:20s} {c:2d}/{t:2d} = {pct(pp)}  CI[{pct(ll)},{pct(hh)}]", flush=True)
        print(f"  {'OVERALL':20s} {k:2d}/{n:2d} = {pct(p)}  CI[{pct(lo)},{pct(hi)}]  "
              f"{'>= TARGET' if lo >= TARGET or p >= TARGET else ''}", flush=True)

    open("optimized_prompt.txt", "w").write(best_prompt)
    print(f"\nBest prompt (train {pct(best_acc)}) saved -> optimized_prompt.txt", flush=True)
    print(f"Full log -> {LOG}", flush=True)


if __name__ == "__main__":
    print(f"Optimize reasoning -> target {pct(TARGET)}. answerer={ANSWER_MODEL}, "
          f"judge={JUDGE_MODEL}, optimizer={OPT_MODEL}. "
          f"train={len(TRAIN)}, val={len(VAL)}. Log={LOG}", flush=True)
    try:
        _run()
    except SessionLimit as e:
        print(f"\n!! Claude Code session limit hit: {e}\n"
              f"   Rerun after reset (6:30pm IST). Partial results in {LOG}.", flush=True)
        sys.exit(2)
