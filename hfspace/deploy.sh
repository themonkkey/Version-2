#!/usr/bin/env bash
# Assemble and push the Hugging Face Space.
#
# Streamlit Community Cloud cannot host this build: the free tier's ~1 GB ceiling has no
# room for a local embedding model on top of the index. HF Spaces free gives 16 GB.
#
# Prerequisites (both need YOUR credentials, so run them yourself first):
#   1. Create a Space at https://huggingface.co/new-space  (SDK: Streamlit)
#   2. venv/bin/hf auth login          # paste a token with write access
#
# Usage:  bash hfspace/deploy.sh <hf-username>/<space-name>
set -euo pipefail

SPACE="${1:-}"
[ -z "$SPACE" ] && { echo "usage: bash hfspace/deploy.sh <user>/<space>"; exit 1; }

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAGE="$REPO_ROOT/.hfspace_build"

echo "==> staging into $STAGE"
rm -rf "$STAGE"
mkdir -p "$STAGE/voyage_out" "$STAGE/.streamlit"

# application code
cp "$REPO_ROOT/app.py"          "$STAGE/"
cp "$REPO_ROOT/embeddings.py"   "$STAGE/"
cp "$REPO_ROOT/hfspace/requirements.txt" "$STAGE/"
cp "$REPO_ROOT/hfspace/README.md"        "$STAGE/"
cp "$REPO_ROOT/.streamlit/config.toml"   "$STAGE/.streamlit/"

# the voyage index -- the only large artifacts. The Cohere index, the 2.8 GB corpus and
# the benchmark suite are all deliberately NOT shipped; the Space only needs to retrieve.
cp "$REPO_ROOT/voyage_out/voyage_index.npz"  "$STAGE/voyage_out/"
cp "$REPO_ROOT/voyage_out/voyage_chunks.pkl" "$STAGE/voyage_out/"

cd "$STAGE"
git init -q
git lfs install --local
git lfs track "voyage_out/*.npz" "voyage_out/*.pkl"
git add .gitattributes

git add .
git -c user.email=deploy@local -c user.name=deploy commit -q -m "Deploy voyage-4-nano build"

echo "==> pushing to https://huggingface.co/spaces/$SPACE"
git remote add origin "https://huggingface.co/spaces/$SPACE"
git push -f origin main 2>/dev/null || { git branch -M main && git push -f origin main; }

cat <<EOF

==> pushed. Now set these in the Space UI (Settings -> Variables and secrets):

  Variables:  EMBED_PROVIDER = voyage_local
              EMBED_DEVICE   = cpu
              LLM_PROVIDER   = groq
  Secret:     GROQ_API_KEY   = <your groq key>

No Cohere key is needed -- that is the point of this build.

First boot downloads ~670 MB of model weights and will take several minutes.
EOF
