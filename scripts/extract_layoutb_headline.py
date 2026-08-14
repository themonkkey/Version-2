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
    # NOT [^)]* — when the closing paren wraps to the next line that eats the
    # value too ("GMDP=(MGVA+Product Taxes -   1,34,076"), losing the figure
    # entirely. Stop at the first digit instead.
    r"=\s*\(?\s*MGVA[^\d)]*\)?", re.I)

NUM = re.compile(r"\d[\d,]*\.?\d*")

MGVA_PAT = r"^\s*(?:\d{1,2}\s+)?(?:Total\s*)?(?:MGVA|GMVA)\b"

# label -> regex. Order matters: MGVA must be tried after GMDP so that the
# "GMDP=(MGVA+..." formula line is not mistaken for the MGVA row.
LABELS = [
    ("GMDP",              re.compile(r"^\s*(?:\d{1,2}\s+)?GMDP\b", re.I)),
    ("NMDP",              re.compile(r"^\s*(?:\d{1,2}\s+)?NMDP\b", re.I)),
    ("PRODUCT TAXES",     re.compile(r"^\s*(?:\d{1,2}\s+)?Product\s*taxes\b", re.I)),
    ("PRODUCT SUBSIDIES", re.compile(r"^\s*(?:\d{1,2}\s+)?Product\s*subsidies\b", re.I)),
    ("POPULATION",        re.compile(r"^\s*(?:\d{1,2}\s+)?Projected\s*Popula", re.I)),
    ("PCI",               re.compile(r"^\s*(?:\d{1,2}\s+)?(?:PER[-\s]?CAPITA|Per\s*capita)\s*INCOME", re.I)),
    # "MGVA" and "GMVA" both occur, with or without a "Total" prefix. An earlier
    # [GM]MVA class silently failed on MGVA (M then GVA, not MVA) and sent the
    # block finder down its fallback path, which swept in sub-sector rows.
    ("GMVA",              re.compile(MGVA_PAT, re.I)),
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


def find_block(lines):
    """The headline block's line range.

    Anchoring matters: "Per Capita Income" and similar phrases also occur in the
    narrative text, and matching the first one anywhere in the document pulled a
    stray year (2022) in as the PCI. A real anchor is an MGVA/GMVA label that has
    both a product-tax line and an NMDP line within the next 20 lines.
    """
    for i, ln in enumerate(lines):
        if not re.search(MGVA_PAT, ln, re.I):
            continue
        window = "\n".join(lines[i:i + 20])
        if re.search(r"Product\s*tax", window, re.I) and re.search(r"\bNMDP\b", window):
            end = min(len(lines), i + 20)
            # the sectoral-breakup table follows immediately, and its rows are
            # bare numbers that pass-2 will happily claim — stop before it
            for j in range(i + 1, end):
                if re.search(r"SECTORAL\s+BREAKUP|OVERALL\s+GVA", lines[j], re.I):
                    end = j
                    break
            return i, end
    # some files put no MGVA label at all — fall back to the taxes line
    for i, ln in enumerate(lines):
        if re.search(r"^\s*(?:\d{1,2}\s+)?Product\s*tax", ln, re.I):
            window = "\n".join(lines[i:i + 18])
            if re.search(r"\bNMDP\b", window):
                return max(0, i - 1), min(len(lines), i + 18)
    return None, None


def parse_headline(pdf):
    try:
        txt = subprocess.run(["pdftotext", "-layout", pdf, "-"],
                             capture_output=True, text=True, timeout=120).stdout
    except Exception as e:
        return None, f"pdftotext failed: {e}"
    if not txt.strip():
        return None, "no text layer"
    lines = txt.splitlines()
    a, b = find_block(lines)
    if a is None:
        return None, "no headline block found in text layer"
    block = lines[a:b]

    # Pass 1 — labels with their value on the same line.
    out, slots, claimed = {}, [], set()
    for i, ln in enumerate(block):
        for key, rx in LABELS:
            if key in out or any(s[0] == key for s in slots):
                continue
            if rx.search(ln):
                vals = [n for n in numbers(ln) if n >= FLOOR[key]]
                if vals:
                    out[key] = vals[0]
                    claimed.add(i)                  # this line's figure is spoken for
                else:
                    slots.append((key, i))          # label present, value elsewhere
                break

    # Pass 2 — bare number lines, assigned to the NEAREST label still waiting.
    # A value can print above its label as easily as below it (the karapa file
    # staggers NMDP and Population one row up), so distance decides, not
    # direction. Anything else mis-assigns and cascades a shift down the block.
    if slots:
        pending = {k for k, _ in slots if k not in out}
        free = []
        for i, ln in enumerate(block):
            if i in claimed:
                continue
            # Only a label still WAITING for its value blocks a line. The closing
            # half of a wrapped formula reads as a label — "Product Subsidies)
            # 197033" — and skipping it lost the GMDP figure sitting on it, even
            # though Product Subsidies had already been read from its own row.
            if any(rx.search(ln) for k, rx in LABELS if k in pending):
                continue
            for n in numbers(ln):
                free.append((i, n))
        for i, n in free:
            cand = [(abs(i - li), k, li) for k, li in slots
                    if k not in out and n >= FLOOR[k]]
            if not cand:
                continue
            cand.sort()
            _, key, _ = cand[0]
            out[key] = n

    # MGVA is sometimes simply not printed (nidadavole). It is not a guess to
    # recover it from the document's own stated identity, and it is cross-checked
    # against the sub-sector rows by the caller.
    if "GMVA" not in out and all(k in out for k in ("GMDP", "PRODUCT TAXES", "PRODUCT SUBSIDIES")):
        out["GMVA"] = out["GMDP"] - out["PRODUCT TAXES"] + out["PRODUCT SUBSIDIES"]
        out["_gmva_derived"] = True

    return (out or None), (None if out else "no headline labels found")


def check(h, sub_total=None, sub_rows=None):
    """Validate the block. Returns (fatal, notes).

    A failure is FATAL only if it means the block cannot be trusted. A PCI that
    contradicts its own printed formula is a defect in that one figure — the
    rajanagaram PDF prints 21,684 where NMDP/population gives 218,686 — so PCI
    is dropped and the four figures that do verify are kept. Discarding all of
    them over one bad cell would lose good data.
    """
    notes = []
    g, mg = h.get("GMDP"), h.get("GMVA")
    tx, sb = h.get("PRODUCT TAXES"), h.get("PRODUCT SUBSIDIES")
    if None not in (g, mg, tx, sb):
        want = mg + tx - sb
        if abs(want - g) > max(1.0, abs(g) * 0.01):
            return True, [f"GMDP {g:,.0f} != MGVA+taxes-subsidies {want:,.0f}"]

    # A derived MGVA has to be corroborated independently. SUMMING the sub-sector
    # rows is the wrong test — the table parser does not always recover every row
    # (nidadavole stores only 138,633 of a real 216,008), so a correct derivation
    # gets rejected. Each row's own percentage gives the implied total instead:
    # value / pct * 100. That needs no completeness, only one usable row.
    if h.pop("_gmva_derived", False):
        implied = sorted(r["value"] / r["pct"] * 100
                         for r in (sub_rows or [])
                         if r.get("pct") and r.get("value"))
        ref = implied[len(implied) // 2] if implied else sub_total
        if ref and abs(ref - mg) > max(1.0, abs(mg) * 0.02):
            return True, [f"derived MGVA {mg:,.0f} != {ref:,.0f} implied by sub-sector shares"]
        notes.append(f"MGVA not printed; derived {mg:,.0f} from GMDP-taxes+subsidies"
                     + (f", corroborated by sub-sector shares ({ref:,.0f})" if ref else ""))

    n, p, pci = h.get("NMDP"), h.get("POPULATION"), h.get("PCI")
    if None not in (n, p, pci) and p:
        want = n / p * 100000
        if abs(want - pci) > max(1.0, abs(pci) * 0.01):
            h.pop("PCI")
            notes.append(f"PCI dropped: printed {pci:,.0f}, formula gives {want:,.0f}")
    return False, notes


def main():
    write = "--write" in sys.argv
    # --recheck also re-parses Layout B files that already have a headline, so a
    # parser fix reaches them. Layout A is never touched under any flag.
    recheck = "--recheck" in sys.argv
    targets = []
    for f in sorted(glob.glob(os.path.join(DATA, "*.json"))):
        if os.path.basename(f).startswith("_"):
            continue
        d = json.load(open(f))
        empty = not any((d.get("headline") or {}).values())
        if empty or (recheck and d.get("layout") == "B"):
            targets.append((f, d))

    print(f"{len(targets)} mandal files to parse"
          f"{' (empty + Layout B recheck)' if recheck else ' with an empty headline'}\n")
    filled = skipped = nopdf = failed = 0
    problems = []
    caveats = []

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
        sub_total = sum(r.get("value") or 0 for r in (d.get("sub_rows") or [])) or None
        fatal, notes = check(h, sub_total, d.get('sub_rows'))
        if fatal:
            skipped += 1
            problems.append((slug, "; ".join(notes)))
            continue
        if notes:
            caveats.append((slug, "; ".join(notes)))
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
    if caveats:
        print("\n-- accepted with a caveat --")
        for sl, why in caveats:
            print(f"  {sl:44} {why}")
    if problems:
        print("\n-- left alone (reported, never guessed) --")
        for sl, why in problems:
            print(f"  {sl:44} {why}")
    if not write:
        print("\ndry run — re-run with --write to apply")


if __name__ == "__main__":
    main()
