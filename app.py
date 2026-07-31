"""Swarna Andhra training-material chatbot — Streamlit prototype.

Scope (per Aryan's brief):
1. GDP/GSDP estimation methodologies (3 types), bottom-up vs top-down, which sector uses which
2. GVA calculation method
3. District economic profile snapshots — comparative-advantage sectors + GVA-boosting interventions
4. GSDP/DDP data of districts (pending a structured dataset — flagged when unavailable)

Retrieval is grounded in the PIF training corpus (TF-IDF over training decks + case studies).
Falls back to the model's general knowledge when the corpus doesn't cover a question,
but is told to say so explicitly rather than blur the two.
"""
import os
import pickle
import re

import numpy as np
import streamlit as st

try:
    from sklearn.metrics.pairwise import cosine_similarity  # only needed for legacy TF-IDF index
except Exception:
    cosine_similarity = None


def _bootstrap_secrets():
    """Make keys available as env vars whether local (.env) or Streamlit Cloud (st.secrets),
    so embeddings.py and the LLM call read them uniformly from os.environ."""
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        for line in open(env_path):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
    try:
        for k, v in st.secrets.items():
            os.environ.setdefault(k, str(v))
    except Exception:
        pass


_bootstrap_secrets()

_BASE = os.path.dirname(__file__)
INDEX_PATH = os.path.join(_BASE, "index.pkl")
EMBED_NPZ = os.path.join(_BASE, "embed_index.npz")
EMBED_CHUNKS = os.path.join(_BASE, "embed_chunks.pkl")
# the 112MB matrix is committed as two <100MB parts (GitHub file-size limit) and
# reassembled here at load time
EMBED_PARTS = [os.path.join(_BASE, f"embed_index_part{i}.npz") for i in range(2)]

# voyage-4-nano index, built by embed_voyage.py. Runs from local open weights, so the
# deployment needs no embedding API key at all -- which is what took the app down before.
VOYAGE_DIR = os.environ.get("VOYAGE_OUT", os.path.join(_BASE, "voyage_out"))
VOYAGE_NPZ = os.path.join(VOYAGE_DIR, "voyage_index.npz")
VOYAGE_CHUNKS = os.path.join(VOYAGE_DIR, "voyage_chunks.pkl")


def _using_voyage():
    return os.environ.get("EMBED_PROVIDER", "cohere").lower() == "voyage_local"


def _load_matrix():
    if _using_voyage() and os.path.exists(VOYAGE_NPZ):
        return np.load(VOYAGE_NPZ)["matrix"]
    if os.path.exists(EMBED_NPZ):
        return np.load(EMBED_NPZ)["matrix"]
    if all(os.path.exists(p) for p in EMBED_PARTS):
        return np.concatenate([np.load(p)["matrix"] for p in EMBED_PARTS], axis=0)
    return None

# Recognizable district-name aliases for direct lookup — TF-IDF alone under-ranks a district
# snapshot against generic methodology docs when the query only has one distinctive term
# (e.g. "gdp of kakinada" loses to docs repeating "GDP"/"district" many times).
DISTRICT_ALIASES = {
    "alluri seetha rama raju": "Alluri_Seetha_Rama_Raju", "asr": "Alluri_Seetha_Rama_Raju",
    "anakapalle": "Anakapalle", "anakapalli": "Anakapalle",
    "ananthapuramu": "Ananthapuramu", "anantapur": "Ananthapuramu",
    "annamayya": "Annamayya",
    "bapatla": "Bapatla",
    "chittoor": "Chittoor",
    "konaseema": "Dr.B.R.Ambedkar_Konaseema", "ambedkar konaseema": "Dr.B.R.Ambedkar_Konaseema",
    "east godavari": "East_Godavari", "kakinada": "Kakinada",
    "eluru": "Eluru",
    "guntur": "Guntur",
    "krishna": "Krishna",
    "kurnool": "Kurnool",
    "markapuram": "Markapuram",
    "nandyal": "Nandyal",
    "ntr": "Ntr",
    "palnadu": "Palnadu",
    "parvathipuram manyam": "Parvathipuram_Manyam", "parvathipuram": "Parvathipuram_Manyam",
    "polavaram": "Polavaram",
    "prakasam": "Prakasam",
    "nellore": "Sps_Nellore", "sps nellore": "Sps_Nellore",
    "sri satya sai": "Sri_Satya_Sai", "satya sai": "Sri_Satya_Sai",
    "srikakulam": "Srikakulam",
    "tirupati": "Tirupati",
    "visakhapatnam": "Visakhapatnam", "vizag": "Visakhapatnam",
    "vizianagaram": "Vizianagaram",
    "west godavari": "West_Godavari",
    "ysr kadapa": "Ysr_Kadapa", "kadapa": "Ysr_Kadapa",
}


_ALIAS_RE = None


def detect_district(query):
    """Match district aliases on WORD BOUNDARIES, not as bare substrings.

    Plain `alias in query` matched short aliases inside unrelated words -- 'ntr' fires on
    "co-ntr-ibutions", "co-ntr-ibuting", "cou-ntr-y". On the 180-prompt hard set that
    detected the wrong district for 16 prompts (9%), and because a detected district
    force-injects that district's chunks at score 1.0, a false match actively poisons
    retrieval. Word boundaries cut it to 5.
    """
    global _ALIAS_RE
    if _ALIAS_RE is None:
        # longest alias first, so "east godavari" wins over "godavari"
        ordered = sorted(DISTRICT_ALIASES, key=len, reverse=True)
        _ALIAS_RE = [(re.compile(r"\b" + re.escape(a) + r"\b"), DISTRICT_ALIASES[a])
                     for a in ordered]
    low = query.lower()
    for pat, folder in _ALIAS_RE:
        if pat.search(low):
            return folder
    return None

SYSTEM_PROMPT = """You are an assistant for Pahlé India Foundation's Swarna Andhra capacity-building \
programme, which trains Andhra Pradesh district/constituency/mandal officials on GDP/GSDP/GDDP \
estimation and sector-wise GVA improvement.

You are focused on exactly four topics:
1. GDP/GSDP estimation methodologies (production, income, expenditure approaches), bottom-up vs \
top-down approaches, and which sector typically uses which method.
2. GVA calculation methodology.
3. Economic profile snapshots of AP districts — sectors with comparative advantage, and possible \
interventions/suggestions to boost GVA in those sectors.
4. GSDP/DDP data of specific districts (numeric figures), when available in context.

You are given CONTEXT chunks retrieved from PIF's own training material (decks, case studies, \
toolkits), each labeled with its source file and, where available, a slide/page number. \
Ground your answer in that context first and cite which source file (and slide/page, if given) \
you drew from. \
If the context doesn't fully answer the question, you may supplement with general economic \
knowledge — but say explicitly which part of your answer is from the PIF corpus and which part is \
general knowledge/not verified against official data.

If asked for district-level GSDP/DDP numeric data that is not in the context, say plainly that you \
don't have that specific figure rather than guessing numbers.
"""


@st.cache_resource
def load_index():
    # semantic (embedding) index — preferred
    matrix = _load_matrix()
    chunks_path = VOYAGE_CHUNKS if (_using_voyage() and os.path.exists(VOYAGE_CHUNKS)) \
        else EMBED_CHUNKS
    if matrix is not None and os.path.exists(chunks_path):
        with open(chunks_path, "rb") as f:
            meta = pickle.load(f)
        model_id = meta.get("model_id")
        # A query embedded by one model and scored against another model's index gives
        # near-random similarities and no error -- it silently returns plausible garbage.
        # Fail loudly instead.
        import embeddings
        if model_id and model_id != embeddings.model_id():
            raise RuntimeError(
                f"Index/model mismatch: index was built with '{model_id}' but "
                f"EMBED_PROVIDER resolves to '{embeddings.model_id()}'. "
                f"Set EMBED_PROVIDER to match the index, or rebuild the index.")
        return {"mode": "embed", "chunks": meta["chunks"],
                "matrix": matrix.astype(np.float32), "model_id": model_id}
    # legacy TF-IDF fallback
    if os.path.exists(INDEX_PATH):
        with open(INDEX_PATH, "rb") as f:
            idx = pickle.load(f)
        idx["mode"] = "tfidf"
        return idx
    return None


def _label(source, page):
    return f"{source} (slide/page {page})" if page else source


def _scores(query, index):
    """Similarity of query against every chunk, for whichever index mode is loaded."""
    if index["mode"] == "embed":
        import embeddings
        qvec = embeddings.embed_query(query)  # L2-normalized
        return index["matrix"] @ qvec  # cosine == dot product
    qvec = index["vectorizer"].transform([query])
    return cosine_similarity(qvec, index["matrix"]).flatten()


# Benchmark-only ablation switches (default off -> production behaviour unchanged).
# run_hard_retrieval.py flips these to measure what the embeddings contribute on their
# own, separately from the two hand-tuned rules layered on top of them.
ABLATE_FORCE = False    # skip the forced district_data injection
ABLATE_RESCUE = False   # skip the keyword rescue for numeric tables


def retrieve(query, index, district_folder=None):
    if index is None:
        return []
    sims = _scores(query, index)
    top_score = float(sims.max())
    # embedding cosines sit higher than TF-IDF; thresholds tuned per mode
    if index["mode"] == "embed":
        k = 6 if top_score > 0.75 else 10 if top_score > 0.6 else 16
    else:
        k = 5 if top_score > 0.3 else 9 if top_score > 0.15 else 14
    top_idx = sims.argsort()[::-1][:k]

    seen_keys = set()
    results = []

    def add_chunk(i, score, neighbor=False):
        c = index["chunks"][i]
        key = (c["source"], c.get("page"))
        if key in seen_keys:
            return
        seen_keys.add(key)
        results.append({
            "source": c["source"],
            "page": c.get("page"),
            "text": c["text"],
            "score": score,
            "neighbor": neighbor,
        })

    # build a lookup: (source, page) -> chunk index, for neighbor expansion
    page_index = {}
    for j, c in enumerate(index["chunks"]):
        if c.get("page") is not None:
            page_index[(c["source"], c["page"])] = j

    # a detected district name is a stronger signal than TF-IDF score — force its snapshot
    # and sector files in first so they aren't drowned out by generic methodology docs.
    if district_folder and not ABLATE_FORCE:
        sector_prefix = f"district_data/{district_folder}/"
        snapshot_name = f"district_data/{district_folder}_Snapshot.txt"
        forced = [
            (j, c) for j, c in enumerate(index["chunks"])
            if c["source"].startswith(sector_prefix) or c["source"] == snapshot_name
        ]

        # headline aggregates (GDDP, NDDP, per-capita, GDVA) and the snapshot must come
        # before the alphabetical per-sector files, or the truncated context drops them.
        def prio(src):
            s = src.lower()
            if "snapshot" in s:
                return 0
            if "gross district domestic product" in s or "gddp" in s:
                return 1
            if "net district domestic product" in s or "nddp" in s:
                return 2
            if "per capita" in s:
                return 3
            if "gross district value added" in s or "gdva" in s:
                return 4
            return 5

        # force only the top few headline aggregates (snapshot carries GDDP/NDDP/
        # per-capita/top-sectors already). Forcing all ~7 buried the semantically
        # relevant mandal/constituency vision plans for topical queries like
        # "paddy productivity in Anaparthi mandal", so keep this lean.
        forced.sort(key=lambda jc: prio(jc[1]["source"]))
        for j, c in forced[:2]:
            add_chunk(j, 1.0)

    primary = [i for i in top_idx if sims[i] > 0]

    # keyword rescue: numeric tables (e.g. "Paddy Productivity 7275 -> 7646") embed
    # poorly, so pure vector search finds the right DOCUMENT but often the wrong PAGE.
    # For each top-matching document, also pull the page whose text best matches the
    # query's content words. Added before the primary hits so it survives the cap.
    stop = {"what", "is", "the", "and", "its", "for", "of", "in", "how", "which",
            "are", "to", "me", "tell", "about", "give", "show", "district", "mandal",
            "constituency", "target", "targets", "plan"}
    qwords = set(w for w in re.findall(r"[a-z]+", query.lower()) if len(w) > 3 and w not in stop)
    if qwords and not ABLATE_RESCUE:
        top_sources = []
        for i in primary[:5]:
            s = index["chunks"][i]["source"]
            if s not in top_sources:
                top_sources.append(s)
        # queries seeking figures ("productivity", "target", "growth"...) want the
        # number-bearing table page, which embeds poorly and has few keywords
        data_intent = bool(re.search(
            r"productiv|target|growth|\brate\b|income|gdp|gddp|gsdp|\bddp\b|per capita|"
            r"population|contribution|hectare|\barea\b|yield|percent|\bvalue\b|figure",
            query.lower()))
        for src in top_sources[:3]:
            # exclude query words that are just the place/name (they appear in the
            # document's own path), so within-document ranking uses topic words only
            path_words = set(re.findall(r"[a-z]+", src.lower()))
            topic = qwords - path_words
            if not topic:
                continue
            scored = []
            for j, c in enumerate(index["chunks"]):
                if c["source"] != src:
                    continue
                low = c["text"].lower()
                cover = sum(1 for w in topic if w in low)
                if cover == 0:
                    continue
                digits = len(re.findall(r"\d", c["text"])) if data_intent else 0
                scored.append((cover * 100 + min(digits, 60), j))
            scored.sort(reverse=True)
            for _, j in scored[:2]:
                add_chunk(j, 0.99)

    # pass 1: all distinct primary hits, so no single document's neighbor pages
    # crowd a more relevant document out of the context window
    for i in primary:
        add_chunk(i, float(sims[i]))

    # pass 2: neighbor expansion (adjacent pages) for multi-page PDFs, appended after
    for i in primary:
        c = index["chunks"][i]
        if c.get("page") is not None and c.get("folder") in ("methodology", "vision_documents"):
            for delta in (-1, +1):
                neighbor_key = (c["source"], c["page"] + delta)
                if neighbor_key in page_index:
                    add_chunk(page_index[neighbor_key], float(sims[i]) * 0.9, neighbor=True)

    return results


# Groq's free tier caps llama models at a few thousand tokens/minute, so the prompt
# must stay small. Cap how many chunks and how much of each go into the LLM context
# (the full hit list is still shown separately under "sources retrieved").
CONTEXT_MAX_CHUNKS = 11
CONTEXT_CHARS_PROSE = 900       # vision/methodology prose — trim hard
CONTEXT_CHARS_DATA = 1600       # district_data files are short + dense with exact numbers


def build_context_block(hits):
    if not hits:
        return "(No relevant material found in the PIF corpus for this query.)"
    parts = []
    for h in hits[:CONTEXT_MAX_CHUNKS]:
        label = _label(h["source"], h["page"])
        cap = CONTEXT_CHARS_DATA if h["source"].startswith("district_data/") else CONTEXT_CHARS_PROSE
        text = h["text"][:cap]
        parts.append(f"--- Source: {label} (relevance {h['score']:.2f}) ---\n{text}")
    return "\n\n".join(parts)


def call_llm(messages):
    provider = os.environ.get("LLM_PROVIDER", "groq").lower()
    if provider == "groq":
        from groq import Groq

        client = Groq(api_key=os.environ["GROQ_API_KEY"])
        resp = client.chat.completions.create(
            model=os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
            messages=messages,
            temperature=0.2,
            max_tokens=1024,
        )
        return resp.choices[0].message.content
    elif provider == "gemini":
        from google import genai

        import time as _t

        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        prompt = "\n\n".join(f"[{m['role']}]\n{m['content']}" for m in messages)
        # Pinned to the chosen production model. gemini-2.0-flash (the old default) is two
        # generations old and quota-blocked on this account.
        model = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
        # 503/UNAVAILABLE is transient (seen twice in testing) — retry with backoff so a
        # blip does not surface to an officer as a failed answer. Quota (429) is not retried.
        last = None
        for attempt in range(4):
            try:
                return client.models.generate_content(model=model, contents=prompt).text
            except Exception as e:
                last = e
                s = str(e).upper()
                transient = ("503" in s or "UNAVAILABLE" in s or "OVERLOADED" in s)
                if transient and attempt < 3:
                    _t.sleep(2 ** attempt)
                    continue
                raise
        raise last
    elif provider == "claude":
        # local Claude Code CLI backend (no API key) — uses `claude -p`
        import subprocess
        prompt = "\n\n".join(f"[{m['role']}]\n{m['content']}" for m in messages)
        r = subprocess.run(
            ["claude", "-p", "--model", os.environ.get("CLAUDE_MODEL", "haiku")],
            input=prompt, capture_output=True, text=True, timeout=180,
        )
        out = (r.stdout or r.stderr).strip()
        if not out:
            raise RuntimeError("claude CLI returned no output")
        return out
    else:
        raise RuntimeError(f"Unknown LLM_PROVIDER: {provider}")


st.set_page_config(
    page_title="Swarna Andhra GVA Assistant",
    page_icon="🏛️",
    layout="centered",
    initial_sidebar_state="expanded",
)

BRAND_CSS = """
<style>
/* Apple system design language: SF Pro, grouped-background greys, squircle cards,
   soft layered depth, tight optical tracking on display type. */
:root{
  --bg:#F2F2F7; --surface:#FFFFFF; --fill:#F7F7FA;
  --label:#000000; --label-2:rgba(60,60,67,.60); --label-3:rgba(60,60,67,.30);
  --sep:rgba(60,60,67,.16); --green:#248A3D; --green-v:#34C759;
  --r:20px; --shadow:0 1px 2px rgba(0,0,0,.04), 0 8px 24px -8px rgba(0,0,0,.10);
}
html,body,[class*="css"],.stApp{
  font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text","SF Pro Display",
    "Helvetica Neue",system-ui,sans-serif !important;
  background:var(--bg) !important;color:var(--label);-webkit-font-smoothing:antialiased;}
#MainMenu,footer,header[data-testid="stHeader"]{visibility:hidden;}
.block-container{padding-top:2.8rem;padding-bottom:7.5rem;max-width:760px;}
.stApp{background:var(--bg);}

.sa-header{background:transparent;border:none;padding:0;margin:0;position:static;overflow:visible;
  display:block;}
.sa-header::before{display:none;}
.sa-emblem{display:none;}
.sa-htext h1{font-size:30px;font-weight:700;letter-spacing:-.024em;line-height:1.12;color:var(--label);margin:0;}
.sa-htext h1 span{color:var(--green);}
.sa-htext p{font-size:13px;color:var(--label-2);margin:6px 0 0;font-weight:400;letter-spacing:-.01em;}
.sa-badge{display:none;}
.sa-sub{font-size:15px;color:var(--label-2);margin:16px 0 0;line-height:1.5;letter-spacing:-.011em;}

.sa-stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:22px 0 6px;}
.sa-stat{background:var(--surface);border-radius:var(--r);padding:18px 16px;box-shadow:var(--shadow);}
.sa-stat .v{font-size:26px;font-weight:700;letter-spacing:-.03em;line-height:1;color:var(--label);
  font-variant-numeric:tabular-nums;}
.sa-stat .k{font-size:11.5px;color:var(--label-2);margin-top:7px;font-weight:500;letter-spacing:-.005em;}

.sa-label{font-size:12.5px;color:var(--label-2);margin:26px 4px 10px;font-weight:500;letter-spacing:-.005em;}

section[data-testid="stSidebar"]{background:var(--surface);border-right:1px solid var(--sep);}
section[data-testid="stSidebar"] .block-container{padding-top:2.8rem;}
.sb-title{font-size:11px;font-weight:600;color:var(--label-2);letter-spacing:.05em;
  text-transform:uppercase;margin:24px 0 10px;}
.sb-title:first-child{margin-top:0;}
.sb-item{font-size:13px;color:var(--label-2);line-height:1.55;margin-bottom:8px;letter-spacing:-.008em;}
.sb-item b{color:var(--label);font-weight:600;}
.sb-note{font-size:12.5px;color:var(--label-2);line-height:1.55;background:var(--fill);
  border-radius:14px;padding:13px 15px;margin-top:12px;letter-spacing:-.008em;}
.sb-note b{color:var(--label);font-weight:600;}
.sb-pill{display:inline-block;font-size:11px;color:var(--label-2);background:var(--fill);
  border-radius:8px;padding:5px 10px;margin:0 5px 6px 0;font-weight:500;letter-spacing:-.005em;}

[data-testid="stChatMessage"]{background:transparent;padding:.2rem 0;}
[data-testid="stChatMessageContent"]{font-size:15px;line-height:1.55;color:var(--label);letter-spacing:-.011em;}
[data-testid="stChatMessageAvatarUser"]{background:var(--label) !important;border:none !important;}
[data-testid="stChatMessageAvatarUser"] *{color:#FFF !important;fill:#FFF !important;}
[data-testid="stChatMessageAvatarAssistant"]{background:var(--green-v) !important;border:none !important;}
[data-testid="stChatMessageAvatarAssistant"] *{color:#FFF !important;fill:#FFF !important;}
.stChatMessage:has([data-testid="stChatMessageAvatarAssistant"]) [data-testid="stChatMessageContent"]{
  background:var(--surface);border-radius:var(--r);padding:18px 20px;box-shadow:var(--shadow);}
.stChatMessage:has([data-testid="stChatMessageAvatarUser"]) [data-testid="stChatMessageContent"]{
  background:var(--fill);border-radius:18px;padding:12px 16px;}

[data-testid="stChatMessageContent"] h1,
[data-testid="stChatMessageContent"] h2,
[data-testid="stChatMessageContent"] h3{
  font-size:15px !important;font-weight:600 !important;color:var(--label) !important;
  letter-spacing:-.014em !important;text-transform:none !important;line-height:1.35 !important;
  margin:20px 0 8px !important;padding:0 !important;}
[data-testid="stChatMessageContent"] h1:first-child,
[data-testid="stChatMessageContent"] h2:first-child,
[data-testid="stChatMessageContent"] h3:first-child{margin-top:0 !important;}
[data-testid="stChatMessageContent"] p{margin-bottom:11px;}
[data-testid="stChatMessageContent"] ul,[data-testid="stChatMessageContent"] ol{margin:6px 0 12px;padding-left:20px;}
[data-testid="stChatMessageContent"] li{margin-bottom:7px;line-height:1.55;}
[data-testid="stChatMessageContent"] li::marker{color:var(--label-3);}
[data-testid="stChatMessageContent"] strong{font-weight:600;}
[data-testid="stChatMessageContent"] code{font-family:ui-monospace,"SF Mono",Menlo,monospace;
  font-size:12px;background:var(--fill);color:var(--label-2);padding:2px 6px;border-radius:6px;}
[data-testid="stChatMessageContent"] table{font-size:13px;border-collapse:collapse;margin:12px 0;width:100%;}
[data-testid="stChatMessageContent"] th{font-weight:600;text-align:left;color:var(--label-2);font-size:12px;}
[data-testid="stChatMessageContent"] th,[data-testid="stChatMessageContent"] td{
  border-bottom:1px solid var(--sep);padding:9px 14px 9px 0;font-variant-numeric:tabular-nums;}

div.stButton>button{background:var(--surface);border:none;color:var(--label);border-radius:16px;
  font-size:14px;font-weight:400;padding:16px 18px;text-align:left;line-height:1.45;
  letter-spacing:-.011em;height:100%;box-shadow:var(--shadow);
  transition:transform .18s cubic-bezier(.4,0,.2,1),box-shadow .18s;}
div.stButton>button:hover{transform:scale(1.015);
  box-shadow:0 2px 4px rgba(0,0,0,.05),0 12px 30px -8px rgba(0,0,0,.14);color:var(--label);}
div.stButton>button:active{transform:scale(.985);}
div.stButton>button:focus:not(:active){color:var(--label);box-shadow:var(--shadow),0 0 0 3px rgba(52,199,89,.28);}

[data-testid="stExpander"]{border:none;background:transparent;margin-top:6px;}
[data-testid="stExpander"] details{border:none;background:transparent;}
[data-testid="stExpander"] summary{font-size:12.5px;color:var(--green);font-weight:500;padding:4px 0;
  letter-spacing:-.008em;}
[data-testid="stExpander"] [data-testid="stExpanderDetails"]{color:var(--label-2);font-size:12px;padding:4px 0 6px;}
[data-testid="stExpander"] [data-testid="stExpanderDetails"] code{font-size:11px;background:transparent;
  color:var(--label-2);padding:0;word-break:break-all;}

[data-testid="stChatInput"]{border:none;border-radius:22px;background:var(--surface);
  box-shadow:0 2px 6px rgba(0,0,0,.05),0 12px 32px -10px rgba(0,0,0,.16);}
[data-testid="stChatInput"]:focus-within{box-shadow:0 2px 6px rgba(0,0,0,.05),
  0 12px 32px -10px rgba(0,0,0,.16),0 0 0 3px rgba(52,199,89,.26);}
[data-testid="stChatInput"] textarea{font-size:15px;color:var(--label);letter-spacing:-.011em;}
[data-testid="stChatInput"] button{background:var(--green-v);border-radius:50%;transition:transform .15s;}
[data-testid="stChatInput"] button:hover{transform:scale(1.08);}
[data-testid="stChatInput"] button svg{color:#FFF;fill:#FFF;}

[data-testid="stSpinner"] p{font-size:13px;color:var(--label-2);letter-spacing:-.008em;}
a{color:var(--green) !important;}
.sa-foot{text-align:center;font-size:12px;color:var(--label-3);margin-top:30px;letter-spacing:-.005em;}
</style>
"""
st.markdown(BRAND_CSS, unsafe_allow_html=True)

st.markdown(
    """
    <div class="sa-header">
      <div class="sa-emblem">🏛️</div>
      <div class="sa-htext">
        <h1>Swarna Andhra <span>GVA Assistant</span></h1>
        <p>Pahlé India Foundation · aligned with Swarna Andhra @2047</p>
      </div>
      <div class="sa-badge">Prototype</div>
    </div>
    <div class="sa-sub">Ask about GDP / GSDP estimation, GVA calculation, district economic profiles,
    or any constituency and mandal vision plan — answered from official material with sources.</div>
    """,
    unsafe_allow_html=True,
)

index = load_index()
if index is None:
    st.error("No index found. Run `python embed_index.py` to build the corpus index.")
    st.stop()

if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending" not in st.session_state:
    st.session_state.pending = None

# starter prompts, grouped so the welcome screen shows what the assistant can actually do
EXAMPLE_GROUPS = [
    ("District data", "figures straight from the official workbook", [
        "What is the GDDP and per capita income of Kakinada?",
        "Which sectors give Visakhapatnam its comparative advantage?",
    ]),
    ("Methodology", "how the estimates are produced", [
        "How is district income estimated — top-down or bottom-up?",
        "What is the difference between GVA and GDP?",
    ]),
    ("Vision plans", "constituency and mandal action plans", [
        "Economic priorities in the Bapatla constituency vision plan?",
        "What is the paddy productivity target for Anaparthi mandal?",
    ]),
]

with st.sidebar:
    st.markdown("<div class='sb-title'>What's inside</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='sb-item'><span class='sb-dot'>▸</span><span>"
        "<b>28</b> districts, four years of GSDP and DDP data</span></div>"
        "<div class='sb-item'><span class='sb-dot'>▸</span><span>"
        "<b>175</b> constituency and <b>1,378</b> mandal vision plans</span></div>"
        "<div class='sb-item'><span class='sb-dot'>▸</span><span>"
        "Official DDP and GSVA methodology guidelines</span></div>"
        "<div class='sb-item'><span class='sb-dot'>▸</span><span>"
        "Sector case studies and training material</span></div>",
        unsafe_allow_html=True)

    st.markdown("<div class='sb-title'>How to read answers</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='sb-item'><span class='sb-dot'>▸</span><span>"
        "Every answer cites the source file it drew from</span></div>"
        "<div class='sb-item'><span class='sb-dot'>▸</span><span>"
        "If a figure is not in the corpus, it says so rather than guessing</span></div>",
        unsafe_allow_html=True)
    st.markdown(
        "<div class='sb-note'><b>Reliability.</b> Numeric lookups are reliable. "
        "Open-ended interpretive questions are weaker and can vary between asks, "
        "so verify anything you plan to quote.</div>",
        unsafe_allow_html=True)

    st.markdown("<div class='sb-title'>Build</div>", unsafe_allow_html=True)
    st.markdown(
        f"<span class='sb-pill'>{os.environ.get('GEMINI_MODEL','model') if os.environ.get('LLM_PROVIDER')=='gemini' else os.environ.get('LLM_PROVIDER','model')}</span> "
        "<span class='sb-pill'>voyage-4-nano</span> <span class='sb-pill'>prototype</span>",
        unsafe_allow_html=True)

# welcome screen with starter questions (only before the first message)
if not st.session_state.messages:
    st.markdown(
        "<div class='sa-stats'>"
        "<div class='sa-stat'><div class='v'>59,388</div><div class='k'>indexed chunks</div></div>"
        "<div class='sa-stat'><div class='v'>28</div><div class='k'>districts</div></div>"
        "<div class='sa-stat'><div class='v'>175</div><div class='k'>constituencies</div></div>"
        "<div class='sa-stat'><div class='v'>1,378</div><div class='k'>vision documents</div></div>"
        "</div>",
        unsafe_allow_html=True)

    n = 0
    for title, blurb, prompts in EXAMPLE_GROUPS:
        st.markdown(f"<div class='sa-label'>{title} <span>· {blurb}</span></div>",
                    unsafe_allow_html=True)
        cols = st.columns(2)
        for j, ex in enumerate(prompts):
            if cols[j].button(ex, key=f"ex{n}", use_container_width=True):
                st.session_state.pending = ex
                st.rerun()
            n += 1

# replay history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant" and msg.get("sources"):
            with st.expander("Sources"):
                st.markdown(msg["sources"])


def handle_query(user_input):
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    district_folder = detect_district(user_input)
    # follow-up handling: carry over the last district mentioned when this turn names none
    if not district_folder:
        for m in reversed(st.session_state.messages[:-1]):
            if m["role"] == "user":
                prev = detect_district(m["content"])
                if prev:
                    district_folder = prev
                    break

    try:
        hits = retrieve(user_input, index, district_folder=district_folder)
    except Exception as e:
        msg = ("The search service is temporarily unavailable (embedding quota reached). "
               "Please try again shortly.") if "429" in str(e) or "quota" in str(e).lower() \
              else f"Sorry, search failed: {e}"
        with st.chat_message("assistant"):
            st.markdown(msg)
        st.session_state.messages.append({"role": "assistant", "content": msg, "sources": ""})
        return
    context_block = build_context_block(hits)
    history = [
        {"role": m["role"], "content": m["content"][:600]}
        for m in st.session_state.messages[:-1][-4:]
    ]
    llm_messages = (
        [{"role": "system", "content": SYSTEM_PROMPT}]
        + history
        + [{"role": "user", "content": f"CONTEXT:\n{context_block}\n\nQUESTION: {user_input}"}]
    )

    with st.chat_message("assistant"):
        with st.spinner("Searching the corpus and drafting an answer…"):
            try:
                answer = call_llm(llm_messages)
            except KeyError as e:
                answer = f"Missing API key: {e}."
            except Exception as e:
                answer = f"Sorry, something went wrong: {e}"
        st.markdown(answer)
        sources_md = ""
        if hits:
            seen = []
            for h in hits:
                lbl = _label(h["source"], h["page"])
                if lbl not in seen:
                    seen.append(lbl)
            sources_md = "\n".join(f"- `{s}`" for s in seen[:8])
            with st.expander("Sources"):
                st.markdown(sources_md)

    st.session_state.messages.append(
        {"role": "assistant", "content": answer, "sources": sources_md}
    )


typed = st.chat_input("Ask about a district, a vision plan, or GVA methodology…")
query = typed or st.session_state.pending
st.session_state.pending = None
if query:
    handle_query(query)
    st.rerun()

st.markdown("<div class='sa-foot'>Grounded in official Swarna Andhra training material · answers may be approximate</div>",
            unsafe_allow_html=True)
