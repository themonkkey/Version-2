#!/usr/bin/env python3
"""Build the 'Improving GVA' playbook data from the AP GDDP training dashboard.

Source: ~/Downloads/AP_GDDP_Training_Dashboard (1).html — a self-contained SPA
whose window.APP object carries the DDP Toolbox frameworks already digested into
clean structure (the toolbox .docx itself has font-substitution corruption, e.g.
"GVA fior oťher zervicez", so the HTML is the better source of the same content).

Emits landing/assets/gva_playbook.json:
    groups: [{key, name, blurb, sectors:[{key,title,estimation,pathways,
              actions,policies,indicators:[[name,level,lag,freq,source]]}]}]
    method / leverage / ai_tools / niti  — the narrative blocks

Usage: python3 scripts/build_gva_playbook.py [path/to/dashboard.html]
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser(
    "~/Downloads/AP_GDDP_Training_Dashboard (1).html")
OUT = os.path.join(ROOT, "landing", "assets", "gva_playbook.json")

# Andhra Pradesh reports domestic product on the STATE classification
# (Agriculture / Industry / Services), not the GoI one (Primary / Secondary /
# Tertiary). The two differ in exactly one place: Mining & Quarrying sits in the
# Primary sector for GoI but in the Industry sector for the State. The site's
# district dashboards already use the state grouping (see sectorHue() in
# components.js), so the playbook follows it too — same three names, same
# colourblind-validated hue per group.
STATE_GROUP = {
    "crops": "Agriculture",
    "livestock_fisheries": "Agriculture",
    "forestry": "Agriculture",
    "mining": "Industry",           # <- Primary under GoI, Industry under State
    "manufacturing": "Industry",
    "electricity_utilities": "Industry",
    "construction": "Industry",
    "trade_hotels": "Services",
    "transport_comm": "Services",
    "financial": "Services",
    "real_estate": "Services",
    "public_admin": "Services",
    "other_services": "Services",
}

GROUP_ORDER = ["Agriculture", "Industry", "Services"]

GROUP_META = {
    "Agriculture": (
        "#6FA817",
        "Land, water and what grows on it — where acreage, yield and price "
        "realisation are the levers a district can actually move.",
    ),
    "Industry": (
        "#2B93BF",
        "Extracting, making and building — where formalisation, power reliability "
        "and capital works convert into measurable value added. Includes mining, "
        "which the state classification counts here rather than with agriculture.",
    ),
    "Services": (
        "#BF8A2B",
        "Trade, movement, finance and human capital — the fastest growing share of "
        "most district economies.",
    ),
}


def load_app(path):
    s = open(path, encoding="utf-8", errors="replace").read()
    m = re.search(r"window\.APP\s*=\s*(\{)", s)
    if not m:
        raise SystemExit("window.APP not found in " + path)
    i = m.start(1)
    depth = 0
    for j in range(i, len(s)):
        if s[j] == "{":
            depth += 1
        elif s[j] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(s[i:j + 1])
    raise SystemExit("unbalanced window.APP object")


def main():
    app = load_app(SRC)
    fw, sectors = app["FW"], app["SECTORS"]

    # which GVA sub-sectors each framework covers, for the "counts toward" line
    covers = {}
    for s in sectors:
        if s.get("type") == "sub" and s.get("fw"):
            covers.setdefault(s["fw"], []).append(s["name"])

    unmapped = [k for k in fw if k not in STATE_GROUP]
    if unmapped:
        raise SystemExit("framework(s) missing a state-sector mapping: " + ", ".join(unmapped))

    groups = []
    for gkey in GROUP_ORDER:
        items = []
        for k, f in fw.items():
            if STATE_GROUP[k] != gkey:
                continue
            items.append({
                "key": k,
                "title": f.get("title", k),
                "covers": covers.get(k, f.get("excel_keys", [])),
                "estimation": f.get("estimation", ""),
                "pathways": f.get("pathways", []),
                "actions": f.get("actions", []),
                "policies": f.get("policies", []),
                "indicators": f.get("indicators", []),
            })
        hue, blurb = GROUP_META[gkey]
        groups.append({"key": gkey.lower(), "name": gkey + " sector",
                       "hue": hue, "blurb": blurb, "sectors": items})

    out = {
        "groups": groups,
        "method": {
            "kicker": "The method",
            "title": "How to read your district in 4 steps",
            "steps": [
                ["Open your district's profile.",
                 "Look at GDDP, rank, growth and per-capita income in the district map."],
                ["Find your competitive advantage.",
                 "Compare each sector's share in your district with its share in the state. "
                 "Where your share is higher, you likely have an edge (a Location Quotient above 1)."],
                ["Understand how that GVA is created",
                 "and which pathways raise it — yield, acreage, price realisation, "
                 "formalisation — using the sector playbooks below."],
                ["Pick the administrative levers you control,",
                 "attach a scheme and a monitoring indicator, and act."],
            ],
        },
        "leverage": {
            "kicker": "Why this matters",
            "title": "The district officer's leverage",
            "points": [
                ["You cannot manage what you cannot measure.",
                 "GVA gives a sector-by-sector scorecard for your district."],
                ["Play to strengths.",
                 "Doubling down on a sector where you already lead is faster than "
                 "building one from scratch."],
                ["Small levers compound.",
                 "Timely seed delivery, a faster land-use approval, a cold-chain link "
                 "— each adds measurable GVA."],
                ["Learn from peers.",
                 "The NITI for States portal and AI tools surface what comparable districts did."],
            ],
        },
        "ai_tools": app.get("AI_TOOLS", []),
        "niti": app.get("NITI", []),
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w"), ensure_ascii=False, separators=(",", ":"))
    n = sum(len(g["sectors"]) for g in out["groups"])
    print(f"groups={len(out['groups'])}  sectors={n}")
    for g in out["groups"]:
        print(f"  {g['name']:18} {len(g['sectors'])} sectors")
    print(f"wrote {OUT} ({os.path.getsize(OUT)//1024} KB)")


if __name__ == "__main__":
    main()
