#!/usr/bin/env bash
# Refresh MIZITO_TOKEN when the API starts returning 401/403.
#
# Opens an ISOLATED Chrome (its own profile, never your everyday browser),
# waits for a manual login, then writes the new token to .env (0600).
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
PY="$HERE/.venv/bin/python"

echo "1/3 launching isolated Chrome (CDP :9333)..."
bash "$HERE/tools/launch-chrome.sh" >/dev/null 2>&1 &
sleep 8

if ! curl -s --max-time 5 http://127.0.0.1:9333/json >/dev/null; then
  echo "ERROR: CDP not reachable on :9333. Is a Chrome already using that port?" >&2
  exit 1
fi

echo "2/3 >>> LOG IN to Mizito in the Chrome window that just opened, then press Enter."
read -r _

echo "3/3 extracting token..."
"$PY" "$HERE/tools/grab_auth.py"

pkill -f "remote-debugging-port=9333" 2>/dev/null || true
echo "done. .env updated; restart your MCP client to pick it up."
