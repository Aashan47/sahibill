#!/usr/bin/env bash
# Ships the app and the built frontend to the server, installs what it runs, restarts the service and checks it.
# Usage: VM=user@host SSH_KEY=~/.ssh/key SSH_PORT=22 deploy/deploy.sh
# The server keeps its own ~/sahibill/env (keys and the spending cap live only there); this script never sends a key,
# and never sends fixtures, real bills, NEPRA PDFs or the local cache.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
: "${VM:?set VM=user@host}"
SSH_PORT="${SSH_PORT:-22}"
SSH=(ssh -p "$SSH_PORT" ${SSH_KEY:+-i "$SSH_KEY"})
RSYNC_SSH="ssh -p $SSH_PORT ${SSH_KEY:+-i $SSH_KEY}"

(cd "$ROOT/frontend" && npm run build)
test -f "$ROOT/web/dist/index.html"

"${SSH[@]}" "$VM" 'mkdir -p ~/sahibill/app ~/sahibill/cache'
rsync -az --delete -e "$RSYNC_SSH" --exclude __pycache__ --exclude '*.pyc' \
  --include 'sahibill/***' --include 'web/***' --include 'deploy/***' --include 'pyproject.toml' --include 'LICENSE' \
  --exclude '*' "$ROOT/" "$VM:sahibill/app/"

"${SSH[@]}" "$VM" bash -s <<'REMOTE'
set -euo pipefail
cd ~/sahibill
if [ ! -x .venv/bin/python ]; then ~/.local/bin/uv venv -q --python 3.12 .venv; fi
~/.local/bin/uv pip install -q --python .venv/bin/python -r app/deploy/requirements.txt
touch env && chmod 600 env
sudo cp app/deploy/sahibill.service /etc/systemd/system/sahibill.service
sudo systemctl daemon-reload
sudo systemctl enable -q sahibill
sudo systemctl restart sahibill
for i in 1 2 3 4 5 6 7 8 9 10; do curl -fsS http://127.0.0.1:8420/api/health && exit 0; sleep 2; done
echo "SahiBill did not answer on 127.0.0.1:8420"; sudo journalctl -u sahibill -n 30 --no-pager; exit 1
REMOTE
