"""Embedding provider abstraction for the Swarna Andhra RAG index.

Swappable by env var EMBED_PROVIDER, exactly like the LLM in app.py:
  - "cohere" (default): embed-english-v3.0, no-card trial key, high RPM. Needs COHERE_API_KEY.
  - "voyage": voyage-3.5-lite, generous free tokens but only 3 RPM without a card. Needs VOYAGE_API_KEY.
  - "gemini": Google gemini-embedding-001, free but ~1000/day cap. Needs GEMINI_API_KEY.
  - "openai": text-embedding-3-small, cheap + high quality. Needs OPENAI_API_KEY.

Both return L2-normalized float32 vectors so cosine similarity is a plain dot product.
The index MUST be built and queried with the same provider + model (vector spaces
are not interchangeable) — the model name is stamped into the saved index and checked
at load time.
"""
import os

import numpy as np

# voyage-4-nano, run locally from open weights (Apache 2.0). 32k context, so no chunk
# is ever truncated -- 18.4% of the corpus exceeds Cohere v3's 512-token cap today and
# is silently cut. Native output is 2048-dim; Matryoshka lets us keep the first 1024 so
# the stored matrix stays the same size as the Cohere index it replaces.
VOYAGE_LOCAL_MODEL = os.environ.get("EMBED_MODEL", "voyageai/voyage-4-nano")
VOYAGE_LOCAL_DIM = int(os.environ.get("EMBED_DIM", "1024"))
_VOYAGE_LOCAL = None

COHERE_MODEL = os.environ.get("EMBED_MODEL", "embed-english-v3.0")
VOYAGE_MODEL = os.environ.get("EMBED_MODEL", "voyage-3.5-lite")
GEMINI_MODEL = os.environ.get("EMBED_MODEL", "gemini-embedding-001")
OPENAI_MODEL = os.environ.get("EMBED_MODEL", "text-embedding-3-small")
# gemini-embedding-001 is natively 3072-dim; Matryoshka truncation to 768 keeps
# retrieval quality while shrinking the stored matrix ~4x (deploy-friendly RAM).
GEMINI_DIM = int(os.environ.get("EMBED_DIM", "768"))
# task types let Gemini optimize doc-vs-query embeddings differently
_GEMINI_DOC_TASK = "RETRIEVAL_DOCUMENT"
_GEMINI_QUERY_TASK = "RETRIEVAL_QUERY"


def provider():
    return os.environ.get("EMBED_PROVIDER", "cohere").lower()


def model_id():
    p = provider()
    if p == "voyage_local":
        return f"voyage_local:{VOYAGE_LOCAL_MODEL}:{VOYAGE_LOCAL_DIM}"
    if p == "cohere":
        return f"cohere:{COHERE_MODEL}"
    if p == "voyage":
        return f"voyage:{VOYAGE_MODEL}"
    if p == "gemini":
        return f"gemini:{GEMINI_MODEL}"
    if p == "openai":
        return f"openai:{OPENAI_MODEL}"
    raise RuntimeError(f"Unknown EMBED_PROVIDER: {p}")


def _normalize(mat):
    mat = np.asarray(mat, dtype=np.float32)
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return mat / norms


def _voyage_local_model():
    """Load the local model once and keep it. Costs ~50s and ~1.5GB RAM on first call."""
    global _VOYAGE_LOCAL
    if _VOYAGE_LOCAL is None:
        import torch
        from sentence_transformers import SentenceTransformer

        device = os.environ.get("EMBED_DEVICE")
        if not device:
            device = "mps" if torch.backends.mps.is_available() else "cpu"
        _VOYAGE_LOCAL = SentenceTransformer(
            VOYAGE_LOCAL_MODEL, trust_remote_code=True, device=device)
    return _VOYAGE_LOCAL


def _embed_voyage_local(texts, is_query, batch_size=16):
    """Embed locally, using the model's own query/document prompts.

    The two are not interchangeable: the model prepends a different instruction to each,
    which is what gives asymmetric retrieval its advantage.
    """
    m = _voyage_local_model()
    fn = m.encode_query if is_query else m.encode_document
    vecs = fn(texts, batch_size=batch_size, show_progress_bar=False,
              convert_to_numpy=True)
    # Matryoshka truncation: the first N dimensions are a valid embedding on their own,
    # provided they are re-normalized (which _normalize does on the way out).
    if VOYAGE_LOCAL_DIM and vecs.shape[1] > VOYAGE_LOCAL_DIM:
        vecs = vecs[:, :VOYAGE_LOCAL_DIM]
    return vecs


def _embed_cohere(texts, is_query, api_key=None):
    import requests

    key = api_key or os.environ["COHERE_API_KEY"]
    r = requests.post(
        "https://api.cohere.com/v2/embed",
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json"},
        json={"texts": texts, "model": COHERE_MODEL,
              "input_type": "search_query" if is_query else "search_document",
              "embedding_types": ["float"]},
        timeout=60,
    )
    if r.status_code != 200:
        raise RuntimeError(f"cohere {r.status_code}: {r.text[:200]}")
    return r.json()["embeddings"]["float"]


def _embed_voyage(texts, is_query):
    import requests

    r = requests.post(
        "https://api.voyageai.com/v1/embeddings",
        headers={"Authorization": f"Bearer {os.environ['VOYAGE_API_KEY']}",
                 "Content-Type": "application/json"},
        json={"input": texts, "model": VOYAGE_MODEL,
              "input_type": "query" if is_query else "document"},
        timeout=60,
    )
    if r.status_code != 200:
        raise RuntimeError(f"voyage {r.status_code}: {r.text[:200]}")
    data = r.json()["data"]
    return [d["embedding"] for d in data]


def _embed_gemini(texts, is_query):
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    task = _GEMINI_QUERY_TASK if is_query else _GEMINI_DOC_TASK
    resp = client.models.embed_content(
        model=GEMINI_MODEL,
        contents=texts,
        config=types.EmbedContentConfig(task_type=task, output_dimensionality=GEMINI_DIM),
    )
    return [e.values for e in resp.embeddings]


def _embed_openai(texts, is_query):
    from openai import OpenAI

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    resp = client.embeddings.create(model=OPENAI_MODEL, input=texts)
    return [d.embedding for d in resp.data]


def embed(texts, is_query=False, api_key=None):
    """Embed a list of strings -> L2-normalized float32 array (n, dim).

    api_key overrides the env key for that call (used for multi-key rotation).
    """
    if isinstance(texts, str):
        texts = [texts]
    p = provider()
    if p == "voyage_local":
        vecs = _embed_voyage_local(texts, is_query)
    elif p == "cohere":
        vecs = _embed_cohere(texts, is_query, api_key=api_key)
    elif p == "voyage":
        vecs = _embed_voyage(texts, is_query)
    elif p == "gemini":
        vecs = _embed_gemini(texts, is_query)
    elif p == "openai":
        vecs = _embed_openai(texts, is_query)
    else:
        raise RuntimeError(f"Unknown EMBED_PROVIDER: {p}")
    return _normalize(vecs)


def _cohere_keys():
    """All configured Cohere keys, in order. COHERE_API_KEYS (comma-separated)
    lets us rotate across several trial keys; falls back to the single key."""
    keys = [k.strip() for k in os.environ.get("COHERE_API_KEYS", "").split(",") if k.strip()]
    if not keys:
        single = os.environ.get("COHERE_API_KEY", "").strip()
        keys = [single] if single else []
    return keys


def embed_query(text):
    """Embed one query. For Cohere, rotate across all configured keys so a single
    quota-exhausted (429) trial key does not take the whole app down."""
    if provider() != "cohere":
        return embed([text], is_query=True)[0]
    keys = _cohere_keys()
    if not keys:
        raise RuntimeError("No Cohere API key configured (set COHERE_API_KEYS or COHERE_API_KEY).")
    last = None
    for key in keys:
        try:
            return embed([text], is_query=True, api_key=key)[0]
        except RuntimeError as e:
            last = e
            if "429" in str(e):  # rate or monthly-quota limit — try the next key
                continue
            raise
    raise RuntimeError(f"All Cohere keys are rate/quota limited: {last}")
