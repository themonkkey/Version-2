"""Sarvam AI speech-to-text — Telugu (and any Indian language) speech into English text.

Why this exists: the corpus, the chunks and the embedding model (voyage-4-nano) are all
English. A Telugu query embedded directly against English chunks retrieves badly. So voice
input has to arrive as English *before* it reaches retrieval, not after.

One endpoint covers both cases the assistant needs:

    mode="translate"   any Indian language speech -> ENGLISH text   <- the default
    mode="transcribe"  speech -> text in the SAME language

`translate` is the default because it also handles English input (English in, English out),
so a single mic button serves a Telugu speaker and an English speaker with no language
picker and no branching. `transcribe` is kept for the cases where the verbatim Telugu is
wanted -- showing the officer what was heard, for instance.

`language_code="unknown"` asks Sarvam to auto-detect, which is what makes the single-button
design possible. The detected language comes back in the response so the UI can show it.

Pricing at time of writing: Rs 30/hour, billed per second, rounded up. A 15-second question
is about Rs 0.13.

Docs: https://docs.sarvam.ai/api-reference/speech-to-text/transcribe
"""
import os
import io
import json
import urllib.request
import urllib.error

ENDPOINT = "https://api.sarvam.ai/speech-to-text"
DEFAULT_MODEL = os.environ.get("SARVAM_MODEL", "saaras:v4")

# The REST endpoint is documented for "quick responses under 30 seconds". Longer audio needs
# the batch API, which is a different endpoint with its own polling contract -- refuse
# clearly here rather than let the request fail with something opaque.
MAX_SECONDS = 30

# Same discipline as bakeoff.py: a quota or auth failure must be recognisable as such and
# never be silently handed downstream as if it were a transcript.
QUOTA_MARKERS = ("quota", "rate limit", "rate_limit", "429", "insufficient",
                 "credit", "exhausted", "unauthorized", "invalid api", "403", "401")


class SarvamError(RuntimeError):
    """Transcription failed. `.quota` is True when the cause was credits or auth."""

    def __init__(self, msg, quota=False):
        super().__init__(msg)
        self.quota = quota


def _key():
    k = os.environ.get("SARVAM_API_KEY", "").strip()
    if not k:
        raise SarvamError("SARVAM_API_KEY is not set", quota=True)
    return k


def _multipart(fields, file_field, filename, file_bytes, content_type):
    """Build a multipart/form-data body without pulling in `requests`."""
    boundary = "----swarna" + os.urandom(12).hex()
    out = io.BytesIO()

    def w(s):
        out.write(s.encode("utf-8") if isinstance(s, str) else s)

    for k, v in fields.items():
        if v is None:
            continue
        w(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n")
    w(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{file_field}\"; "
      f"filename=\"{filename}\"\r\nContent-Type: {content_type}\r\n\r\n")
    w(file_bytes)
    w(f"\r\n--{boundary}--\r\n")
    return out.getvalue(), f"multipart/form-data; boundary={boundary}"


def transcribe(audio_bytes, filename="audio.wav", mode="translate",
               language_code="unknown", model=None, timeout=60):
    """Send audio to Sarvam and return {text, language, language_confidence, mode}.

    mode="translate" returns ENGLISH regardless of what was spoken -- use this for anything
    that feeds retrieval. mode="transcribe" returns the spoken language as-is.
    """
    if not audio_bytes:
        raise SarvamError("no audio captured")

    body, ctype = _multipart(
        {"model": model or DEFAULT_MODEL, "mode": mode, "language_code": language_code},
        "file", filename, audio_bytes, "audio/wav")

    req = urllib.request.Request(
        ENDPOINT, data=body,
        headers={"api-subscription-key": _key(), "Content-Type": ctype})

    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8")[:300]
        except Exception:
            pass
        msg = f"Sarvam HTTP {e.code}: {detail or e.reason}"
        low = (msg + " " + str(e.code)).lower()
        raise SarvamError(msg, quota=any(m in low for m in QUOTA_MARKERS)) from None
    except urllib.error.URLError as e:
        raise SarvamError(f"Sarvam unreachable: {e.reason}") from None

    text = (data.get("transcript") or "").strip()
    if not text:
        # Silence, or audio the model could not resolve. Say so rather than sending an
        # empty string into retrieval, which would return the corpus's generic top hits.
        raise SarvamError("no speech detected in the recording")

    return {
        "text": text,
        "language": data.get("language_code"),
        "language_confidence": data.get("language_probability"),
        "mode": mode,
        "request_id": data.get("request_id"),
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print(__doc__)
        print("usage: python sarvam.py <audio-file> [transcribe|translate]")
        raise SystemExit(2)
    path = sys.argv[1]
    md = sys.argv[2] if len(sys.argv) > 2 else "translate"
    res = transcribe(open(path, "rb").read(), os.path.basename(path), mode=md)
    print(json.dumps(res, ensure_ascii=False, indent=1))
