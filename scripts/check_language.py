#!/usr/bin/env python3
"""Language guard for the dashboard: one engine, every user-facing surface.

Sweeps the copy a reader can actually meet - page text and attributes in the
HTML, prose string literals inside the inline scripts, and every string value
in the copy-bearing JSON assets - and flags:

  em-dash    an em dash in prose (site rule: colon, comma, semicolon, middot)
  spelling   US spellings on a British-English site (program, center, -ize...)
  flagged    words PIF has asked to retire (e.g. 'taught')
  typo       common misspellings (recieve, seperate, capapcity...)

CSS never reaches a reader and is skipped wholesale; script code is skipped
except for its quoted strings that look like prose. Exceptions live in
scripts/language_allow.txt, one regex per line - a finding whose line matches
any of them is suppressed.

Usage:
  python3 scripts/check_language.py            report findings
  python3 scripts/check_language.py --check    exit 1 if anything is found
"""
import json, re, sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAND = ROOT / "landing"
ALLOW = Path(__file__).resolve().parent / "language_allow.txt"

HTML_FILES = [LAND / "index.html"] + \
    sorted((LAND / "cases").glob("*.html")) + \
    sorted((LAND / "capacity").glob("*.html"))

JSON_FILES = [
    LAND / "assets" / "suggested_interventions.json",
    LAND / "assets" / "gva_playbook.json",
    LAND / "assets" / "recommendations.json",
    LAND / "assets" / "i18n" / "en.json",
]

# ── rules ────────────────────────────────────────────────────────────────────
# (kind, compiled regex, note). Word-boundary, case-insensitive prose checks.
def w(p): return re.compile(r"\b(" + p + r")\b", re.I)

RULES = [
    ("em-dash",  re.compile("—"), "use colon / comma / semicolon / middot"),
    ("flagged",  w(r"taught"), "PIF: say 'discussed' or 'delivered'"),
    # US spellings on a British-English site
    ("spelling", w(r"programs?"), "programme"),
    ("spelling", w(r"centers?"), "centre"),
    ("spelling", w(r"organi[zs]?ations?'?s?|organized?|organizing"), "organisation / organised"),
    ("spelling", w(r"analyzed?|analyzing|analyzes"), "analyse"),
    ("spelling", w(r"digitized?|digitizing"), "digitise"),
    ("spelling", w(r"summarized?|summarizing"), "summarise"),
    ("spelling", w(r"prioritized?|prioritizing"), "prioritise"),
    ("spelling", w(r"utilized?|utilizing|utilization"), "utilise / utilisation"),
    ("spelling", w(r"labor"), "labour"),
    ("spelling", w(r"favorable"), "favourable"),
    ("spelling", w(r"modernized?|modernizing|modernization"), "modernise"),
    ("spelling", w(r"formalized?|formalizing|formalization"), "formalise"),
    ("spelling", w(r"mechanized?|mechanizing|mechanization"), "mechanise"),
    # common typos
    ("typo", w(r"teh|recieve[ds]?|seperate[ds]?|occured|accomodate[ds]?|"
               r"definately|goverment|enviroment|acheive[ds]?|untill|"
               r"capapcity|capactiy|buiding|distict|disctrict|programe|"
               r"intervension|assesment|feild|managment"), "typo"),
]

# organisation is fine; the regex above catches only the z-forms via review:
RULES[4] = ("spelling", w(r"organized?|organizing|organization"), "organise / organisation")

def allow_patterns():
    if not ALLOW.exists(): return []
    pats = []
    for ln in ALLOW.read_text().splitlines():
        ln = ln.strip()
        if ln and not ln.startswith("#"):
            pats.append(re.compile(ln))
    return pats

ALLOWED = allow_patterns()

def allowed(line_text):
    return any(p.search(line_text) for p in ALLOWED)

# ── HTML extraction ──────────────────────────────────────────────────────────
PROSE_ATTRS = {"title", "alt", "aria-label", "placeholder", "data-t"}
STR_RE = re.compile(r"'((?:[^'\\]|\\.)*)'|\"((?:[^\"\\]|\\.)*)\"")

def looks_like_prose(s):
    # a quoted JS string worth checking: has a space and some letters,
    # and is not markup-ish css/selector/url noise
    if len(s) < 8 or " " not in s: return False
    if not re.search(r"[A-Za-z]{3}", s): return False
    if re.match(r"^[.#\[]|^https?:|^assets/|^\s*<\w+[^>]*>$", s): return False
    return True

class Extractor(HTMLParser):
    """Yields (line, text) pairs for reader-visible text."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []            # (lineno, text)
        self.skip = 0            # inside <style>
        self.in_script = 0
    def handle_starttag(self, tag, attrs):
        if tag == "style": self.skip += 1
        if tag == "script": self.in_script += 1
        for k, v in attrs:
            if k in PROSE_ATTRS and v and len(v) > 2:
                self.out.append((self.getpos()[0], v))
    def handle_endtag(self, tag):
        if tag == "style": self.skip = max(0, self.skip - 1)
        if tag == "script": self.in_script = max(0, self.in_script - 1)
    def handle_data(self, data):
        line = self.getpos()[0]
        if self.skip: return
        if self.in_script:
            # check only the prose-looking string literals, minus comments;
            # block comments are blanked first, newlines kept so lines hold
            data = re.sub(r"/\*.*?\*/",
                          lambda m: "\n" * m.group(0).count("\n"), data,
                          flags=re.S)
            for i, raw in enumerate(data.splitlines()):
                code = re.sub(r"(^|\s)//.*$", "", raw)
                for m in STR_RE.finditer(code):
                    s = m.group(1) or m.group(2) or ""
                    if looks_like_prose(s):
                        self.out.append((line + i, s))
            return
        if data.strip():
            for i, t in enumerate(data.splitlines()):
                if t.strip(): self.out.append((line + i, t.strip()))

def scan_text(findings, where, line, text):
    for kind, rx, note in RULES:
        m = rx.search(text)
        if m and not allowed(text):
            snippet = text.strip()
            if len(snippet) > 90:
                a = max(0, m.start() - 35)
                snippet = ("…" if a else "") + snippet[a:a + 80] + "…"
            findings.append((where, line, kind, m.group(0), note, snippet))

def scan_html(findings, path):
    ex = Extractor()
    ex.feed(path.read_text(encoding="utf-8", errors="replace"))
    rel = str(path.relative_to(ROOT))
    for line, text in ex.out:
        scan_text(findings, rel, line, text)

def scan_json(findings, path):
    rel = str(path.relative_to(ROOT))
    def walk(node, keypath):
        if isinstance(node, dict):
            for k, v in node.items(): walk(v, keypath + "." + str(k))
        elif isinstance(node, list):
            for i, v in enumerate(node): walk(v, keypath + "[%d]" % i)
        elif isinstance(node, str) and len(node) > 3:
            scan_text(findings, rel + keypath, 0, node)
    walk(json.loads(path.read_text(encoding="utf-8")), "")

def main():
    check = "--check" in sys.argv
    findings = []
    for p in HTML_FILES:
        if p.exists(): scan_html(findings, p)
    for p in JSON_FILES:
        if p.exists(): scan_json(findings, p)
    if not findings:
        print("language check: clean across %d html + %d json files"
              % (len(HTML_FILES), len(JSON_FILES)))
        return 0
    by_kind = {}
    for f in findings: by_kind.setdefault(f[2], []).append(f)
    for kind in sorted(by_kind):
        rows = by_kind[kind]
        print("\n[%s] %d finding(s)" % (kind, len(rows)))
        for where, line, _k, hit, note, snip in rows[:40]:
            loc = "%s:%d" % (where, line) if line else where
            print("  %-58s %-14s -> %s\n    %s" % (loc[:58], repr(hit), note, snip))
        if len(rows) > 40:
            print("  … and %d more" % (len(rows) - 40))
    print("\n%d finding(s) in all." % len(findings))
    return 1 if check else 0

if __name__ == "__main__":
    sys.exit(main())
