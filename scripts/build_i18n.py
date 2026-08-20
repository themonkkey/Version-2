#!/usr/bin/env python3
"""Collect every translatable string on the site, and fill the Telugu for them.

WHY A BUILD STEP AND NOT AN EMBEDDED WIDGET. The obvious answer to "translate the
site" is a script tag from Google or Weglot. Google's website translator was
retired for new sites; the rest are paid proxies that route every page view
through a third party. Bhashini — the Government of India's own translation
mission — is free for a non-commercial site like this one, but its own docs say
the free tier is for proof-of-concept use, so putting it in the request path of a
government dashboard would be both slow and fragile.

So the API is called ONCE, here, offline. What ships is a static dictionary: no
key in production, no third party in the request path, nothing to rate-limit, and
— the part that matters for a government site — the Telugu is on disk where a
Telugu speaker can correct it before anyone sees it.

WHAT IS COLLECTED
  1. Interface text from landing/index.html — headings, labels, buttons, captions.
     Script and style blocks, comments and attribute values are skipped.
  2. Data labels from the built JSON in landing/assets — sector names, playbook
     and recommendation titles. Only label-like fields; never numbers, never
     district names, never estimate classes (TRE/SRE/FRE/FAE), which must read
     the same in both languages or the figures stop being checkable.

en.json is the extracted set. te.json maps each English string to its Telugu.
Re-running preserves every translation already present and only adds what is new,
so hand corrections are never overwritten by a later pass.

Usage:
    python3 scripts/build_i18n.py               # extract, report what is missing
    python3 scripts/build_i18n.py --bhashini    # extract, then fill the gaps
    python3 scripts/build_i18n.py --check       # verify only, exit 1 on drift

--bhashini needs credentials from https://bhashini.gov.in (free, register as a
developer), passed as environment variables:
    BHASHINI_USER_ID, BHASHINI_API_KEY, BHASHINI_PIPELINE_ID
"""
import json, os, re, sys
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(ROOT, "landing", "index.html")
ASSETS = os.path.join(ROOT, "landing", "assets")
OUT_DIR = os.path.join(ASSETS, "i18n")
EN = os.path.join(OUT_DIR, "en.json")
TE = os.path.join(OUT_DIR, "te.json")

# Fields in the built JSON that hold a human-readable label rather than a value.
LABEL_KEYS = {"title", "name", "label", "sector", "group", "headline", "kicker"}

# Only these files. Walking every JSON in assets/ pulled 2,000+ strings, because
# mandal_index.json, docs_tree.json and dashboard_index.json are full of `name`
# and `title` fields holding mandal names, district names and document titles.
# Those are proper nouns and filenames — translating them would be wrong, and it
# would bury the couple of hundred labels that actually matter.
DATA_FILES = {
    "gva_playbook.json",         # sector playbooks: names, pathways, actions
    "recommendations.json",      # priority interventions
    "fisheries_benchmark.json",  # calculator benchmark labels
    "districts_data.json",       # sector names on the district panel
}

# Left in English on purpose. Estimate classes are the vocabulary the figures are
# quoted in and are used verbatim in the source workbooks; translating them would
# make a number impossible to trace back. The rest are proper nouns or units.
KEEP_ENGLISH = {
    "TRE", "SRE", "FRE", "FAE", "GVA", "GDVA", "GDDP", "DDP", "GSVA",
    "NITI Aayog", "Swarna Andhra @2047", "Swarna Andhra", "PIF",
    "cr", "L cr", "Rs", "%",
}

# A string worth translating has at least two letters and is not a bare number,
# a lone symbol, or a template placeholder left in the markup.
WORTH = re.compile(r"[A-Za-z]{2}")
PLACEHOLDER = re.compile(r"^[\s{}\[\]$]*$")


# Only elements that contain text and NOTHING ELSE are collected.
#
# The first version of this took every run of text between two tags, which cut
# sentences apart wherever a <b> or an <a> sat inside them: ", and 2023-24 at"
# is not a translatable string, and asking a translation model for 2,200 such
# fragments would produce grammatical rubbish. Worse, putting the pieces back
# would mean rewriting innerHTML and destroying the links and emphasis inside.
#
# So a paragraph with inline markup in it is deliberately left in English rather
# than translated badly. The count of those is reported, so the gap is visible
# rather than silent.
SKIP_TAGS = {"script", "style", "svg", "path", "code", "pre"}
VOID_TAGS = {"br", "img", "input", "hr", "meta", "link", "source", "i"}


class TextOnlyCollector(HTMLParser):
    """Collects text from elements whose content is a single plain text run."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []          # [tag, text_so_far, saw_child_element]
        self.skip = 0
        self.found = set()
        self.mixed = 0           # elements left behind because of inline markup

    def handle_starttag(self, tag, attrs):
        if tag in SKIP_TAGS:
            self.skip += 1
            return
        if tag in VOID_TAGS:
            # A void tag still counts as an element inside the parent: a line
            # broken by <br> is two strings, not one.
            if self.stack:
                self.stack[-1][2] = True
            return
        if self.stack:
            self.stack[-1][2] = True
        self.stack.append([tag, [], False])

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS:
            self.skip = max(0, self.skip - 1)
            return
        if tag in VOID_TAGS:
            return
        while self.stack:
            el = self.stack.pop()
            if el[0] == tag:
                text = " ".join("".join(el[1]).split())
                if not el[2] and text and WORTH.search(text) \
                        and not PLACEHOLDER.match(text) and text not in KEEP_ENGLISH:
                    self.found.add(text)
                elif el[2] and text and WORTH.search(text):
                    self.mixed += 1
                break

    def handle_data(self, data):
        if self.skip or not self.stack:
            return
        self.stack[-1][1].append(data)


def interface_strings():
    src = open(HTML, encoding="utf-8").read()
    src = re.sub(r"<!--.*?-->", "", src, flags=re.S)
    c = TextOnlyCollector()
    c.feed(src)
    interface_strings.mixed = c.mixed
    return c.found


def data_labels():
    found = set()
    if not os.path.isdir(ASSETS):
        return found
    for fn in sorted(DATA_FILES):
        if not os.path.exists(os.path.join(ASSETS, fn)):
            continue
        try:
            with open(os.path.join(ASSETS, fn), encoding="utf-8") as fh:
                doc = json.load(fh)
        except Exception:
            continue

        def walk(node):
            if isinstance(node, dict):
                for k, v in node.items():
                    if k in LABEL_KEYS and isinstance(v, str):
                        t = " ".join(v.split())
                        if t and WORTH.search(t) and t not in KEEP_ENGLISH:
                            found.add(t)
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)

        walk(doc)
    return found


def bhashini_translate(strings):
    """Fill Telugu for `strings` via Bhashini. Returns {english: telugu}."""
    import urllib.request

    user = os.environ.get("BHASHINI_USER_ID")
    key = os.environ.get("BHASHINI_API_KEY")
    pipe = os.environ.get("BHASHINI_PIPELINE_ID")
    if not (user and key and pipe):
        sys.exit("--bhashini needs BHASHINI_USER_ID, BHASHINI_API_KEY and "
                 "BHASHINI_PIPELINE_ID in the environment. Register free at "
                 "https://bhashini.gov.in to get them.")

    def post(url, body, headers):
        req = urllib.request.Request(
            url, data=json.dumps(body).encode(), method="POST",
            headers={"Content-Type": "application/json", **headers})
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())

    # 1. Ask which service can do en->te, and where to send the text.
    cfg = post(
        "https://meity-auth.ulcacontrib.org/ulca/apis/v0/model/getModelsPipeline",
        {"pipelineTasks": [{"taskType": "translation",
                            "config": {"language": {"sourceLanguage": "en",
                                                    "targetLanguage": "te"}}}],
         "pipelineRequestConfig": {"pipelineId": pipe}},
        {"userID": user, "ulcaApiKey": key})

    service = cfg["pipelineResponseConfig"][0]["config"][0]["serviceId"]
    endpoint = cfg["pipelineInferenceAPIEndPoint"]
    url = endpoint["callbackUrl"]
    auth = endpoint["inferenceApiKey"]

    out, batch = {}, 25          # small batches: one long request that fails
    todo = sorted(strings)       # loses everything, 25 loses one batch
    for i in range(0, len(todo), batch):
        chunk = todo[i:i + batch]
        res = post(url,
                   {"pipelineTasks": [{"taskType": "translation",
                                       "config": {"language": {"sourceLanguage": "en",
                                                               "targetLanguage": "te"},
                                                  "serviceId": service}}],
                    "inputData": {"input": [{"source": s} for s in chunk]}},
                   {auth["name"]: auth["value"]})
        got = res["pipelineResponse"][0]["output"]
        for src, item in zip(chunk, got):
            t = (item.get("target") or "").strip()
            if t:
                out[src] = t
        print("  translated {}/{}".format(min(i + batch, len(todo)), len(todo)))
    return out


def main():
    check = "--check" in sys.argv
    use_api = "--bhashini" in sys.argv

    strings = interface_strings() | data_labels()
    if not strings:
        sys.exit("no translatable strings found — has index.html moved?")

    have = {}
    if os.path.exists(TE):
        with open(TE, encoding="utf-8") as fh:
            have = json.load(fh)

    # Preserve every existing translation; drop only what no longer appears on
    # the site, so the file cannot grow stale entries forever.
    merged = {s: have.get(s, "") for s in sorted(strings)}
    missing = [s for s, v in merged.items() if not v]

    if check:
        if not os.path.exists(EN) or not os.path.exists(TE):
            sys.exit("--check: i18n files missing, run without --check")
        with open(EN, encoding="utf-8") as fh:
            en_have = json.load(fh)
        if sorted(en_have) != sorted(strings):
            sys.exit("--check: extracted strings differ from en.json ({} on site "
                     "vs {} published). Re-run without --check."
                     .format(len(strings), len(en_have)))
        print("--check: {} string(s) verified, {} still untranslated"
              .format(len(strings), len(missing)))
        return

    if use_api and missing:
        print("asking Bhashini for {} string(s)...".format(len(missing)))
        merged.update(bhashini_translate(missing))
        missing = [s for s, v in merged.items() if not v]

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(EN, "w", encoding="utf-8") as fh:
        json.dump(sorted(strings), fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    with open(TE, "w", encoding="utf-8") as fh:
        json.dump(merged, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")

    done = len(merged) - len(missing)
    print("{} string(s) on the site; {} translated, {} still English"
          .format(len(merged), done, len(missing)))
    mixed = getattr(interface_strings, "mixed", 0)
    if mixed:
        print("{} element(s) hold text mixed with links or emphasis and are left "
              "in English on purpose — translating them would mean rewriting "
              "their markup.".format(mixed))
    print("wrote {} and {}".format(os.path.relpath(EN, ROOT), os.path.relpath(TE, ROOT)))
    if missing:
        print("\nRun with --bhashini (and the three BHASHINI_* variables set) to "
              "fill the rest, or type them into te.json by hand.")


if __name__ == "__main__":
    main()
