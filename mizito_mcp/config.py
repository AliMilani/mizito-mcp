"""Runtime settings, read once from the environment.

Every knob is an env var so the launcher (run-mcp.sh / Docker --env-file) is the
only place configuration lives. Nothing here is ever logged.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

_TRUE = {"1", "true", "yes", "on"}


def _flag(env: Mapping[str, str], name: str, default: bool = False) -> bool:
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in _TRUE


@dataclass(frozen=True)
class Settings:
    token: str
    base_url: str = "https://app.mizito.ir"
    # Informational only. Mizito binds the workspace to the TOKEN (switching
    # = `workspace/switch` mints a new token); the SPA sends no workspace
    # header. Sent as a `workspace` header when set, which the server ignores.
    workspace_id: str | None = None
    # MIZITO_READ_ONLY=1 -> write tools are not registered at all.
    read_only: bool = False
    timeout: float = 30.0
    # Seconds that users/projects/labels/dialogs stay cached in-process.
    cache_ttl: float = 300.0
    log_level: str = "WARNING"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        env = os.environ if env is None else env
        return cls(
            token=(env.get("MIZITO_TOKEN") or "").strip(),
            base_url=(env.get("MIZITO_BASE") or "https://app.mizito.ir").rstrip("/"),
            workspace_id=(env.get("MIZITO_WORKSPACE_ID") or "").strip() or None,
            read_only=_flag(env, "MIZITO_READ_ONLY"),
            timeout=float(env.get("MIZITO_TIMEOUT") or 30),
            cache_ttl=float(env.get("MIZITO_CACHE_TTL") or 300),
            log_level=(env.get("MIZITO_LOG_LEVEL") or "WARNING").upper(),
        )
