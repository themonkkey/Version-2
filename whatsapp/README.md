# WhatsApp bot

Meta Cloud API webhook wrapping the same pipeline as the Streamlit app.
Text messages and voice notes (any Indian language, via Sarvam) both work.

## One-time Meta setup (needs your account — ~15 min for the sandbox)

1. https://developers.facebook.com -> Create App -> type "Business".
2. Add the **WhatsApp** product. The console gives you, on the API Setup page:
   - a **test phone number** + its **Phone number ID**  -> `WA_PHONE_ID`
   - a **temporary access token** (24 h; make a permanent one later) -> `WA_ACCESS_TOKEN`
   - a box to register up to 5 recipient numbers for the sandbox — add your own.
3. Webhook config: URL = `https://<your-tunnel-or-server>/webhook`,
   Verify token = whatever you set as `WA_VERIFY_TOKEN`. Subscribe to `messages`.

Production later: business verification for PIF + a dedicated number, or an Indian
BSP (Gupshup/AiSensy) to skip the paperwork.

## Run

```bash
export WA_VERIFY_TOKEN=pick-anything WA_ACCESS_TOKEN=... WA_PHONE_ID=...
export LLM_PROVIDER=gemini GEMINI_API_KEY=... EMBED_PROVIDER=cohere COHERE_API_KEY=...
export SARVAM_API_KEY=...   # only needed for voice notes
uvicorn whatsapp.server:app --port 8000
# separate terminal — public HTTPS for Meta's webhook:
cloudflared tunnel --url http://localhost:8000
```

Message the test number from your registered phone. Voice notes get a
"Heard: <english text>" echo, then the answer.

## Notes

- Replies are capped at 200 words / plain text (WhatsApp style block in server.py).
- Message ids are deduped in memory (Meta retries webhooks).
- `/health` returns the loaded index size.
