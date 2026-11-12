#!/usr/bin/env python3
"""Rebuild docs/ENDPOINTS.md from Mizito's current SPA bundle.

The SPA (AngularJS) calls every API as `X.invokeApi("ns.method", body)`, so a
static scan of the bundle lists every endpoint plus the literal body the call
site builds. Nothing from the bundle is executed.

    .venv/bin/python -I tools/extract_endpoints.py            # download + write
    .venv/bin/python -I tools/extract_endpoints.py a_dec.js   # use a local copy

The bundle is https://office.mizito.ir/a_.js; it is served gzip-compressed
*without* a Content-Encoding header, so it is gunzipped here. Bodies shown as
a bare variable (e.g. `o`) are assembled elsewhere: open the bundle around
that call site (search for `invokeApi("ns.method"`) to see how.
"""
from __future__ import annotations

import collections
import gzip
import re
import sys
import urllib.request
from datetime import date
from pathlib import Path

BUNDLE_URL = "https://office.mizito.ir/a_.js"
OUT = Path(__file__).resolve().parents[1] / "docs" / "ENDPOINTS.md"
CALL = re.compile(r'invokeApi\(\s*"([A-Za-z0-9_]+)\.([A-Za-z0-9_.]+)"')


def load(path: str | None) -> str:
    if path:
        raw = Path(path).read_bytes()
    else:
        req = urllib.request.Request(BUNDLE_URL, headers={"User-Agent": "Mozilla/5.0"})
        raw = urllib.request.urlopen(req, timeout=60).read()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return raw.decode("utf-8", errors="replace")


def args_after(src: str, i: int, limit: int = 600) -> str:
    depth, j = 1, i
    while j < len(src) and depth and j - i < limit:
        if src[j] in "([{":
            depth += 1
        elif src[j] in ")]}":
            depth -= 1
        j += 1
    return src[i:j - 1].lstrip(",").strip()


def main() -> None:
    src = load(sys.argv[1] if len(sys.argv) > 1 else None)
    found: dict[str, set[str]] = collections.defaultdict(set)
    for m in CALL.finditer(src):
        ep = f"{m.group(1)}/{m.group(2).replace('.', '/')}"
        found[ep].add(re.sub(r"\s+", " ", args_after(src, m.end()))[:220])
    by_ns: dict[str, list[str]] = collections.defaultdict(list)
    for ep in sorted(found):
        by_ns[ep.split("/")[0]].append(ep)
    lines = [
        "# Mizito API endpoint catalog (generated)",
        "",
        f"Generated {date.today()} by `tools/extract_endpoints.py` from the SPA bundle.",
        f"{len(found)} endpoints in {len(by_ns)} namespaces. All are `POST /api/<endpoint>`",
        "with a JSON body. This lists what the SPA *calls*; whether an endpoint is",
        "wired into the MCP, and its verified body, is in docs/API.md.",
        "",
        "Body column = the literal argument text at the call site (minified).",
        "`!0` = true, `!1` = false. A bare letter means the body is built elsewhere.",
        "",
    ]
    for ns in sorted(by_ns):
        lines += [f"## {ns} ({len(by_ns[ns])})", "", "| endpoint | body at call site |", "|---|---|"]
        for ep in by_ns[ns]:
            bodies = sorted(found[ep], key=len)[:2]
            cell = " ; ".join(f"`{b}`" if b else "`{}`" for b in bodies).replace("|", "\\|")
            lines.append(f"| `{ep}` | {cell} |")
        lines.append("")
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT} ({len(found)} endpoints)")


if __name__ == "__main__":
    main()
