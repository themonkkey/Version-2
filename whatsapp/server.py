"""WhatsApp front door for the Swarna Andhra assistant.

Meta Cloud API webhook -> the SAME pipeline the Streamlit app uses
(detect_district -> retrieve -> build_context_block -> call_llm), plus
sarvam.py for voice notes (any Indian language speech -> English text).

Run locally:
    uvicorn whatsapp.server:app --port 8000
    # expose for Meta's webhook: cloudflared tunnel --url http://localhost:8000

Env (in addition to the app's own GEMINI_API_KEY / EMBED_PROVIDER / etc.):
    WA_VERIFY_TOKEN   any string you choose; paste the same one in the Meta console
    WA_ACCESS_TOKEN   Meta access token (temporary token works for the sandbox)
    WA_PHONE_ID       the "Phone number ID" from the Meta console (not the number)
"""
import os
import sys
import re
import logging
from collections import OrderedDict

import requests
from fastapi import FastAPI, Request, Response

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import st_stub  # noqa: F401  (must precede app import)
import app as bot
import sarvam

log = logging.getLogger("whatsapp")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

GRAPH = "https://graph.facebook.com/v21.0"

# WhatsApp reads on a phone: short, plain, no markdown tables. Layered on top of the
# production prompt so the discipline/example rules still apply.
WA_STYLE = (
    "\n\nThis conversation happens on WhatsApp. Keep the answer under 200 words, plain "
    "text only (no markdown tables, no headers). Cite the source file name in "
    "parentheses at the end."
)

app = FastAPI()
_INDEX = None


def index():
    global _INDEX
    if _INDEX is None:
        _INDEX = bot.load_index()
    return _INDEX


# Meta retries webhooks on slow/failed responses — answer each message id once.
_seen = OrderedDict()


def seen(msg_id):
    if msg_id in _seen:
        return True
    _seen[msg_id] = True
    while len(_seen) > 500:
        _seen.popitem(last=False)
    return False


def answer(question):
    df = bot.detect_district(question)
    hits = bot.retrieve(question, index(), district_folder=df)
    block = bot.build_context_block(hits, query=question, district_folder=df)
    messages = [
        {"role": "system", "content": bot.SYSTEM_PROMPT + WA_STYLE},
        {"role": "user", "content": f"CONTEXT:\n{block}\n\nQUESTION: {question}"},
    ]
    return bot.call_llm(messages).strip()[:4000]


def send_text(to, text):
    r = requests.post(
        f"{GRAPH}/{os.environ['WA_PHONE_ID']}/messages",
        headers={"Authorization": f"Bearer {os.environ['WA_ACCESS_TOKEN']}"},
        json={"messaging_product": "whatsapp", "to": to,
              "type": "text", "text": {"body": text}},
        timeout=30,
    )
    if r.status_code != 200:
        log.error("send failed %s: %s", r.status_code, r.text[:300])


def fetch_media(media_id):
    """Voice notes arrive as a media id; resolve it to bytes via the Graph API."""
    headers = {"Authorization": f"Bearer {os.environ['WA_ACCESS_TOKEN']}"}
    meta = requests.get(f"{GRAPH}/{media_id}", headers=headers, timeout=30).json()
    audio = requests.get(meta["url"], headers=headers, timeout=60)
    return audio.content, meta.get("mime_type", "audio/ogg")


@app.get("/webhook")
def verify(request: Request):
    q = request.query_params
    if q.get("hub.verify_token") == os.environ.get("WA_VERIFY_TOKEN"):
        return Response(q.get("hub.challenge", ""), media_type="text/plain")
    return Response("forbidden", status_code=403)


@app.post("/webhook")
def receive(payload: dict):
    try:
        value = payload["entry"][0]["changes"][0]["value"]
        msgs = value.get("messages") or []
    except (KeyError, IndexError):
        return {"ok": True}
    for m in msgs:
        if seen(m.get("id")):
            continue
        sender = m["from"]
        try:
            if m["type"] == "text":
                q = m["text"]["body"].strip()
            elif m["type"] == "audio":
                blob, mime = fetch_media(m["audio"]["id"])
                ext = "ogg" if "ogg" in mime else "mp3"
                q = sarvam.transcribe(blob, filename=f"note.{ext}", mode="translate")
                send_text(sender, f"Heard: {q}")
            else:
                send_text(sender, "Please send a text message or a voice note.")
                continue
            if not q:
                continue
            log.info("Q from %s: %s", sender[-4:], q[:120])
            send_text(sender, answer(q))
        except Exception as e:
            log.exception("failed handling message")
            send_text(sender, "Sorry, something went wrong. Please try again shortly.")
    return {"ok": True}


@app.get("/health")
def health():
    return {"ok": True, "index_chunks": len(index()["chunks"])}
