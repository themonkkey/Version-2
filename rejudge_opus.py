"""Re-judge the most recent run's conceptual answers with Opus, to separate
bot quality from judge strictness. Prints Sonnet-judge vs Opus-judge agreement."""
import sys, json, subprocess, re, glob

log = sorted(glob.glob("bench_log_*.jsonl"))[-1]
rows = [json.loads(l) for l in open(log)]
conc = [r for r in rows if r.get("phase") == "e2e" and r.get("grade") == "judge"]
print(f"log {log}: {len(conc)} conceptual answers to re-judge with Opus", flush=True)

def judge(p, ref, ans, model):
    j = (f'Grade a chatbot answer for a government economics assistant.\nQuestion: "{p}"\n'
         f'Reference key points: {ref}\nAnswer: "{ans[:1200]}"\n'
         f'Respond ONLY minified JSON: {{"verdict":"Correct|Partial|Incorrect","reason":"<12 words"}}')
    o = subprocess.run(["claude", "-p", "--model", model], input=j,
                       capture_output=True, text=True, timeout=150).stdout
    m = re.search(r"\{.*\}", o, re.DOTALL)
    return json.loads(m.group(0)) if m else {"verdict": "Incorrect", "reason": "parse"}

agree = opus_c = son_c = 0
rowsout = []
for i, r in enumerate(conc):
    jv = judge(r["prompt"], r["reference"], r.get("answer", ""), "opus")
    ov, sv = jv["verdict"], r.get("verdict", "")
    opus_c += ov == "Correct"; son_c += sv == "Correct"
    agree += (ov == "Correct") == (sv == "Correct")
    rowsout.append({"metric": r["metric"], "sonnet_judge": sv, "opus_judge": ov,
                    "prompt": r["prompt"][:70]})
    print(f"  [{i+1}/{len(conc)}] sonnet={sv:9s} opus={ov:9s} {r['metric']}", flush=True)

n = len(conc)
print(f"\nSonnet-judge Correct: {son_c}/{n} = {son_c/n*100:.0f}%")
print(f"Opus-judge   Correct: {opus_c}/{n} = {opus_c/n*100:.0f}%")
print(f"Judge agreement:      {agree}/{n} = {agree/n*100:.0f}%")
json.dump(rowsout, open("rejudge_opus.json", "w"), indent=1)
