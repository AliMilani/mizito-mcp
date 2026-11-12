#!/usr/bin/env python3
"""Live smoke test over real stdio: spawn run-mcp.sh, list tools, call every
READ tool once against the real workspace, print a one-line verdict each.

Never calls write tools. Usage (from the project dir):
    .venv/bin/python tools/smoke.py            # all read tools
    .venv/bin/python tools/smoke.py --full     # also print trimmed output
Exit code 1 if any read tool fails.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

HERE = Path(__file__).resolve().parents[1]

# tool -> arguments. Names are resolved by the server, so these stay valid as
# long as the workspace has at least one project / chat.
CALLS: dict[str, dict] = {
    "whoami": {},
    "health_check": {},
    "list_workspaces": {},
    "list_workspace_users": {},
    "get_task_counts": {},
    "get_dashboard_summary": {},
    "list_projects": {},
    "get_projects_summary": {},
    "list_labels": {},
    "list_my_tasks": {"limit": 3},
    "list_tasks": {"scope": "outbox", "limit": 3},
    "search_tasks": {"query": "a", "limit": 2},
    "daily_brief": {},
    "list_chats": {"limit": 3},
    "search_messages": {"query": "سلام"},
}


async def main(full: bool) -> int:
    # MCP stdio clients pass only a minimal env to the server, so forward
    # MIZITO_* overrides (e.g. MIZITO_READ_ONLY=1) explicitly. The token still
    # comes from .env inside run-mcp.sh.
    env = {k: v for k, v in os.environ.items()
           if k.startswith("MIZITO_") and k != "MIZITO_TOKEN"}
    transport = StdioTransport(command=str(HERE / "run-mcp.sh"), args=[], cwd=str(HERE),
                               env=env or None)
    failed = 0
    async with Client(transport, timeout=120) as c:
        tools = {t.name: t for t in await c.list_tools()}
        reads = sorted(n for n, t in tools.items() if t.annotations and t.annotations.readOnlyHint)
        writes = sorted(set(tools) - set(reads))
        print(f"tools={len(tools)} read={len(reads)} write={len(writes)}")
        print("write tools:", ", ".join(writes) or "(none: read-only mode)")

        async def run(name: str, args: dict) -> object:
            nonlocal failed
            try:
                r = await c.call_tool(name, args)
                data = r.data if r.data is not None else r.structured_content
                text = json.dumps(data, ensure_ascii=False, default=str)
                print(f"OK   {name:24s} {len(text):6d} chars")
                if full:
                    print("     " + text[:400])
                return data
            except Exception as e:  # noqa: BLE001 - report every failure
                failed += 1
                print(f"FAIL {name:24s} {type(e).__name__}: {str(e)[:200]}")
                return None

        for name, args in CALLS.items():
            if name in tools:
                await run(name, args)

        # dependent calls: first project, first task, first chat
        projects = await run("list_projects", {"with_counts": False}) or []
        if projects:
            pid = projects[0]["id"]
            await run("get_project", {"project": pid})
            page = await run("list_tasks", {"project": pid, "status": "all", "limit": 2}) or {}
            if page.get("tasks"):
                tid = page["tasks"][0]["id"]
                await run("get_task", {"task_id": tid, "include_history": True})
                await run("get_task_comments", {"task_id": tid})
                await run("get_task_history", {"task_id": tid})
                await run("get_task_seen", {"task_id": tid})
            await run("get_project_chat", {"project": pid, "limit": 3})
        await run("get_user_workload", {"user": "me"})
        chats = await run("list_chats", {"limit": 1}) or []
        if chats:
            await run("read_chat", {"chat": chats[0]["id"], "limit": 3})
            await run("search_chat", {"chat": chats[0]["id"], "query": "سلام", "limit": 5})
        spaces = await run("list_workspaces", {}) or []
        cur = next((w for w in spaces if w.get("current")), None)
        other = next((w for w in spaces if not w.get("current")), None)
        if cur and other and "switch_workspace" in tools:
            await run("switch_workspace", {"workspace": other["id"]})
            await run("whoami", {})
            await run("switch_workspace", {"workspace": cur["id"]})
        untested = sorted(set(reads) - set(CALLS) - {
            "get_project", "get_task", "get_task_comments", "get_task_history",
            "get_task_seen", "get_project_chat", "get_user_workload", "read_chat",
            "search_chat", "switch_workspace"})
        if untested:
            print("read tools without a smoke call:", ", ".join(untested))
    print("FAILED" if failed else "ALL READ TOOLS OK", f"({failed} failures)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main("--full" in sys.argv)))
