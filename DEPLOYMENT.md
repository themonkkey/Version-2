# Deployment

How this repository reaches the live site. Written 3 September 2026, after the
Git integration was set up; before that date every deploy was run by hand from
a laptop, so anything older than this file describes a different world.

## The short version

| | |
|---|---|
| Live site | https://version-2-coral.vercel.app |
| Repository | `themonkkey/Version-2` (public) |
| Production branch | `main` |
| Vercel project | `version-2` |
| Vercel scope | `aryansingh-8099` (Hobby) |
| **Root Directory** | **`landing`** — the site is NOT at the repo root |
| Framework preset | Other. No build step; the files are served as they are. |

**Push to `main` and the site deploys itself.** A build takes about 20 seconds.

## The one setting that matters

The site lives in `landing/`, not at the top of the repository. The repo root
holds the research side of the project — `app.py`, `scripts/`, `corpus_files/`,
and roughly 190 MB of tracked model artefacts (`embed_chunks.pkl` alone is
79 MB). None of that belongs on a web server.

So the Vercel project's **Root Directory is set to `landing`**. Everything else
follows from that: no build command, no output directory, no install step —
Vercel serves `landing/` as static files.

If Root Directory is ever reset to `.`, the next deploy will look for a site at
the repo root, find no `index.html`, and replace the working production
deployment with a broken one. This is not hypothetical: the setting *was* `.`
until 3 September 2026, which is why the Git integration was deliberately left
untriggered until it had been changed.

Check it before trusting a Git deploy:

```bash
vercel project inspect version-2 | grep -i "root directory"
```

## Two ways to deploy

### 1. Push to main (normal)

```bash
git push origin main
```

Vercel builds and promotes to production on its own. This is the path to use.

### 2. The CLI, from `landing/` (fallback)

```bash
cd landing && vercel --prod --yes
```

This was the *only* method before 3 September 2026 — you will find
`git push does NOT deploy` written in older notes, and that was true then.

It still works and is worth knowing, because it bypasses the Root Directory
setting entirely: it uploads whatever directory you run it from. That makes it
the safe move if a Git build is misbehaving and the site is down.

The CLI link lives in `landing/.vercel/project.json` (git-ignored, as it should
be). It records project `prj_36AIPJv3mT0NEmsf3J3zpRqxzPhz` under org
`team_NP6yR28CqEjohk9VVlg0yDH1`. Run the CLI from `landing/`, never from the
repo root, or it will offer to create a second project.

## Accounts, and which one can do what

Two GitHub accounts are logged in on this machine:

| Account | Access to `themonkkey/Version-2` |
|---|---|
| `themonkkey` | admin — **can push**, currently active |
| `aryaninternships-netizen` | read only — pushes fail with HTTP 403 |

If a push is rejected with 403, this is why. Fix it with:

```bash
gh auth switch --user themonkkey
```

The Vercel account (`aryansingh-8099`) is a separate identity from either GitHub
account. It is a personal Hobby scope, so there is no team to add people to.

## A trap: `v6appdashboard`

The same repository is also connected to an unrelated Vercel project called
`v6appdashboard` (`prj_qy54xHFbhKQg1TZZBHNXN9ZClusu`), whose Root Directory is
still `.`. That project last had real work in it around June 2026 and serves
nothing anyone uses.

Because the connection exists, **every push to `main` builds that project too**.
Its builds are harmless — nothing points a domain at them — but they are noise,
and a red build there does not mean the live site is broken.

Worth disconnecting in its Settings → Git when someone has a minute. It was
connected by mistake while looking for this project's Git settings.

## Verifying a deploy actually worked

Vercel reporting "Ready" only means the upload succeeded. To check the site
serves what you think it does, ask production directly rather than trusting the
dashboard:

```bash
# Is it up?
curl -s -o /dev/null -w "%{http_code}\n" https://version-2-coral.vercel.app/

# Did a specific asset ship?
curl -s -o /dev/null -w "%{http_code}\n" \
  https://version-2-coral.vercel.app/cases/media/mango-processing/0.jpg
```

Content served from JSON is worth checking by content, not by file presence —
the file can be there and still be the old copy from a browser or CDN cache.
Download it first and parse the file; piping `curl` straight into `python3`
is unreliable under this repo's shell wrapper:

```bash
cd /tmp && curl -s -o cs.json \
  https://version-2-coral.vercel.app/assets/case_studies.json && python3 -c "
import json
d = json.load(open('cs.json'))
have = [c['title'] for g in d.values() for c in g if c.get('cover')]
miss  = [c['title'] for g in d.values() for c in g if not c.get('cover')]
print(f'{len(have)} of {len(have)+len(miss)} have covers')
print('missing:', miss or 'none')
"
```

As of 3 September 2026 that prints `17 of 17 have covers`. The file is shaped
`{"ap": [...], "model": [...]}` — two lists of case studies, hence the nested
loop.

## Cache-busting, which bites often

`landing/index.html` fetches its data files with a version string in the query:

```js
fetch('assets/case_studies.json?v=2026-09-03b')
```

Editing a JSON file under `landing/assets/` is not enough — readers with the old
query string cached will keep the old data. **Bump the `?v=` string in the same
commit as the data change.** The convention is the date plus a letter.

## Recent deployment history

- Until 3 Sep 2026 — CLI only, run by hand from `landing/`.
- 3 Sep 2026 — repository connected, Root Directory corrected to `landing`,
  and the pipeline proven end to end by an empty commit
  (`Trigger the first Git-driven production deploy`). Built in 22 s.
