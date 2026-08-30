#!/usr/bin/env bash
# Mizito MCP launcher. Token lives in ./.env (0600), never in argv or config.
set -euo pipefail
cd "$(dirname "$0")"
set -a
# shellcheck disable=SC1091
. ./.env
set +a
exec .venv/bin/python server.py
