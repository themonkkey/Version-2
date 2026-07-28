"""Generate a stratified gold benchmark of ~450 prompts for the Swarna Andhra bot.

Output: gold_prompts.jsonl — one JSON object per line:
  {id, category, metric, district, year, prompt, target, reference, grade}
where grade == "numeric" (objective: target figure must appear) or
      grade == "judge"   (LLM-judge against `reference` key points).
"""
import csv, json, os, re, random, glob

random.seed(11)
CSV = "structured_district_data.csv"
OUT = "gold_prompts.jsonl"
SNAP_DIR = "corpus_files/district_data"
SKIP_D = {"Andhra Pradesh PCI"}
YEARS = {"2023-24 (SRE)": "2023-24", "2024-25 (FRE)": "2024-25", "2025-26 (FAE)": "2025-26"}

# metric label in CSV -> (short tag, question template)
NUM_METRICS = {
    "Gross District Domestic Product (GDDP)": ("GDDP", "What is the GDDP of {d} for {y}?"),
    "Net District Domestic Product (NDDP)":   ("NDDP", "What is the NDDP of {d} for {y}?"),
    "Gross District Value Added (GDVA)":       ("GDVA", "What is the GDVA of {d} for {y}?"),
    "Per Capita Income (Rs.)":                 ("PerCapita", "What is the per capita income of {d} in {y}?"),
    "Population ('000)":                        ("Population", "What is the population of {d} in {y}?"),
    "AGRICULTURE & ALLIED SECTOR":             ("AgriSector", "What is the agriculture and allied sector value of {d} in {y}?"),
    "Industry Sector (aggregate)":             ("Industry", "What is the industry sector value of {d} in {y}?"),
    "Services Sector (aggregate)":             ("Services", "What is the services sector value of {d} in {y}?"),
    "Manufacturing":                           ("Manufacturing", "What is the manufacturing sector value of {d} in {y}?"),
    "Construction":                            ("Construction", "What is the construction sector value of {d} in {y}?"),
    "Fishing & Aquaculture":                   ("Fishing", "What is the fishing and aquaculture value of {d} in {y}?"),
    "Horticulture":                            ("Horticulture", "What is the horticulture value of {d} in {y}?"),
    "Mining & Quarrying":                      ("Mining", "What is the mining and quarrying value of {d} in {y}?"),
}
N_NUMERIC = 400

# ---- fixed methodology prompts (judge-graded) ----
METHOD = [
    ("What are the three approaches to estimating GDP?", "production/output approach; income approach; expenditure approach"),
    ("Explain the difference between bottom-up and top-down estimation of GSDP.", "bottom-up builds from district/unit level up; top-down allocates state total down using indicators"),
    ("What is Gross Value Added (GVA) and how does it relate to GDP?", "GVA = output minus intermediate consumption; GDP = GVA + product taxes - product subsidies"),
    ("Which GDP estimation approach is typically used for the agriculture sector?", "production/output approach using crop area and yield"),
    ("How is the services sector output usually estimated?", "income approach / indicator-based; often top-down using employment or value indicators"),
    ("What is the difference between GDDP and NDDP?", "NDDP = GDDP minus depreciation (consumption of fixed capital)"),
    ("What does per capita income represent and how is it derived?", "district income divided by population; NDDP per person"),
    ("What are product taxes and product subsidies in GVA to GDP conversion?", "product taxes added, product subsidies subtracted, to move from GVA to GDP/GDDP"),
    ("Define comparative advantage in the context of a district economy.", "sectors where the district has higher share/rank relative to others"),
    ("What is the production approach to GVA measurement?", "sum of value added across producing units = output minus intermediate inputs"),
    ("Why is the expenditure approach harder to apply at the district level?", "district-level consumption/investment/trade data are scarce; hence production/income preferred"),
    ("What are the revision stages of DDP estimates such as TRE, SRE, FRE, FAE?", "advance/first revised/second revised etc; estimates revised as data matures over years"),
]


def clean_district_display(d):
    return d.title()


def build_numeric(pool):
    for r in csv.DictReader(open(CSV)):
        d = r["district"].strip()
        if d in SKIP_D or r["year"] not in YEARS:
            continue
        m = NUM_METRICS.get(r["sector"].strip())
        if not m:
            continue
        try:
            val = float(r["value_rs_cr"])
        except (ValueError, TypeError):
            continue
        if val < 500:  # avoid tiny numbers that produce false substring matches
            continue
        tag, tmpl = m
        pool.append({
            "category": "numeric", "metric": tag, "district": d.title(),
            "year": YEARS[r["year"]],
            "prompt": tmpl.format(d=clean_district_display(d), y=YEARS[r["year"]]),
            # corpus shows the truncated integer part + 2 decimals (e.g. 42,632.85);
            # accept either the truncated or rounded integer form when grading.
            "target": str(int(val)), "target_alt": str(int(round(val))),
            "reference": None, "grade": "numeric",
        })


def build_profile(items):
    """Judge-graded comparative-advantage prompts from each district snapshot."""
    for path in sorted(glob.glob(os.path.join(SNAP_DIR, "*_Snapshot.txt"))):
        txt = open(path).read()
        d = txt.split("Snapshot:")[1].split("(latest")[0].strip()
        sects = re.findall(r"- ([A-Za-z &.,'()]+?): [\d.]+% of district GVA", txt)
        if len(sects) >= 3:
            ref = "; ".join(s.strip() for s in sects[:3])
            items.append({
                "category": "profile", "metric": "ComparativeAdvantage", "district": d,
                "year": "2025-26", "grade": "judge", "target": None,
                "prompt": f"Which sectors give {d} its strongest comparative advantage?",
                "reference": f"top comparative-advantage sectors: {ref}",
            })


def main():
    numeric = []
    build_numeric(numeric)
    random.shuffle(numeric)
    # stratify: keep roughly even counts per metric up to the cap
    by_metric = {}
    for q in numeric:
        by_metric.setdefault(q["metric"], []).append(q)
    per = max(1, N_NUMERIC // len(by_metric))
    picked = []
    for m, qs in by_metric.items():
        picked.extend(qs[:per])
    random.shuffle(picked)
    picked = picked[:N_NUMERIC]

    conceptual = [{"category": "method", "metric": "Methodology", "district": None,
                   "year": None, "grade": "judge", "target": None,
                   "prompt": q, "reference": ref} for q, ref in METHOD]
    build_profile(conceptual)

    allq = picked + conceptual
    for i, q in enumerate(allq):
        q["id"] = f"g{i:04d}"
    with open(OUT, "w") as f:
        for q in allq:
            f.write(json.dumps(q) + "\n")

    print(f"Wrote {len(allq)} gold prompts -> {OUT}")
    print(f"  numeric (objective): {len(picked)}")
    print(f"  conceptual (judge):  {len(conceptual)}")
    cnt = {}
    for q in allq:
        cnt[q["metric"]] = cnt.get(q["metric"], 0) + 1
    for k in sorted(cnt):
        print(f"    {k:20s} {cnt[k]}")


if __name__ == "__main__":
    main()
