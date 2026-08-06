#!/usr/bin/env python3
"""Harvest constituency data from the official AP Assembly Constituencies portal.

Source: https://apconstituencies.ap.gov.in  (Govt. of Andhra Pradesh)
The site is an Angular front-end over a plain JSON API at /CONST/api/Home/*.
Everything pulled here is the same public data the portal renders to any visitor.

Endpoints, all POST + JSON:
  constituencieslist   {page,pageSize}          -> roster, incl. the encrypted id
  profile              {encryptedConstId}       -> narrative profile sections
  EconomyGlance        {encryptedConstId}       -> GCDP narrative (HTML)
  growth-cards/latest  {constituencyId}         -> GCDP baseline/CAGR/target per sector  <- the numbers
  sector-share/get     {constituencyId,dataYear,shareType} -> sector share %
  constituencies/sectors {EncryptedConstituencyId} -> thrust sectors
  Mlas-List            {encryptedConstId}       -> MLA history

Note the key name is inconsistent across endpoints (encryptedConstId vs
constituencyId vs EncryptedConstituencyId) — that is the API's own quirk, not a
typo here. The id itself is an opaque AES blob the roster hands out; there is no
need to decrypt it, only to pass it back.

Politeness: one worker, a delay between calls, and a resumable on-disk cache, so
a re-run costs the government server nothing. Do not parallelise this.

Output: landing/assets/apc/<code>.json  (one file per constituency)
        landing/assets/apc/_roster.json

    python3 scripts/fetch_apc_data.py            # all 175, resumable
    python3 scripts/fetch_apc_data.py --limit 3  # smoke test
"""
import argparse
import json
import os
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "landing", "assets", "apc")
BASE = "https://apconstituencies.ap.gov.in/CONST/api/Home"
DELAY = 1.0          # seconds between requests — be a good citizen
TIMEOUT = 45

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://apconstituencies.ap.gov.in",
    "Referer": "https://apconstituencies.ap.gov.in/",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
}


def post(path, payload, retries=3):
    body = json.dumps(payload).encode()
    for attempt in range(retries):
        req = urllib.request.Request(f"{BASE}/{path}", data=body, headers=HEADERS, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                raw = r.read().decode("utf-8", "replace").strip()
            return json.loads(raw) if raw else None
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            if attempt == retries - 1:
                return {"_error": str(e)}
            time.sleep(2 ** attempt)
    return None


def fetch_roster():
    """All 175, paged."""
    items, page = [], 1
    while True:
        j = post("constituencieslist", {"page": page, "pageSize": 50})
        if not j or not j.get("items"):
            break
        items.extend(j["items"])
        if len(items) >= j.get("total", 0):
            break
        page += 1
        time.sleep(DELAY)
    # the roster can repeat rows across pages; key on code
    seen, uniq = set(), []
    for it in items:
        if it["code"] not in seen:
            seen.add(it["code"])
            uniq.append(it)
    return uniq


def fetch_one(entry):
    eid = entry["constituencyID"]
    rec = {
        "code": entry["code"],
        "name": entry["name"],
        "district": entry["district"],
        "logoUrl": entry.get("logoUrl"),
    }
    calls = [
        ("profile",       "profile",                {"encryptedConstId": eid}),
        ("economy_text",  "EconomyGlance",          {"encryptedConstId": eid}),
        ("growth",        "growth-cards/latest",    {"constituencyId": eid}),
        ("share_current", "sector-share/get",       {"constituencyId": eid, "dataYear": 1, "shareType": "CURRENT"}),
        ("share_target",  "sector-share/get",       {"constituencyId": eid, "dataYear": 22, "shareType": "TARGET"}),
        ("thrust",        "constituencies/sectors", {"EncryptedConstituencyId": eid}),
        ("mlas",          "Mlas-List",              {"encryptedConstId": eid}),
    ]
    for key, path, payload in calls:
        rec[key] = post(path, payload)
        time.sleep(DELAY)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, help="only fetch the first N (smoke test)")
    ap.add_argument("--force", action="store_true", help="refetch even if cached")
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    roster_path = os.path.join(OUT_DIR, "_roster.json")

    if os.path.exists(roster_path) and not args.force:
        roster = json.load(open(roster_path))
        print(f"roster: {len(roster)} (cached)")
    else:
        roster = fetch_roster()
        json.dump(roster, open(roster_path, "w"), indent=1)
        print(f"roster: {len(roster)} fetched")

    targets = roster[: args.limit] if args.limit else roster
    for i, entry in enumerate(targets, 1):
        dest = os.path.join(OUT_DIR, f"{entry['code']}.json")
        if os.path.exists(dest) and not args.force:
            print(f"  [{i}/{len(targets)}] {entry['name']} — cached")
            continue
        rec = fetch_one(entry)
        json.dump(rec, open(dest, "w"), indent=1)
        gcdp = None
        if isinstance(rec.get("growth"), list) and rec["growth"]:
            gcdp = rec["growth"][0].get("baselineAmountCrore")
        print(f"  [{i}/{len(targets)}] {entry['name']} — GCDP {gcdp}")

    print(f"\nwrote {OUT_DIR}")


if __name__ == "__main__":
    main()
