"""The only module that talks HTTP to Mizito.

Mizito's SPA calls `invokeApi("ns.method", body)`, which becomes
`POST {base}/api/ns/method` with a JSON body. Auth is one `x-token` header.

Status codes double as an oracle (useful when probing new endpoints):
  405 -> endpoint does not exist
  400 -> endpoint exists, body wrong (or no permission on that object)
  401 -> token missing/revoked
Error pages are HTML, never JSON, so there is no server message to surface.

Reads are retried on network errors / 429 / 5xx. Writes are NEVER retried:
a timed-out write may still have landed, so the caller must read back first.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Callable

import httpx
from fastmcp.exceptions import ToolError

log = logging.getLogger("mizito.client")

RETRY_STATUSES = {429, 500, 502, 503, 504}


class MizitoError(ToolError):
    """Base class. Messages are written for the calling agent and never
    contain the token or response bodies."""


class AuthError(MizitoError):
    pass


class EndpointMissing(MizitoError):
    pass


class BadRequest(MizitoError):
    pass


class UpstreamError(MizitoError):
    pass


class AppError(MizitoError):
    """HTTP 200 whose body says the operation failed (an i18n error key)."""


class LookupError_(MizitoError):
    """A name/id the caller passed could not be resolved (or was ambiguous)."""


AUTH_HINT = ("Mizito rejected the token (HTTP {code}). The session was revoked "
             "(logout elsewhere / password change). Fix: run "
             "tools/refresh-auth.sh, then restart the MCP client.")


class MizitoClient:
    def __init__(
        self,
        token: str,
        base_url: str = "https://app.mizito.ir",
        workspace_id: str | None = None,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
        max_retries: int = 2,
        backoff: float = 0.6,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._token = token
        self._max_retries = max_retries
        self._backoff = backoff
        self._sleep = sleep
        headers = {
            "x-token": token,
            "content-type": "application/json",
            "origin": "https://office.mizito.ir",
            "referer": "https://office.mizito.ir/",
        }
        # No workspace header: Mizito binds the workspace to the token and the
        # SPA sends none (docs/API.md). `workspace_id` is accepted for
        # compatibility and ignored, so switch_workspace cannot be undermined
        # by a stale header.
        del workspace_id
        self._http = httpx.Client(base_url=base_url, headers=headers,
                                  timeout=timeout, transport=transport)

    @property
    def has_token(self) -> bool:
        return bool(self._token)

    def token_for_swap(self) -> str:
        """Current token, only for keeping it in memory across a workspace
        switch. Never return it from a tool."""
        return self._token

    def set_token(self, token: str) -> None:
        """Swap the session token in memory (workspace switching). Never
        persisted by the client itself."""
        self._token = token
        self._http.headers["x-token"] = token

    def close(self) -> None:
        self._http.close()

    # ------------------------------------------------------------------ core

    def call(self, endpoint: str, body: Any = None, *, write: bool = False) -> Any:
        """POST `endpoint` ("tasks/get" or "tasks.get") and return parsed JSON.

        `write=True` disables retries (see module docstring).
        """
        if not self._token:
            raise AuthError("MIZITO_TOKEN is not set. Run tools/refresh-auth.sh "
                            "(writes .env) and restart the MCP client.")
        ep = endpoint.strip("/").replace(".", "/")
        path = f"/api/{ep}"
        attempts = 1 if write else 1 + self._max_retries
        payload = {} if body is None else body
        for attempt in range(1, attempts + 1):
            t0 = time.monotonic()
            try:
                r = self._http.post(path, json=payload)
            except (httpx.TimeoutException, httpx.TransportError) as e:
                log.warning("mizito %s attempt=%d network_error=%s", ep, attempt,
                            type(e).__name__)
                if write:
                    raise UpstreamError(
                        f"{ep}: network error ({type(e).__name__}). The write may "
                        "or may not have been applied: read the object back "
                        "before trying again.") from None
                if attempt < attempts:
                    self._sleep(self._backoff * (2 ** (attempt - 1)))
                    continue
                raise UpstreamError(f"{ep}: Mizito unreachable after {attempts} "
                                    f"attempts ({type(e).__name__}).") from None
            ms = int((time.monotonic() - t0) * 1000)
            log.info("mizito %s status=%d ms=%d attempt=%d", ep, r.status_code, ms,
                     attempt)
            if (r.status_code in RETRY_STATUSES and not write
                    and attempt < attempts):
                self._sleep(self._retry_after(r) or
                            self._backoff * (2 ** (attempt - 1)))
                continue
            if write and r.status_code >= 500:
                raise UpstreamError(
                    f"{ep}: Mizito error HTTP {r.status_code} on a write. It may "
                    "still have been applied: read the object back before trying "
                    "again.")
            return self._parse(ep, r)
        raise UpstreamError(f"{ep}: retries exhausted")  # pragma: no cover

    @staticmethod
    def _retry_after(r: httpx.Response) -> float | None:
        raw = r.headers.get("retry-after")
        try:
            return min(float(raw), 10.0) if raw else None
        except ValueError:
            return None

    @staticmethod
    def _check_app_error(ep: str, data: Any) -> None:
        """Application errors come back as HTTP 200 in several shapes (SPA
        `invokeApi` callers): {error:"<i18n key>"}, {error:true,msg},
        {success:false,msg|message}, {ok:false,errorMessage}."""
        if not isinstance(data, dict):
            return
        err = data.get("error")
        failed = (bool(err) or data.get("success") is False or data.get("ok") is False)
        if not failed:
            return
        detail = next((str(v) for v in (data.get("msg"), data.get("message"),
                                        data.get("errorMessage"),
                                        err if isinstance(err, str) else None) if v), "")
        raise AppError(f"{ep}: Mizito refused the request"
                       + (f" ({detail[:200]})." if detail else "."))

    @staticmethod
    def _parse(ep: str, r: httpx.Response) -> Any:
        sc = r.status_code
        if 200 <= sc < 300:
            if not r.content:
                return None
            try:
                data = r.json()
            except ValueError:
                raise UpstreamError(f"{ep}: Mizito returned a non-JSON body "
                                    f"(HTTP {sc}).") from None
            MizitoClient._check_app_error(ep, data)
            return data
        if sc in (401, 403):
            raise AuthError(AUTH_HINT.format(code=sc))
        if sc == 405:
            raise EndpointMissing(f"{ep}: endpoint does not exist (HTTP 405).")
        if sc == 400:
            raise BadRequest(
                f"{ep}: Mizito rejected the request (HTTP 400). Usually a wrong "
                "or stale id, a missing field, or no permission on that object.")
        if sc == 429:
            raise UpstreamError(f"{ep}: rate limited by Mizito (HTTP 429). "
                                "Wait a little and retry.")
        raise UpstreamError(f"{ep}: Mizito error HTTP {sc}.")
