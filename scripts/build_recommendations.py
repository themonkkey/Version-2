#!/usr/bin/env python3
r"""Build district-specialised GVA intervention recommendations.

Prototype scope: KURNOOL ONLY. The schema is level-keyed and district-keyed so
the other 25 districts, and later the constituency and mandal levels, slot in
without a rewrite. See "GENERALISING" at the bottom of this docstring.

Three layers are joined per sector:

  DIAGNOSIS    computed from landing/assets/dist/Kurnool.json. Every figure is
               either copied verbatim from that file or derived by the location
               quotient formula below, which uses only fields already in it.
               Nothing is invented.

  PRESCRIPTION verbatim quotes from the district's own Vision & Action Plan,
               each carrying the PDF page it came from. These are hand-curated
               (KURNOOL_ANCHORS) rather than regexed, because the plan's 30-odd
               department sections use inconsistent headings: the reliable
               "Constraints -> Interventions Proposed" pattern only covers the
               Agriculture section, while Fisheries uses "STRATEGIS FOR
               IMPROVEMENT OF...", Mines uses running prose, and Industry and
               Food Processing use PRESENT/TARGET tables.

  FRAME        a KEY into gva_playbook.json, never a copy, so reshaping the
               playbook cannot fork this content.

The location quotient uses only existing fields:

    state_sector_total = value / (pct_of_state_sector / 100)
    state_total        = sum(state_sector_total)
    state_share_pct    = state_sector_total / state_total * 100
    LQ                 = pct_of_district / state_share_pct

THE PERCENTAGE TRAP: pct_of_district is a sector's share of Kurnool's OWN GDVA.
pct_of_state_sector is Kurnool's share of the STATE total for that sector. They
are different quantities and are never interchangeable. Each is labelled
separately in the output and in the UI.

Every anchor is re-verified against the PDF at build time: the quote must be
found on the page it claims. A drifting anchor fails the build naming the page,
so "hand-verified" is mechanically enforced rather than promised.

HOW THE ANCHORS WERE PRODUCED (repeatable):
    pdftotext -layout <plan.pdf> - | ...            # split on \f for pages
    grep -n "Interventions Proposed"                # 8 blocks, pages 40-53
    grep -n "STRATEGIS\|VISION & GOAL\|Way forward" # the other heading styles
Read each hit, copy the constraint sentence and the intervention list verbatim,
record the PDF page. Tables become figures[] plus a caption quote; a table is
never turned into prose.

Usage:
    python3 scripts/build_recommendations.py            # build + verify, write
    python3 scripts/build_recommendations.py --check    # verify only, no write

GENERALISING: the diagnosis layer needs no change at all, it runs off any
dist/*.json. The mapping tables are already district-agnostic. Only the
prescription layer is Kurnool-specific; replacing KURNOOL_ANCHORS with a tiered
parser (tier 1 the Constraints pattern, tier 2 a per-department heading
registry, tier 3 a PRESENT/TARGET table reader) is the work. Keep the
`extraction` field on every item so machine-extracted content can be marked and
triaged separately from hand-verified content.
"""
import json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "landing", "assets", "dist", "Kurnool.json")
PLAYBOOK = os.path.join(ROOT, "landing", "assets", "gva_playbook.json")
PDF = os.path.join(ROOT, "corpus_files", "vision_documents", "district",
                   "Kurnool", "Kurnool_District_Vision_Action_Plan.pdf")
OUT = os.path.join(ROOT, "landing", "assets", "recommendations.json")

SOURCE_ID = "kurnool_vap"

# The sub-sector names in dist/*.json come from the state GDDP tables and match
# no playbook key. This table is the single join point, and it targets the
# CURRENT playbook shape (Agriculture 3 / Industry 2 / Services 1 merged).
#
# Construction and Electricity map to a null sector: the state classification
# puts both in Industry, but Industry now carries only mining and manufacturing,
# so they keep the Industry framing and simply render without a playbook rather
# than being mis-filed under Services.
SUBSECTOR_TO_PLAYBOOK = {
    "Agriculture":                        ("crops",               "agriculture"),
    "Horticulture":                       ("crops",               "agriculture"),
    "Live stock":                         ("livestock_fisheries", "agriculture"),
    "Fishing & Aquaculture":              ("livestock_fisheries", "agriculture"),
    "Forestry & Logging":                 ("forestry",            "agriculture"),
    "Mining & Quarrying":                 ("mining",              "industry"),
    "Manufacturing":                      ("manufacturing",       "industry"),
    "Electricity, Gas, Water Supply":     (None,                  "industry"),
    "Construction":                       (None,                  "industry"),
    "Trade,Hotel & Restaurants":          ("services",            "services"),
    "Transport by Other means & Storage": ("services",            "services"),
    "Railways":                           ("services",            "services"),
    "Communications":                     ("services",            "services"),
    "Banking & Insurance":                ("services",            "services"),
    "Real est., Ownership of Dwellings":  ("services",            "services"),
    "Public Admn.":                       ("services",            "services"),
    "Other Services":                     ("services",            "services"),
}

# Sub-sectors are grouped into one recommendation per bucket. Keeping Agriculture
# and Horticulture apart from each other (rather than rolling both into `crops`)
# would hide that Horticulture alone is Kurnool's single largest sector, so the
# bucket is the unit a reader can act on, not the playbook key.
# Order here is the CLASSIFICATION order, and it is carried onto each rec as
# `order`. The summary panel sorts by priority, but inside a sector playbook the
# reader is reading a classification ("Crops / Horticulture"), so the blocks
# follow the same sequence as the sector title rather than jumping about.
BUCKETS = [
    ("crops",         "Crops",                     ["Agriculture"]),
    ("horticulture",  "Horticulture",              ["Horticulture"]),
    ("livestock",     "Livestock",                 ["Live stock"]),
    ("fisheries",     "Fishing & Aquaculture",     ["Fishing & Aquaculture"]),
    ("forestry",      "Forestry & Logging",        ["Forestry & Logging"]),
    ("mining",        "Mining & Quarrying",        ["Mining & Quarrying"]),
    ("manufacturing", "Manufacturing",             ["Manufacturing"]),
    ("construction",  "Construction",              ["Construction"]),
    ("electricity",   "Electricity, Gas & Water",  ["Electricity, Gas, Water Supply"]),
    ("trade_hotels",  "Trade, Hotels & Restaurants", ["Trade,Hotel & Restaurants"]),
    ("transport",     "Transport & Storage",       ["Transport by Other means & Storage",
                                                    "Railways"]),
    ("communications", "Communications",           ["Communications"]),
    ("financial",     "Banking & Insurance",       ["Banking & Insurance"]),
    ("real_estate",   "Real Estate & Dwellings",   ["Real est., Ownership of Dwellings"]),
    ("public_admin",  "Public Administration",     ["Public Admn."]),
    ("other_services", "Other Services",           ["Other Services"]),
]

# Pattern thresholds. Named so the rule is auditable rather than buried.
LQ_EDGE = 1.2          # at or above this, the district is specialised in it
LQ_GAP = 0.6           # at or below this, it under-performs the state
GAP_MIN_SHARE = 3.0    # a gap only matters if the sector is big enough to move
EMERGING_GROWTH = 25.0 # fast enough to call it emerging
SHARP_DECLINE = -10.0  # a contraction this steep is news whatever the LQ

SEVERITY = {
    "edge_declining": 3.0,
    "structural_gap": 2.0,
    "declining":      2.0,
    "emerging":       1.5,
    "edge_growing":   1.2,
    "steady":         0.5,
}
PLAN_BONUS = 1.5       # the district's own plan already names this sector

PATTERN_LABEL = {
    "edge_declining": "Strength slipping",
    "structural_gap": "Structural gap",
    "declining":      "Contracting",
    "edge_growing":   "Strength to build on",
    "emerging":       "Emerging",
    "steady":         "Steady",
}

# Expected lead order, frozen so a data refresh that reshuffles priorities is
# noticed rather than silently shipped.
EXPECTED_LEAD = ["horticulture", "crops"]


# ---------------------------------------------------------------- anchors ---
# Hand-curated from the plan. `page` is the PDF page (1-based, as pdftotext
# counts them); the printed folio is 7 lower and is derived at build time.
# `quote` must appear on that page verbatim once whitespace is normalised.
KURNOOL_ANCHORS = [
    # --- Crops / Horticulture -------------------------------------------
    {
        "bucket": "crops", "page": 40, "department": "Agriculture",
        "constraint": "Erratic rainfall",
        "quote": "The volume and distribution of rainfall during the cropping period is very "
                 "uncertain and also unevenly distributed.",
        "interventions": [
            "Avoid mono-cropping and encourage inter-cropping to escape from the risk.",
            "Proper crop planning with respect to prevailing Market prices, Incidences of pests & diseases, water releases etc.",
            "Adoption of low cost technologies",
            "Promotion of Micro irrigation in field crops",
        ],
        "figures": [],
    },
    {
        "bucket": "crops", "page": 40, "department": "Agriculture",
        "constraint": "Small and marginal farm holdings",
        "quote": "In Kurnool District majority of the farmers are small and marginal farmers "
                 "with small holdings below 5 acres.",
        "interventions": [
            "Formation of Clusters / GAP Polam badi",
            "Formation of Crop wise Farmer Producer Organizations(FPO).",
            "Promoting Integrated Farming system by providing small livestock units under subsidy",
            "Promotion of Natural farming like A Grade models, ATM Models, 365 days",
        ],
        "figures": [],
    },
    {
        "bucket": "crops", "page": 40, "department": "Agriculture",
        "constraint": "Barren and fallow lands",
        "quote": "In Kurnool District, nearly 1,53,650 ha of Barren and Fallow lands "
                 "(Current fallow- 90,000 Ha, Other than current fallow (1-5 years) - "
                 "40,793Ha, cultivable waste (>5 years) - 22,857 ha.) are available which "
                 "has to be brought under cultivation.",
        "interventions": [
            "Natural farming: palletization with PMDS",
            "Drought Prone models",
            "365 days",
        ],
        "figures": [
            {"label": "Barren and fallow land", "value": "1,53,650 ha"},
            {"label": "Current fallow", "value": "90,000 Ha"},
            {"label": "Cultivable waste, over 5 years", "value": "22,857 ha"},
        ],
    },
    {
        "bucket": "crops", "page": 41, "department": "Agriculture",
        "constraint": "Indiscriminate use of chemical fertilizers",
        "quote": "Farmers are heavily using Chemical Fertilizer rather it is Indiscriminate "
                 "usage of Fertilizer which will degrade the soil thus effecting the Soil fertility.",
        "interventions": [
            "Soil Testing and Issue of Soil Health Cards (SHC)",
            "Soil Test based Fertilizer usage",
            "Establishment of Vermi compost units",
            "Drone technology for spraying liquid fertilizer.",
        ],
        "figures": [],
    },
    {
        "bucket": "crops", "page": 41, "department": "Agriculture",
        "constraint": "Mono cropping",
        "quote": "In Kurnool District, Majority of farmers cultivate Single crop, particularly "
                 "Long Duration Crop like Cotton, Redgram etc.",
        "interventions": [
            "Intercropping with Pulses & Oil seeds. Ex: Groundnut - Red gram",
            "Cotton Crop diversification to Millets & Maize",
            "To get remunerative price to millets, include Millets in midday meal in Schools, Hostels",
        ],
        "figures": [],
    },
    {
        # The constraint is stated at the foot of page 41 and its interventions
        # run over onto page 42, so the quote is verified against its own page.
        "bucket": "crops", "page": 42, "quote_page": 41, "department": "Agriculture",
        "constraint": "Low market price at harvest",
        "quote": "Farmers are getting low market price at the time of harvest and the farmers "
                 "are left with no choice but to sell as the agriculture produce is perishable.",
        "interventions": [
            "Construction of Cold storages",
            "Value addition of Agricultural Produce by encouraging Millet Processing units Dal Mills, Oil extractors, flour mills",
            "Split Bengal gram or Redgram dal, Rice markets through FPO",
        ],
        "figures": [],
    },
    {
        "bucket": "horticulture", "page": 48, "department": "Horticulture",
        "constraint": "Crop clusters and major interventions to 2029 and 2047",
        "quote": "Horticulture Crop Clusters & Major Interventions for Viksit AP for 2029 & 2047",
        "interventions": [
            "Promotion of varieties suitable for storage",
            "Storage Structures/Solar dehydration units.",
            "Primary Collection Centres.",
            "Cold Storages.",
            "Ripening Chambers.",
        ],
        "figures": [
            {"label": "Onion production now", "value": "2,14,815"},
            {"label": "Onion production by 2029", "value": "3,35,818"},
            {"label": "Chilli production now", "value": "2,69,910"},
            {"label": "Tomato production by 2029", "value": "1,68,420"},
        ],
    },
    {
        "bucket": "horticulture", "page": 53, "department": "Micro Irrigation (APMIP)",
        "constraint": "Micro irrigation coverage",
        "quote": "All crops which are cultivated under Bore wells/Open well irrigation "
                 "invariably brought under Micro Irrigation.",
        "interventions": [
            "Integration of Lift Irrigation schemes with community Drip.",
            "Micro Irrigation should be made mandatory for water intensive crops",
            "Low cost automation system for small holdings.",
            "Training to local unemployment youth as micro irrigation technician",
        ],
        "figures": [
            {"label": "Micro irrigation area now", "value": "34,137"},
            {"label": "Micro irrigation target 2028-29", "value": "1,13,503"},
        ],
    },
    # --- Fisheries -------------------------------------------------------
    {
        "bucket": "fisheries", "page": 62, "department": "Fisheries",
        "constraint": "Raising inland fish production",
        "quote": "STRATEGIS FOR IMPROVEMENT OF FISH PRODUCTION",
        "interventions": [
            "Enhancing of fish production and Prawn Production by expansion of aquaculture area",
            "By Adoption of Advance technologies like cage culture, Re- Circulatory Aquaculture System and Bio-Flock.",
            "Implementation of Ban period in Reservoirs for the month of July and August for every year",
            "Construction Captive nurseries nearby water bodies for rearing of spawn",
        ],
        "figures": [
            {"label": "Fish and prawn production 2023-24", "value": "24914 MTs"},
            {"label": "Inland fish production target 2028-29", "value": "54008"},
        ],
    },
    {
        "bucket": "fisheries", "page": 62, "department": "Fisheries",
        "constraint": "Expanding aquaculture area",
        "quote": "There is 631.79 Acres of Aquaculture area is existing in Adoni division of "
                 "Kurnool District",
        "interventions": [
            "Creating of awareness to the aqua farmers for conversion of non agriculture lands to fish ponds.",
            "Issue of license to the un registered aquaculture ponds as per APSADA act in the District.",
        ],
        "figures": [
            {"label": "Existing aquaculture area, Adoni division", "value": "631.79 Acres"},
            {"label": "Extent still to be licensed", "value": "194.82 Acres"},
        ],
    },
    # --- Forestry --------------------------------------------------------
    {
        "bucket": "forestry", "page": 65, "department": "Forest",
        "constraint": "Raising green cover outside reserved forest",
        "quote": "Raising nurseries based on the availability of the budget for distribution to "
                 "the Public and other line departments.",
        "interventions": [
            "Raising nurseries based on the availability of the budget for distribution to the Public and other line departments.",
            "Providing technical guidance for planting and maintenance to all the stakeholders.",
            "Raising seedlings by other line departments like DWMA, Horticulture, Sericulture, Agricultures etc.",
            "Ensuring the survival of seedlings planted.",
        ],
        "figures": [],
    },
    # --- Mining ----------------------------------------------------------
    {
        "bucket": "mining", "page": 89, "department": "Mines",
        "constraint": "Low grade iron ore at Veldurthy goes unbeneficiated",
        "quote": "There is a scope for establishment of Iron ore beneficiation plant along with "
                 "crushing unit",
        "interventions": [
            "Mineral Beneficiation Industry and setting up of fresher",
            "establishment of Iron ore beneficiation plant along with crushing unit",
        ],
        "figures": [
            {"label": "Estimated investment", "value": "Rs.100.00 cores"},
            {"label": "Employment, direct", "value": "100"},
            {"label": "Employment, indirect", "value": "250"},
        ],
    },
    {
        "bucket": "mining", "page": 89, "department": "Mines",
        "constraint": "Granite cutting and polishing units lie closed",
        "quote": "There were 25 Granite cutting and Polishing units existing in Adoni "
                 "surroundings which are not working at present",
        "interventions": [
            "If the Government provided incentives (Viz., reduction of royalty)",
            "resumption of Granite cutting and polishing units existing in Kurnool District resulting Employment generation",
        ],
        "figures": [
            {"label": "Units closed", "value": "25"},
            {"label": "Estimated reinvestment", "value": "Rs.25.00 cores"},
        ],
    },
    # --- Manufacturing ---------------------------------------------------
    {
        "bucket": "manufacturing", "page": 90, "department": "Food Processing",
        "constraint": "Perishable produce is lost to price swings at harvest",
        "quote": "Processing of vegetables and Spices has huge scope in the district, it "
                 "increases the shelf-life of the produce",
        "interventions": [
            "these vegetables can be processed through proven dehydration technology and well preserved.",
            "there is a need to establish small to medium scale integrated processing unit for vegetable/spices potential clusters in the district.",
        ],
        "figures": [
            {"label": "Processing units now", "value": "177"},
            {"label": "Processing units target 2028-29", "value": "1787"},
        ],
    },
    {
        "bucket": "manufacturing", "page": 68, "department": "Industry",
        "constraint": "MSME and large industry targets to 2028-29",
        "quote": "INDUSTRY",
        "interventions": [],
        "figures": [
            {"label": "MSME units, 2024-25 target", "value": "6000"},
            {"label": "MSME units, 2028-29 target", "value": "12540"},
            {"label": "MSME employment, 2028-29 target", "value": "16705"},
        ],
    },
    # --- Services --------------------------------------------------------
    {
        "bucket": "trade_hotels", "page": 141, "department": "Tourism & Culture",
        "constraint": "Tourism value is not converted into local economic linkage",
        "quote": "Encourage participative tourism where local communities participate and gain",
        "interventions": [
            "Bring in awareness of the industry about potential for employment and economic development.",
            "Encourage participative tourism where local communities participate and gain",
            "Generate responsible tourism due to which industry will be responsible, to its environment",
            "Involve the local communities near by the attractions and develop the meaningful economic linkages.",
        ],
        "figures": [],
    },
]


# ------------------------------------------------------------- utilities ---
def norm(s):
    """Normalise for comparison: collapse whitespace and fold the dash and quote
    glyphs the PDF uses (en dash, curly apostrophe) onto ASCII."""
    s = (s.replace("–", "-").replace("—", "-").replace("’", "'")
          .replace("‘", "'").replace("“", '"').replace("”", '"'))
    return re.sub(r"\s+", " ", s).strip()


def pdf_pages():
    if not os.path.exists(PDF):
        sys.exit("missing source PDF: " + PDF)
    out = subprocess.run(["pdftotext", "-layout", PDF, "-"],
                         capture_output=True).stdout.decode("utf-8", "replace")
    return out.split("\f")


def folio_of(page_text):
    """The printed folio is the last bare number on the page. Derived rather
    than hardcoded so it cannot drift out of step with `page`."""
    nums = re.findall(r"^\s*(\d{1,3})\s*$", page_text, re.M)
    return int(nums[-1]) if nums else None


def fmt(x, n=2):
    return round(x, n)


# ------------------------------------------------------------ diagnosis ----
def diagnose(dist):
    """Per sub-sector: LQ plus the inputs it was derived from."""
    rows = {}
    usable = [s for s in dist["sectors"] if s.get("pct_of_state_sector")]
    state_totals = {}
    for s in usable:
        # WHY: pct_of_state_sector is Kurnool's share of the STATE total for
        # this sector, so dividing the district value by it recovers that state
        # total. No external state file is needed and nothing is assumed.
        state_totals[s["name"]] = s["value"] / (s["pct_of_state_sector"] / 100.0)
    state_total = sum(state_totals.values())

    for s in usable:
        st = state_totals[s["name"]]
        state_share = st / state_total * 100.0
        rows[s["name"]] = {
            "value": s["value"],
            "pct_of_district": s["pct_of_district"],
            "pct_of_state_sector": s["pct_of_state_sector"],
            "growth": s["growth"],
            "rank": s["rank"],
            "state_sector_total": st,
            "state_share_pct": state_share,
            "lq": s["pct_of_district"] / state_share,
        }
    return rows, state_total


def classify(lq, growth, share):
    """Order matters. A sector the district is specialised in AND losing is the
    worst case, so it is tested first. A sharp contraction is tested before the
    structural-gap rule because a sector can be small enough to fall under
    GAP_MIN_SHARE and still be collapsing, and calling that "steady" would be
    plainly wrong. Growth is tested before the LQ-only rules for the same
    reason: a sector growing 50 percent is not steady at any LQ."""
    if lq >= LQ_EDGE and growth < 0:
        return "edge_declining"
    if growth <= SHARP_DECLINE:
        return "declining"
    if lq <= LQ_GAP and share >= GAP_MIN_SHARE:
        return "structural_gap"
    if growth >= EMERGING_GROWTH:
        return "emerging"
    if lq >= LQ_EDGE:
        return "edge_growing"
    return "steady"


def sentence(label, share, state_share, lq, growth):
    edge = ("above" if lq > 1 else "below") + " the state"
    move = ("grew %.2f percent" % growth) if growth >= 0 else ("contracted %.2f percent" % abs(growth))
    return ("%s is %.2f percent of Kurnool's own GDVA against %.2f percent for the state, "
            "a location quotient of %.2f, %s. It %s in the latest year."
            % (label, share, state_share, lq, edge, move))


# ---------------------------------------------------------------- build ----
def main():
    check = "--check" in sys.argv

    with open(DIST, encoding="utf-8") as fh:
        dist = json.load(fh)

    # How many districts a sector rank is out of. Counted from the dist/ files
    # that produce those ranks rather than written down, because the number has
    # changed with state reorganisation and a hardcoded one silently goes stale.
    districts_total = len([f for f in os.listdir(os.path.dirname(DIST))
                           if f.endswith(".json")])
    with open(PLAYBOOK, encoding="utf-8") as fh:
        playbook = json.load(fh)
    valid_keys = {s["key"] for g in playbook["groups"] for s in g["sectors"]}

    # Every sector name must be known, or the mapping has silently gone stale.
    for s in dist["sectors"]:
        if s["name"] not in SUBSECTOR_TO_PLAYBOOK:
            sys.exit("unmapped sector name in dist/Kurnool.json: %r" % s["name"])

    rows, state_total = diagnose(dist)

    # --- verify every anchor against the PDF page it claims ---------------
    pages = pdf_pages()
    anchors_by_bucket = {}
    for a in KURNOOL_ANCHORS:
        p = a["page"]
        if p < 1 or p > len(pages):
            sys.exit("anchor page %d out of range (pdf has %d pages)" % (p, len(pages)))
        hay = norm(pages[p - 1])
        # A constraint and its interventions can straddle a page break, so the
        # quote may be verified against a different page from the bullets.
        qp = a.get("quote_page", p)
        qhay = norm(pages[qp - 1]) if qp != p else hay
        if norm(a["quote"]) not in qhay:
            sys.exit("anchor quote NOT FOUND on pdf page %d (%s / %s):\n  %s"
                     % (qp, a["bucket"], a["constraint"], a["quote"][:90]))
        for iv in a["interventions"]:
            if norm(iv) not in hay:
                sys.exit("intervention NOT FOUND on pdf page %d (%s):\n  %s"
                         % (p, a["constraint"], iv[:90]))
        for f in a["figures"]:
            if norm(f["value"]) not in hay:
                sys.exit("figure %r NOT FOUND on pdf page %d (%s)"
                         % (f["value"], p, a["constraint"]))
        a["_folio"] = folio_of(pages[p - 1])
        anchors_by_bucket.setdefault(a["bucket"], []).append(a)

    # --- assemble one rec per bucket --------------------------------------
    recs = []
    for border, (bkey, label, names) in enumerate(BUCKETS):
        parts = [rows[n] for n in names if n in rows]
        if not parts:
            continue
        share = sum(p["pct_of_district"] for p in parts)
        value = sum(p["value"] for p in parts)
        st = sum(p["state_sector_total"] for p in parts)
        state_share = st / state_total * 100.0
        lq = share / state_share
        # WHY no combined growth figure: growth is a rate, and the source gives
        # no prior-year values to weight it by, so a bucket of two sub-sectors
        # reports each one's growth rather than inventing an average.
        growths = [{"name": n, "growth": rows[n]["growth"], "rank": rows[n]["rank"]}
                   for n in names if n in rows]
        lead_growth = growths[0]["growth"]
        lead_rank = growths[0]["rank"]

        pattern = classify(lq, lead_growth, share)
        pres = anchors_by_bucket.get(bkey, [])
        priority = share * SEVERITY[pattern] * (PLAN_BONUS if pres else 1.0)

        sec_key, grp_key = SUBSECTOR_TO_PLAYBOOK[names[0]]
        if sec_key is not None and sec_key not in valid_keys:
            sys.exit("playbook key %r not in gva_playbook.json" % sec_key)

        recs.append({
            "id": "kurnool-" + bkey,
            "bucket": bkey,
            "order": border,          # classification order, see BUCKETS
            "label": label,
            "sub_sectors": names,
            "pattern": pattern,
            "pattern_label": PATTERN_LABEL[pattern],
            "playbook_sector": sec_key,
            "playbook_group": grp_key,
            "priority": fmt(priority, 3),
            "diagnosis": {
                "value_rs_cr": fmt(value, 2),
                "share_of_district_pct": fmt(share),
                "state_share_pct": fmt(state_share),
                "lq": fmt(lq),
                "growth_pct": fmt(lead_growth),
                "rank_among_districts": lead_rank,
                "per_sub_sector": growths,
                "sentence": sentence(label, share, state_share, lq, lead_growth),
            },
            "prescription": [{
                "source": SOURCE_ID,
                "page": a["page"],
                "folio": a["_folio"],
                "department": a["department"],
                "constraint": a["constraint"],
                "quote": a["quote"],
                "interventions": a["interventions"],
                "figures": a["figures"],
                "extraction": "anchored",
            } for a in pres],
        })

    recs.sort(key=lambda r: (-r["priority"], -r["diagnosis"]["share_of_district_pct"]))
    for i, r in enumerate(recs, 1):
        r["rank"] = i

    lead = [r["bucket"] for r in recs[:len(EXPECTED_LEAD)]]
    if lead != EXPECTED_LEAD:
        sys.exit("lead order changed: expected %s, got %s. If the data legitimately "
                 "moved, update EXPECTED_LEAD deliberately." % (EXPECTED_LEAD, lead))

    out = {
        "_note": "Diagnosis is computed from landing/assets/dist/<District>.json. "
                 "Prescriptions are verbatim quotes from the district's own Vision & "
                 "Action Plan, each verified against the cited PDF page at build time. "
                 "Nothing here is authored.",
        "version": "2026-08-17",
        "sources": {
            SOURCE_ID: {
                "title": "Kurnool District Vision & Action Plan",
                "path": os.path.relpath(PDF, ROOT),
                "pages": len(pages),
            }
        },
        "levels": {
            "district": {
                "Kurnool": {
                    "name": "Kurnool",
                    "coverage": "prototype",
                    "data_year": dist.get("latest_year"),
                    "data_source": dist.get("source"),
                    "districts_total": districts_total,
                    "state_basis": {
                        "method": "state_sector_total = value / (pct_of_state_sector/100); "
                                  "state_total = sum(state_sector_total); "
                                  "state_share_pct = state_sector_total / state_total * 100; "
                                  "lq = pct_of_district / state_share_pct",
                        "state_total_rs_cr": fmt(state_total, 0),
                        "caution": "pct_of_district is a sector's share of the district's own "
                                   "GDVA. pct_of_state_sector is the district's share of the "
                                   "state total for that sector. They are not interchangeable.",
                    },
                    "recs": recs,
                }
            }
        },
    }

    blob = json.dumps(out, ensure_ascii=False)
    if "—" in blob:
        sys.exit("em dash found in output; the project style forbids it")

    # The recompute-by-hand sheet: everything the panel shows traces to a row here.
    print("%-36s %8s %8s %6s %8s %5s" % ("sub-sector", "dist%", "state%", "LQ", "growth", "rank"))
    for name, r in sorted(rows.items(), key=lambda kv: -kv[1]["lq"]):
        print("%-36s %8.2f %8.2f %6.2f %8.2f %5.0f"
              % (name[:36], r["pct_of_district"], r["state_share_pct"],
                 r["lq"], r["growth"], r["rank"]))
    print("\nderived state GDVA total: Rs %s crore" % format(int(state_total), ","))
    print("\n%-5s %-16s %-18s %7s %6s %s" % ("rank", "bucket", "pattern", "share%", "LQ", "cites"))
    for r in recs:
        print("%-5d %-16s %-18s %7.2f %6.2f %d"
              % (r["rank"], r["bucket"], r["pattern"],
                 r["diagnosis"]["share_of_district_pct"], r["diagnosis"]["lq"],
                 len(r["prescription"])))

    n_anchor = sum(len(r["prescription"]) for r in recs)
    covered = sum(1 for r in recs if r["prescription"])
    print("\n%d recommendations, %d with prescriptions, %d anchors verified against the PDF"
          % (len(recs), covered, n_anchor))

    if check:
        print("\n--check: verified, nothing written")
        return

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print("wrote", os.path.relpath(OUT, ROOT))


if __name__ == "__main__":
    main()
