# Phase 02 — Deploy

Everything here is scripted. Run on the VM unless stated otherwise.

## Checklist

- [ ] Run the provisioner on the VM:
      `bash <(curl -fsSL https://raw.githubusercontent.com/themonkkey/swarna-andhra-chatbot/main/deploy/vm_setup.sh)`
- [ ] Upload the index **from your Mac** (130 MB):
      `scp -r ~/swarna-andhra-chatbot/voyage_out_512 ubuntu@<ip>:~/swarna-andhra-chatbot/`
- [ ] Create `~/swarna-andhra-chatbot/.env` on the VM containing only:
      `GROQ_API_KEY=<key>`
- [ ] Re-run the model warm-up so the first user request isn't slow
- [ ] `sudo systemctl restart swarna`
- [ ] `sudo systemctl status swarna` shows active (running)
- [ ] `journalctl -u swarna -n 50` is clean — no tracebacks
- [ ] Reboot the VM and confirm the service comes back by itself

## Challenges

**`transformers` must stay below version 5.** voyage-4-nano's remote code leaves
`config_class` as `None`, which transformers 5.x rejects with an opaque
`AttributeError: 'NoneType' object has no attribute '__name__'`. The pin is in
`vm_setup.sh` — do not "upgrade to latest" later without re-testing.

**First boot downloads ~670 MB of model weights.** On a slow link this takes a while, and
the very first query pays the full model-load cost. The warm-up step exists to move that
cost off the first user.

**`EMBED_DIM=512` must match the index.** The systemd unit sets it. If index and env ever
disagree, `app.py` raises on startup by design — a mismatch would otherwise return
plausible nonsense rather than an error. If you see that error, trust it.

**`trust_remote_code=True`** executes code from the model repo. Already accepted for this
build, but worth naming to whoever signs off on a government deployment.

**The index is not in git.** It must be `scp`'d. `vm_setup.sh` prints the exact command if
it finds the directory missing.

**Disk.** Model cache ~670 MB + index 130 MB + venv with torch ~2 GB. Budget 10 GB free.
