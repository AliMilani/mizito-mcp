#!/usr/bin/env bash
# Mizito MCP launcher. The token lives in an env file (0600), never in argv or
# in the MCP client's config.
#
#   MIZITO_ENV_FILE  env file to source (default: .env next to this script).
#                    Optional when MIZITO_TOKEN is already in the environment.
#   MIZITO_PYTHON    interpreter (default: .venv/bin/python, else python3)
set -euo pipefail
cd "$(dirname "$0")"

env_file="${MIZITO_ENV_FILE:-.env}"
if [ -f "$env_file" ]; then
  set -a
  # shellcheck disable=SC1090
  . "$env_file"
  set +a
elif [ -z "${MIZITO_TOKEN:-}" ]; then
  echo "mizito-mcp: $env_file not found and MIZITO_TOKEN is not set" >&2
  exit 1
fi

py="${MIZITO_PYTHON:-}"
if [ -z "$py" ]; then
  if [ -x .venv/bin/python ]; then py=.venv/bin/python; else py=python3; fi
fi
exec "$py" server.py
