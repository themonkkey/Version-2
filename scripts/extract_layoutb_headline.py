#!/usr/bin/env python3
"""Recover the headline GMDP block for Layout B mandals.

WHY THIS IS SEPARATE FROM extract_mandal_data.py
That script parses PDF *tables* with pdfplumber, and for Layout B it only ever
recovered the sub-sector rows — its Layout B branch explicitly skips any row
beginning "TOTAL", which is exactly where the headline block lives. The block
is present in the PDFs, but it does not survive table extraction cleanly: the
labels wrap across lines and the values often sit on a line of their own.

The text layer does carry it, so this reads `pdftotext -layout` instead and
patches ONLY those mandal JSONs whose `headline` is empty. The 487 Layout A
files are never opened, so there is no way for this to regress them.

WHAT THE LABELS ACTUALLY LOOK LIKE (surveyed across all 57 affected PDFs)
    Total MGVA / TotalMGVA / GMVA          + optional row-number prefix ("21 ")
    Product Taxes / Product taxes / Producttaxes
    Product Subsidies / Product subsidies / ProductSubsidies
    GMDP=(MGVA+Product Taxes -Product Subsidies)   ... or a bare "GMDP"
    NMDP
    Projected Population / ProjectedPopulation / "Projected Popula on"
        (that last one is a pdftotext ligature glitch dropping the "ti")
    PER-CAPITA INCOME(Rs) =(NMDP/Projected Pop) * 100000, and five other spellings

THREE TRAPS THIS HANDLES
  1. A formula literal can share the line with the value:
         "Percapita Income (Rs.)=(NMDP/Projected Pop) *100000   186881"
     Scanning naively yields 100000. Formula text is stripped before any number
     is read.
  2. "Total MGVA  194604  100" carries a trailing percent marker, so the FIRST
     number is the value, not the last.
  3. In a few PDFs the value lands on the line ABOVE a bare label rather than
     on or below it (NMDP and Population in the karapa / ainavilli files).
     Lines below are tried first, then the line above.

NOTHING IS WRITTEN UNLESS IT PROVES ITSELF. Two identities are checked:
      GMDP == MGVA + taxes - subsidies      (within 1%)
      PCI  == NMDP / population * 100000    (within 1%)
A file is only patched if every identity that CAN be computed holds. Anything
that fails is reported and left alone — a gap is better than a wrong figure.

Units match the existing contract: GMVA/GMDP/NMDP in LAKHS (enrich.js divides
by 100 for crore), PCI already in RUPEES, POPULATION a headcount.

Usage:
    python3 scripts/extract_layoutb_headline.py [--write]     # default is dry-run
"""
import json, os, re, subprocess, sys, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "landing", "assets", "mandal_data")
PDFROOT = os.path.join(ROOT, "corpus_files", "vision_documents", "mandal")

# formula text that must go before any number is read off a line
FORMULA = re.compile(
    r"\(\s*NMDP\s*/\s*Projected\s*Pop[a-z ]*\)|\*\s*100000|"
    r"\(\s*MGVA\s*\+\s*Product\s*Taxes?\s*-?\s*Product\s*Subsidies?\s*\)|"
    r"=\s*\(?MGVA[^)]*\)?", re.I)

NUM = re.compile(r"\d[\d,]*\.?\d*")

# label -> regex. Order matters: MGVA must be tried after GMDP so that the
# "GMDP=(MGVA+..." formula line is not mistaken for the MGVA row.
LABELS = [
    ("GMDP",              re.compile(r"^\s*(?:\d{1,2}\s+)?GMDP\b", re.I)),
    ("NMDP",              re.compile(r"^\s*(?:\d{1,2}\s+)?NMDP\b", re.I)),
    ("PRODUCT TAXES",     re.compile(r"^\s*(?:\d{1,2}\s+)?Product\s*taxes\b", re.I)),
    ("PRODUCT SUBSIDIES", re.compile(r"^\s*(?:\d{1,2}\s+)?Product\s*subsidies\b", re.I)),
    ("POPULATION",        re.compile(r"^\s*(?:\d{1,2}\s+)?Projected\s*Popula", re.I)),
    ("PCI",               re.compile(r"^\s*(?:\d{1,2}\s+)?(?:PER[-\s]?CAPITA|Per\s*capita)\s*INCOME", re.I)),
    ("GMVA",              re.compile(r"^\s*(?:\d{1,2}\s+)?(?:Total\s*)?[GM]MVA\b|^\s*(?:\d{1,2}\s+)?Total\s*MGVA\b", re.I)),
]


# A leading 1-2 digit row number ("21 Total MGVA", "22 ProductTaxes") is table
# furniture, not data. Left in, it is read as the value — that is what produced
# nonsense like GMDP=21 and PCI=24 on the first pass.
ROWNUM = re.compile(r"^\s*\d{1,2}(?=\s)")


# Smallest credible value per field, used to reject stray row numbers. Taxes and
# subsidies get a lower bar than the totals — a small mandal can genuinely levy
# only a few hundred lakh — but none of these is ever a two-digit figure.
FLOOR = {
    "GMVA": 1000, "GMDP": 1000, "NMDP": 1000, "PCI": 1000, "POPULATION": 1000,
    "PRODUCT TAXES": 100, "PRODUCT SUBSIDIES": 100,
}


def numbers(line):
    """Numbers on a line, with row-number furniture and formula literals removed."""
    return [float(n.replace(",", ""))
            for n in NUM.findall(FORMULA.sub(" ", ROWNUM.sub(" ", line)))]


def is_label(line):
    return any(rx.search(line) for _, rx in LABELS)


def value_near(lines, i, floor):
    """The figure belonging to the label on line i.

    Same line first (its first number — a trailing '100' is a percent marker,
    not the value), then the next two lines, then the line above: a few PDFs
    stagger the number one row ABOVE a bare label. Neighbouring lines that are
    themselves labels are skipped, since their number belongs to that field.

    `floor` rejects implausible candidates. A stray row number sitting alone on
    its own line survives the ROWNUM strip (nothing follows it to anchor the
    lookahead), and was being read as the value — hence GMDP=21. These figures
    are lakhs, rupees or headcounts; none is a two-digit number.
    """
    for j in (i, i + 1, i + 2, i - 1):
        if not (0 <= j < len(lines)):
            continue
        if j != i and is_label(lines[j]):
            continue
        for n in numbers(lines[j]):
            if n >= floor:
                return n
    return None


def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def find_pdf(slug):
    """Locate a mandal's source PDF from its <constituency>__<mandal> slug."""
    mandal = norm(slug.split("__", 1)[1])
    best = None
    for p in glob.glob(os.path.join(PDFROOT, "**", "*.pdf"), recursive=True):
        if "-2026" in p:                       # the script's existing de-dup rule
            continue
        stem = norm(os.path.basename(p))
        if stem.startswith(mandal):
            # prefer the shortest match, so "Kotananduru" beats "KotananduruExtra"
            if best is None or len(os.path.basename(p)) < len(os.path.basename(best)):
                best = p
    return best


def parse_headline(pdf):
    try:
        txt = subprocess.run(["pdftotext", "-layout", pdf, "-"],
                             capture_output=True, text=True, timeout=120).stdout
    except Exception as e:
        return None, f"pdftotext failed: {e}"
    if not txt.strip():
        return None, "no text layer"
    lines = txt.splitlines()
    out = {}
    for i, ln in enumerate(lines):
        for key, rx in LABELS:
            if key in out:
                continue
            if rx.search(ln):
                v = value_near(lines, i, FLOOR[key])
                if v is not None:
                    out[key] = v
    return (out or None), (None if out else "no headline labels found")


def check(h):
    """Both identities, where computable. Returns (ok, notes)."""
    notes = []
    g, mg = h.get("GMDP"), h.get("GMVA")
    tx, sb = h.get("PRODUCT TAXES"), h.get("PRODUCT SUBSIDIES")
    if None not in (g, mg, tx, sb):
        want = mg + tx - sb
        if abs(want - g) > max(1.0, abs(g) * 0.01):
            notes.append(f"GMDP {g:,.0f} != MGVA+taxes-subsidies {want:,.0f}")
    n, p, pci = h.get("NMDP"), h.get("POPULATION"), h.get("PCI")
    if None not in (n, p, pci) and p:
        want = n / p * 100000
        if abs(want - pci) > max(1.0, abs(pci) * 0.01):
            notes.append(f"PCI {pci:,.0f} != NMDP/pop*1e5 {want:,.0f}")
    return (not notes), notes


def main():
    write = "--write" in sys.argv
    targets = []
    for f in sorted(glob.glob(os.path.join(DATA, "*.json"))):
        if os.path.basename(f).startswith("_"):
            continue
        d = json.load(open(f))
        if not any((d.get("headline") or {}).values()):
            targets.append((f, d))

    print(f"{len(targets)} mandal files with an empty headline\n")
    filled = skipped = nopdf = failed = 0
    problems = []

    for f, d in targets:
        slug = os.path.basename(f)[:-5]
        pdf = find_pdf(slug)
        if not pdf:
            nopdf += 1
            problems.append((slug, "source PDF not found"))
            continue
        h, err = parse_headline(pdf)
        if not h:
            failed += 1
            problems.append((slug, err))
            continue
        ok, notes = check(h)
        if not ok:
            skipped += 1
            problems.append((slug, "; ".join(notes)))
            continue
        got = [k for k in ("GMVA", "GMDP", "NMDP", "POPULATION", "PCI") if k in h]
        if "GMDP" not in h and "GMVA" not in h:
            skipped += 1
            problems.append((slug, "no GMDP or GMVA recovered"))
            continue
        filled += 1
        if write:
            d["headline"] = h
            json.dump(d, open(f, "w"), ensure_ascii=False, separators=(",", ":"))
        print(f"  {'WROTE' if write else 'would fill'} {slug:44} {' '.join(got)}")

    print(f"\nfilled={filled}  rejected={skipped}  no-pdf={nopdf}  parse-failed={failed}")
    if problems:
        print("\n-- left alone (reported, never guessed) --")
        for s, why in problems:
            print(f"  {s:44} {why}")
    if not write:
        print("\ndry run — re-run with --write to apply")


if __name__ == "__main__":
    main()
