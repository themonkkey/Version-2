#!/usr/bin/env python3
"""Cross-verify the Google Drive vision-documents folder against the local tree,
and generate per-document Drive share links for the website.

The Drive folder (1lfMgehWYVglycFVK-dh5ITxwsbJ06IzU) is a direct upload of
corpus_files/vision_documents, so the Drive path of any file is just its local
`dest` with the "corpus_files/vision_documents/" prefix stripped. That 1:1
mapping is what makes both verify and link generation exact.

Needs rclone with a Google Drive remote. One-time setup:
    rclone config                      # make a remote, e.g. named 'gdrive'
Then point every call at the shared folder as the root via its id.

    # 1) VERIFY — list Drive files, diff against local, report missing/extra
    python3 scripts/drive_sync.py verify --remote gdrive

    # 2) LINKS — make each doc 'anyone with link' and write doc_links.json
    python3 scripts/drive_sync.py links  --remote gdrive

Both accept --root-id (defaults to the shared folder id below) and --dry-run.
"""
import argparse, json, os, subprocess, sys, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, "corpus_files", "vision_documents_manifest.json")
LINKS_OUT = os.path.join(ROOT, "landing", "assets", "doc_links.json")
PREFIX = "corpus_files/vision_documents/"
SHARED_FOLDER_ID = "1lfMgehWYVglycFVK-dh5ITxwsbJ06IzU"


def rclone(args, root_id):
    base = ["rclone", "--drive-root-folder-id=" + root_id]
    return subprocess.run(base + args, capture_output=True, text=True)


def active_docs():
    rows = [d for d in json.load(open(MANIFEST)) if str(d.get("isActive")) == "1"]
    seen, uniq = set(), []
    for d in rows:
        if d["dest"] in seen:
            continue
        seen.add(d["dest"])
        uniq.append(d)
    return uniq


def drivepath(dest):
    return dest[len(PREFIX):] if dest.startswith(PREFIX) else dest


def cmd_verify(remote, root_id, dry):
    docs = active_docs()
    want = {drivepath(d["dest"]) for d in docs}
    # every PDF actually on disk (ground truth, includes inactive)
    disk = set()
    for base, _, files in os.walk(os.path.join(ROOT, PREFIX.rstrip("/"))):
        for f in files:
            if f.lower().endswith(".pdf"):
                disk.add(os.path.relpath(os.path.join(base, f), os.path.join(ROOT, PREFIX.rstrip("/"))))
    print(f"local: {len(disk)} PDFs on disk, {len(want)} active in manifest")

    r = rclone(["lsf", "-R", "--files-only", f"{remote}:"], root_id)
    if r.returncode != 0:
        print("rclone lsf failed:\n" + r.stderr, file=sys.stderr)
        sys.exit(1)
    have = {ln for ln in r.stdout.splitlines() if ln.lower().endswith(".pdf")}
    print(f"drive: {len(have)} PDFs under folder {root_id}")

    missing = sorted(disk - have)   # on disk but not in Drive
    extra = sorted(have - disk)     # in Drive but not on disk
    print(f"\n== MISSING from Drive ({len(missing)}) ==")
    for m in missing[:40]:
        print("  -", m)
    if len(missing) > 40:
        print(f"  … +{len(missing)-40} more")
    print(f"\n== EXTRA in Drive ({len(extra)}) ==")
    for e in extra[:40]:
        print("  +", e)
    if len(extra) > 40:
        print(f"  … +{len(extra)-40} more")
    print(f"\nverdict: {'MATCH' if not missing else 'MISMATCH — see missing list'}")


def cmd_links(remote, root_id, dry):
    docs = active_docs()
    cfg = {}
    if os.path.exists(LINKS_OUT):
        try:
            cfg = json.load(open(LINKS_OUT))
        except Exception:
            cfg = {}
    links = dict(cfg.get("links") or {})

    ok = fail = skip = 0
    by_id = {}
    # collapse dupes: many doc_ids share one dest (e.g. the state plan); link once per path
    for d in docs:
        p = drivepath(d["dest"])
        by_id.setdefault(p, []).append(d["doc_id"])

    # One recursive listing gives every file's Drive ID, so the share URL can be
    # built locally. `rclone link` was ~1 process + 1 API round-trip PER FILE
    # (1108 of them, minutes); this is a single call. It relies on the folder
    # already being shared "anyone with the link" — which it is, since the whole
    # tree was shared as one folder — so no per-file permission call is needed.
    print("listing Drive (one call)…")
    r = rclone(["lsjson", "-R", "--files-only", f"{remote}:"], root_id)
    if r.returncode != 0:
        print("rclone lsjson failed:\n" + r.stderr, file=sys.stderr)
        sys.exit(1)
    id_by_path = {}
    for it in json.loads(r.stdout):
        if it.get("ID"):
            id_by_path[it["Path"]] = it["ID"]
    print(f"  got {len(id_by_path)} file IDs")

    for p, ids in sorted(by_id.items()):
        if all(str(x) in links for x in ids):
            skip += 1
            continue
        if dry:
            print(f"[dry] would link {p}  -> ids {ids}")
            continue
        fid = id_by_path.get(p)
        if fid:
            url = f"https://drive.google.com/file/d/{fid}/view"
            for x in ids:
                links[str(x)] = url
            ok += 1
        else:
            fail += 1
            print(f"  ! not found in Drive: {p}", file=sys.stderr)

    if not dry:
        # preserve the provider seam; only refresh the links map
        cfg["provider"] = cfg.get("provider", "drive")
        cfg["cloudBase"] = cfg.get("cloudBase", "")
        cfg["links"] = {k: links[k] for k in sorted(links, key=lambda x: (len(x), x))}
        json.dump(cfg, open(LINKS_OUT, "w"), ensure_ascii=False, indent=1)
    print(f"\nlinked={ok}  failed={fail}  already-had={skip}  -> {LINKS_OUT}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["verify", "links"])
    ap.add_argument("--remote", default="gdrive", help="rclone remote name (from `rclone config`)")
    ap.add_argument("--root-id", default=SHARED_FOLDER_ID, help="Drive folder id to treat as root")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.cmd == "verify":
        cmd_verify(a.remote, a.root_id, a.dry_run)
    else:
        cmd_links(a.remote, a.root_id, a.dry_run)


if __name__ == "__main__":
    main()
