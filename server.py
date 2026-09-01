#!/usr/bin/env python3
"""Mizito MCP server — projects, tasks, and chat for office.mizito.ir.

Reverse-engineered from the SPA's own API (app.mizito.ir/api). Auth is a single
`x-token` header minted by POST /capi/session/create.

All endpoints are POST with a JSON body; an empty body is `{}`.
"""
from __future__ import annotations

import os
import sys
from typing import Any

import httpx
from fastmcp import FastMCP

BASE = os.environ.get("MIZITO_BASE", "https://app.mizito.ir")
TOKEN = os.environ.get("MIZITO_TOKEN", "").strip()
WORKSPACE = os.environ.get("MIZITO_WORKSPACE_ID", "").strip()

if not TOKEN:
    print("MIZITO_TOKEN is not set (see .env)", file=sys.stderr)

mcp = FastMCP("mizito")

_client: httpx.Client | None = None


def client() -> httpx.Client:
    global _client
    if _client is None:
        headers = {
            "x-token": TOKEN,
            "content-type": "application/json",
            "origin": "https://office.mizito.ir",
            "referer": "https://office.mizito.ir/",
        }
        if WORKSPACE:
            headers["workspace"] = WORKSPACE
        _client = httpx.Client(base_url=BASE, headers=headers, timeout=30.0)
    return _client


def api(path: str, body: dict[str, Any] | None = None) -> Any:
    """POST to a Mizito API path and return parsed JSON."""
    r = client().post(f"/api/{path.lstrip('/')}", json=body or {})
    if r.status_code == 405:
        raise ValueError(f"Endpoint /api/{path} does not exist (405).")
    if r.status_code == 401 or r.status_code == 403:
        raise ValueError("Mizito token rejected — it likely expired. Re-login "
                         "and refresh MIZITO_TOKEN in .env.")
    r.raise_for_status()
    try:
        return r.json()
    except Exception:
        return {"raw": r.text[:2000]}


def _trim_project(p: dict) -> dict:
    """Keep the fields an agent actually reasons about."""
    return {
        "id": p.get("_id"),
        "title": p.get("title"),
        "color": p.get("color"),
        "archived": p.get("archived", False),
        "is_advanced": p.get("is_advanced"),
        "owner": p.get("owner"),
        "dialog_id": p.get("dialog"),
        "boards": [
            {"id": b.get("_id"), "title": b.get("title")}
            for b in (p.get("kanban_boards") or [])
        ],
        "member_count": len(p.get("members_admin") or []),
    }


# ---------------------------------------------------------------- workspace


@mcp.tool()
def whoami() -> dict:
    """Get the current user and workspace: user id, workspace id, plan, phone.

    Use this first to learn your own user id, which other tools reference in
    fields like `owner`, `assignee`, and chat `from`.
    """
    d = api("workspace/userId", {"regId": None})
    name = api("workspace/name")
    return {
        "user_id": d.get("uid"),
        "workspace_id": d.get("wid"),
        "workspace_name": name if isinstance(name, str) else None,
        "phone": d.get("phone"),
        "is_guest": d.get("is_guest"),
        "plan_remain_days": d.get("remain_days"),
    }


@mcp.tool()
def list_workspace_users() -> list[dict]:
    """List every member of the current workspace with their id and name.

    Use to resolve a user id (from a task assignee or chat message) into a
    human name.
    """
    d = api("workspace/getUsers")
    users = d.get("users", d) if isinstance(d, dict) else d
    out = []
    for u in users or []:
        if not isinstance(u, dict):
            continue
        out.append({
            "id": u.get("_id"),
            "name": (u.get("name") or
                     f"{u.get('first_name','')} {u.get('last_name','')}".strip()),
            "phone": u.get("phone"),
            "role": u.get("role"),
        })
    return out


# ----------------------------------------------------------------- projects


@mcp.tool()
def list_projects(include_archived: bool = False) -> list[dict]:
    """List projects in the workspace (id, title, kanban boards, chat dialog id).

    By default returns only OPEN (non-archived) projects. Set
    include_archived=True to see finished ones too. The returned `dialog_id`
    is the project's group chat — pass it to read_chat.
    """
    d = api("projects/getList")
    projects = [_trim_project(p) for p in (d.get("projects") or [])]
    if not include_archived:
        projects = [p for p in projects if not p["archived"]]
    return projects


@mcp.tool()
def get_projects_summary(with_details: bool = True) -> list[dict]:
    """Get per-project task statistics: totals, completed, overdue, remaining.

    This is the fastest way to answer "how is project X doing" or "which
    projects have overdue work" without fetching individual tasks.
    """
    d = api("projects/allSummary", {"with_details": with_details})
    out = []
    for s in (d.get("summaries") or []):
        out.append({
            "project_id": s.get("project"),
            "title": s.get("project_title") or s.get("name"),
            "archived": s.get("is_archived"),
            "dialog_id": s.get("dialog"),
            "total_tasks": s.get("total_tasks"),
            "my_completed": s.get("me_completed"),
            "my_remaining": s.get("me_remain_count"),
            "my_overdue": s.get("me_overdue"),
            "my_today": s.get("me_today"),
            "others_completed": s.get("others_completed"),
            "others_overdue": s.get("others_overdue"),
            "last_completed": s.get("last_completed"),
        })
    return out


# -------------------------------------------------------------------- tasks


@mcp.tool()
def list_my_tasks(inbox: bool = True, limit: int = 50) -> list[dict]:
    """List the current user's upcoming/assigned tasks across all projects.

    Returns tasks with title, notes, project, deadline, and completion state.
    Use this for "what am I working on" / "what's due".
    """
    d = api("tasks/upcoming",
            {"inbox": inbox, "from_dashboard": True, "from": None,
             "filter": None})
    items = d if isinstance(d, list) else (d.get("tasks") or [])
    out = []
    for t in items[:limit]:
        if not isinstance(t, dict):
            continue
        notes = t.get("notes") or ""
        out.append({
            "id": t.get("_id"),
            "title": t.get("title"),
            "notes": (notes[:500] + "...") if len(notes) > 500 else notes,
            "project_id": t.get("project_entity") or t.get("project"),
            "board_id": t.get("board"),
            "owner": t.get("owner"),
            "assignee": t.get("assignee"),
            "completed": t.get("completed"),
            "deadline": t.get("deadline") or t.get("date"),
            "created": t.get("create_date"),
        })
    return out


@mcp.tool()
def get_task_counts() -> dict:
    """Get task badge counts for the current user: due today and total open."""
    return api("tasks/badge")


@mcp.tool()
def get_dashboard_summary() -> list[dict]:
    """Get a cross-workspace summary: unread chat/inbox and task counts.

    Each entry is one workspace the user belongs to, with today/overdue/open
    task counts. Good for a daily standup overview.
    """
    d = api("dashboard/getAllSummary")
    return d if isinstance(d, list) else [d]


# --------------------------------------------------------------------- chat


@mcp.tool()
def list_chats(only_unread: bool = False, limit: int = 60) -> list[dict]:
    """List chat conversations: direct messages and project group chats.

    Each entry has an `id` (dialog id) to pass to read_chat, a title, unread
    count, and last message time. Direct messages are titled with the other
    person's name; project group chats carry `project_id`.
    """
    d = api("chat/getDialogs")
    # resolve peer user ids -> names so DMs are not anonymous
    names: dict[str, str] = {}
    try:
        for u in list_workspace_users():
            if u.get("id"):
                names[u["id"]] = u.get("name") or ""
    except Exception:
        pass

    out = []
    for c in (d.get("dialogs") or []):
        peer = c.get("peer_user")
        title = c.get("title")
        if not title and peer:
            title = names.get(peer) or f"DM {peer[:8]}"
        item = {
            "id": c.get("_id"),
            "title": title,
            "is_group": c.get("is_group", False),
            "is_project_chat": c.get("is_project_group", False),
            "project_id": c.get("project_entity"),
            "peer_user": peer,
            "unread": c.get("unread_count", 0),
            "message_count": c.get("messages_count"),
            "last_message_date": c.get("last_message_date"),
            "member_count": len(c.get("members") or []) or None,
        }
        if only_unread and not item["unread"]:
            continue
        out.append(item)
    out.sort(key=lambda x: (x.get("last_message_date") or ""), reverse=True)
    return out[:limit]


@mcp.tool()
def read_chat(dialog_id: str, limit: int = 30) -> list[dict]:
    """Read recent messages from one chat conversation.

    `dialog_id` comes from list_chats (or `dialog_id` on a project). Messages
    include sender id, date, text, and a note when the message is a task card
    rather than plain text.
    """
    d = api("chat/getHistory", {"dialog": dialog_id, "limit": limit})
    msgs = d if isinstance(d, list) else (d.get("messages") or [])
    names: dict[str, str] = {}
    try:
        for u in list_workspace_users():
            if u.get("id"):
                names[u["id"]] = u.get("name") or ""
    except Exception:
        pass
    out = []
    for m in msgs:
        if not isinstance(m, dict):
            continue
        media = m.get("media") or {}
        kind = media.get("_")
        sender = m.get("from")
        entry = {
            "id": m.get("_id"),
            "from": sender,
            "from_name": names.get(sender) if sender else None,
            "date": m.get("date"),
            "text": m.get("message") or m.get("text") or "",
        }
        if kind == "messageMediaTask":
            task = media.get("task") or {}
            entry["type"] = "task_card"
            entry["task"] = {"id": task.get("_id"), "title": task.get("title")}
        elif kind:
            entry["type"] = kind
        out.append(entry)
    return out


@mcp.tool()
def get_project_chat(project_id: str, limit: int = 30) -> list[dict]:
    """Read the group chat attached to a project, by project id.

    Convenience wrapper: looks up the project's dialog, then reads it.
    """
    for p in api("projects/getList").get("projects") or []:
        if p.get("_id") == project_id:
            dlg = p.get("dialog")
            if not dlg:
                raise ValueError(f"Project {project_id} has no chat dialog.")
            return read_chat(dlg, limit)
    raise ValueError(f"No project with id {project_id}.")


@mcp.tool()
def send_message(text: str, dialog_id: str | None = None,
                 to: str | None = None) -> dict:
    """Send a text message to a Mizito chat (DM or project group).

    Give either `dialog_id` (from list_chats) or `to` — a person's name or a
    project/group title, matched case-insensitively against list_chats titles.
    Newlines in `text` are preserved.

    Returns the resolved target plus the message as it came back from the
    server, so the send is verified rather than assumed. Empty `text` is
    rejected (the API silently accepts it and posts nothing useful).
    """
    text = (text or "").strip()
    if not text:
        raise ValueError("text is empty — nothing to send.")

    dialogs = list_chats(limit=200)
    if not dialog_id:
        if not to:
            raise ValueError("Pass dialog_id or to=<name/title>.")
        needle = to.strip().casefold()
        hits = [d for d in dialogs
                if needle in (d.get("title") or "").casefold()]
        if not hits:
            raise ValueError(f"No chat matching {to!r}. Use list_chats first.")
        if len(hits) > 1:
            exact = [d for d in hits
                     if (d.get("title") or "").casefold() == needle]
            if len(exact) != 1:
                titles = ", ".join(repr(d.get("title")) for d in hits[:8])
                raise ValueError(f"{to!r} is ambiguous: {titles}. "
                                 "Pass dialog_id instead.")
            hits = exact
        dialog_id = hits[0]["id"]

    assert dialog_id
    target = next((d for d in dialogs if d.get("id") == dialog_id), None)

    api("chat/send", {"dialog": dialog_id, "message": text})

    sent = None
    # A chatbot peer can post several replies within the same second, so the
    # echo of our own message may already be pushed down the history.
    for m in read_chat(dialog_id, limit=15):
        if (m.get("text") or "").strip() == text:
            sent = m
            break
    if sent is None:
        raise ValueError("Message did not appear in the chat history — "
                         "treat the send as failed.")
    return {
        "dialog_id": dialog_id,
        "title": (target or {}).get("title"),
        "sent": sent,
    }


if __name__ == "__main__":
    mcp.run()
