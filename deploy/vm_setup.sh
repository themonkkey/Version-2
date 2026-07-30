#!/usr/bin/env bash
# Provision a fresh Linux VM (Oracle Always Free ARM / Hetzner / any Ubuntu box) to run
# the Swarna Andhra assistant with LOCAL voyage-4-nano embeddings -- no embedding API key,
# no quota. Tested target: Ubuntu 22.04+, arm64 or x86_64, >=4 GB RAM.
#
# Run ON THE VM as a sudo-capable user:
#   curl -fsSL https://raw.githubusercontent.com/themonkkey/swarna-andhra-chatbot/main/deploy/vm_setup.sh | bash
# or copy it over and: bash vm_setup.sh
set -euo pipefail

REPO="https://github.com/themonkkey/swarna-andhra-chatbot.git"
APP_DIR="$HOME/swarna-andhra-chatbot"
PY=python3

echo "==> system packages"
sudo apt-get update -qq
sudo apt-get install -y -qq python3-venv python3-pip git git-lfs build-essential
git lfs install

echo "==> clone/update repo"
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" pull --ff-only
else
  git clone --depth 1 "$REPO" "$APP_DIR"
fi
cd "$APP_DIR"

echo "==> python env"
[ -d venv ] || $PY -m venv venv
./venv/bin/pip install -q --upgrade pip
# transformers must stay <5: voyage-4-nano's remote code sets config_class=None, which
# transformers 5.x rejects with an opaque AttributeError at load time.
./venv/bin/pip install -q streamlit numpy requests groq "transformers<5" torch sentence-transformers

echo "==> voyage index"
# The index (~300 MB) is NOT in git -- it exceeds GitHub's file limits and would bloat the
# repo. Fetch it from wherever you published it, or scp it up from your Mac:
#   scp -r voyage_out/ user@<vm-ip>:~/swarna-andhra-chatbot/
if [ ! -f voyage_out/voyage_index.npz ]; then
  echo "  !! voyage_out/voyage_index.npz missing."
  echo "  !! From your Mac, run:"
  echo "     scp ~/swarna-andhra-chatbot/voyage_out/voyage_index.npz \\"
  echo "         ~/swarna-andhra-chatbot/voyage_out/voyage_chunks.pkl \\"
  echo "         \$USER@<vm-ip>:$APP_DIR/voyage_out/"
  mkdir -p voyage_out
fi

echo "==> warm the model cache (downloads ~670 MB once, so first user request is fast)"
EMBED_PROVIDER=voyage_local EMBED_DEVICE=cpu ./venv/bin/python - <<'PY' || echo "  (skipped: run again after index is present)"
import embeddings
m = embeddings._voyage_local_model()
print("  model ready:", m.max_seq_length, "tokens,", m.device)
PY

echo "==> systemd service"
sudo tee /etc/systemd/system/swarna.service >/dev/null <<EOF
[Unit]
Description=Swarna Andhra GVA Assistant
After=network.target

[Service]
User=$USER
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
Environment=EMBED_PROVIDER=voyage_local
Environment=EMBED_DEVICE=cpu
Environment=LLM_PROVIDER=groq
ExecStart=$APP_DIR/venv/bin/streamlit run app.py \\
  --server.port=8501 --server.address=0.0.0.0 --server.headless=true
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now swarna

cat <<EOF

==> done.

  Create $APP_DIR/.env with just:
      GROQ_API_KEY=<your groq key>
  (No Cohere key needed -- embeddings run locally.)

  Then:  sudo systemctl restart swarna
  Logs:  journalctl -u swarna -f
  App:   http://<vm-ip>:8501

  Oracle Cloud only -- open the port in BOTH places or it will appear dead:
    1. VCN security list: ingress TCP 8501 from 0.0.0.0/0
    2. On the VM:  sudo iptables -I INPUT -p tcp --dport 8501 -j ACCEPT
                   sudo netfilter-persistent save
  (Oracle images ship with a restrictive iptables ruleset that ignores the console rules.)
EOF
