#!/usr/bin/env python3
"""Build the Documents-tab tree from the vision-documents manifest.

Emits landing/assets/docs_tree.json — a state -> district -> constituency ->
mandal hierarchy of every ACTIVE catalogued document, deduped by file path and
with titles cleaned of the manifest's stray whitespace. Leaves carry doc_id
(the key drive_links.json uses), a display title, kind, and size in MB.

The manifest's `category` field is a mess (hundreds of near-duplicate,
whitespace-varying strings); `kind` is clean, so grouping keys off `kind`, not
category. `district` is the level-1 group, `constituency` the level-2 group;
mandal rows carry their parent constituency in that same field.
"""
import json, os, re, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, "corpus_files", "vision_documents_manifest.json")
OUT = os.path.join(ROOT, "landing", "assets", "docs_tree.json")


def clean(s):
    return re.sub(r"\s+", " ", (s or "").replace(" ", " ")).strip()


def norm(t):
    return re.sub(r"[^a-z0-9]", "", (t or "").lower())


def dedup(leaves):
    seen, out = set(), []
    for l in leaves:
        n = norm(l["title"])
        if n in seen:
            continue
        seen.add(n)
        out.append(l)
    return out


PREFIX = "corpus_files/vision_documents/"


def relpath(dest):
    # the storage-relative path, identical in Drive and in any future cloud
    # bucket that preserves the same tree; the cloud provider resolves a leaf
    # as base_url + this path, so no per-file mapping is needed there.
    return dest[len(PREFIX):] if dest.startswith(PREFIX) else dest


def leaf(d):
    return {
        "id": d["doc_id"],
        "title": clean(d["title"]),
        "kind": d["kind"],
        "mb": round(float(d.get("fileSizeMB") or 0), 1),
        "path": relpath(d["dest"]),
    }


def main():
    rows = json.load(open(MANIFEST))
    rows = [d for d in rows if str(d.get("isActive")) == "1"]

    # dedupe by destination path — the manifest repeats the same file across the
    # constituencies it was crawled under (the state plan alone appears 175x).
    seen, uniq = set(), []
    for d in rows:
        if d["dest"] in seen:
            continue
        seen.add(d["dest"])
        uniq.append(d)

    state = None
    districts = collections.OrderedDict()

    for d in sorted(uniq, key=lambda x: (x["district"], x["constituency"], x["title"])):
        k = d["kind"]
        if k == "state":
            # keep the single state plan as the tree root; ignore its dupes
            if state is None:
                state = leaf(d)
            continue

        dist = clean(d["district"])
        node = districts.setdefault(dist, {"name": dist, "plans": [], "cons": collections.OrderedDict()})

        if k == "district":
            node["plans"].append(leaf(d))
            continue

        cons = clean(d["constituency"])
        cnode = node["cons"].setdefault(cons, {"name": cons, "vision": None, "profile": None, "mandals": []})
        if k == "constituency":
            cnode["vision"] = leaf(d)
        elif k == "profile":
            cnode["profile"] = leaf(d)
        elif k == "mandal":
            cnode["mandals"].append(leaf(d))

    out = {
        "state": state,
        "districts": [
            {
                "name": n["name"],
                "plans": dedup(n["plans"]),
                "constituencies": [
                    {
                        "name": c["name"],
                        "vision": c["vision"],
                        "profile": c["profile"],
                        "mandals": dedup(sorted(c["mandals"], key=lambda x: x["title"])),
                    }
                    for c in n["cons"].values()
                ],
            }
            for n in sorted(districts.values(), key=lambda x: x["name"])
        ],
    }

    n_leaves = (1 if state else 0) + sum(
        len(dd["plans"]) + sum(1 + (1 if c["vision"] else 0) + (1 if c["profile"] else 0) + len(c["mandals"]) - 1
                               for c in dd["constituencies"])
        for dd in out["districts"]
    )
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w"), ensure_ascii=False, separators=(",", ":"))
    total = sum(1 for _ in uniq)
    print(f"districts={len(out['districts'])}  unique_docs={total}  leaves~{n_leaves}")
    print(f"wrote {OUT}  ({os.path.getsize(OUT)//1024} KB)")


if __name__ == "__main__":
    main()
