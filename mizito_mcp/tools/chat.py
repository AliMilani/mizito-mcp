"""Chat reads: dialogs, history (paged), project chat, local search."""
from __future__ import annotations

from .. import shape
from ..util import norm
from . import Ctx

# chat/getHistory {dialog, offset, limit?}: newest first; offset counts back
# from the newest message. The SPA never sends `limit` (server default 15) but
# the server honours it; 200 verified live 2026-11-12.
HISTORY_MAX = 200


def register(tool, ctx: Ctx) -> None:
    c, d = ctx.client, ctx.dir

    def _history(dialog_id: str, limit: int, offset: int = 0,
                 extra: dict | None = None) -> list[dict]:
        """Newest-first messages. `offset` skips that many newest messages.
        `extra` = {"filter": "search", "filterSearch": s} or
        {"filter": "sender", "filterSender": uid} (server-side filters)."""
        out: list[dict] = []
        seen: set[str] = set()
        while len(out) < limit:
            want = min(HISTORY_MAX, limit - len(out))
            rows = c.call("chat/getHistory", {"dialog": dialog_id, "limit": want,
                                              "offset": offset + len(out),
                                              **(extra or {})})
            rows = rows if isinstance(rows, list) else (rows or {}).get("messages") or []
            fresh = [m for m in rows if isinstance(m, dict) and m.get("_id") not in seen]
            for m in fresh:
                seen.add(m["_id"])
            out.extend(fresh)
            if len(rows) < want or not fresh:
                break
        return out[:limit]

    ctx.chat_history = _history  # shared with chat_writes

    @tool()
    def list_chats(only_unread: bool = False, kind: str | None = None,
                   query: str | None = None, limit: int = 60) -> list[dict]:
        """Chats (DMs, groups, project group chats), most recent first: id,
        title (DMs are titled with the other person's name), kind, unread
        count, last message time. Filter by kind "dm"|"group"|"project" or by
        a title substring. Chat arguments elsewhere accept ids or titles."""
        d.invalidate("dialogs")
        raw = d.dialogs()
        rows = [shape.dialog(x, d) for x in (raw.get("dialogs") or [])]
        if only_unread:
            rows = [r for r in rows if r.get("unread")]
        if kind:
            rows = [r for r in rows if r.get("kind") == kind]
        if query:
            nq = norm(query)
            rows = [r for r in rows if nq in norm(r.get("title"))]
        rows.sort(key=lambda r: r.get("last_message") or "", reverse=True)
        return rows[:limit]

    @tool()
    def read_chat(chat: str, limit: int = 30, offset: int = 0,
                  oldest_first: bool = False, include_deleted: bool = False) -> dict:
        """Messages of one chat (id or title), newest first by default.

        Page back through history with offset (skip that many newest
        messages): offset=0 then offset=30, ... `has_more` says whether older
        messages exist. Messages carry sender names, reply_to ids, mentions,
        and task cards (type=task_card + task title). Deleted messages (which
        Mizito keeps as "." placeholders) are skipped unless include_deleted.
        """
        did = d.resolve_dialog(chat)
        limit = max(1, min(limit, 500))
        rows = _history(did, limit + 1, offset)
        has_more = len(rows) > limit
        page = rows[:limit]  # offsets count raw rows, deleted ones included
        msgs = [shape.message(m, d) for m in page
                if include_deleted or not m.get("deleted")]
        if oldest_first:
            msgs.reverse()
        dialog = next((x for x in d.dialogs().get("dialogs") or [] if x.get("_id") == did), {})
        return {"chat_id": did, "title": d.dialog_title(dialog) if dialog else None,
                "offset": offset, "returned": len(msgs), "has_more": has_more,
                "next_offset": offset + len(page) if has_more else None,
                "messages": msgs}

    @tool()
    def get_project_chat(project: str, limit: int = 30, offset: int = 0) -> dict:
        """The group chat of a project (id or title). Same output as read_chat."""
        pid = d.resolve_project(project)
        dlg = (d.projects().get(pid) or {}).get("dialog")
        if not dlg:
            raise ValueError(f"Project {pid} has no chat.")
        return read_chat(dlg, limit=limit, offset=offset)

    @tool()
    def search_chat(chat: str, query: str | None = None,
                    from_user: str | None = None, limit: int = 50,
                    offset: int = 0) -> dict:
        """Search inside one chat (id or title), server side, newest first.

        query: text to find (Mizito's own in-chat search).
        from_user: only messages from this person (name/id/"me").
        Give query, from_user, or both (both = server filters by text, then
        sender is checked locally). Paged with offset/next_offset.
        """
        did = d.resolve_dialog(chat)
        uid = d.resolve_user(from_user) if from_user else None
        if not (query and query.strip()) and not uid:
            raise ValueError("give query and/or from_user")
        extra = ({"filter": "search", "filterSearch": query.strip()} if query and query.strip()
                 else {"filter": "sender", "filterSender": uid})
        limit = max(1, min(limit, 200))
        rows = _history(did, limit + 1, offset, extra)
        has_more = len(rows) > limit
        rows = rows[:limit]
        hits = [m for m in rows if not m.get("deleted")
                and (not (uid and query) or m.get("from") == uid)]
        return {"chat_id": did, "offset": offset, "returned": len(hits),
                "has_more": has_more,
                "next_offset": offset + len(rows) if has_more else None,
                "messages": [shape.message(m, d) for m in hits]}

    @tool()
    def search_messages(query: str, offset: int = 0) -> dict:
        """Search all chats at once (Mizito's global message search). Returns
        up to 15 hits per page with the chat each came from; page with
        offset/next_offset."""
        if not query or not query.strip():
            raise ValueError("query is empty")
        rows = c.call("chat/search", {"mode": "chat", "offset": offset,
                                      "search_str": query.strip()}) or []
        rows = rows if isinstance(rows, list) else []
        by_id = {x.get("_id"): x for x in d.dialogs().get("dialogs") or []}
        out = []
        for m in rows:
            row = shape.message(m, d)
            row["chat_id"] = m.get("dialog")
            known = by_id.get(m.get("dialog"))
            full = m.get("chat_full") or {}
            # DMs come back titled "to_person"; resolve via the dialog list
            row["chat"] = (d.dialog_title(known) if known else
                           full.get("title") if full.get("title") != "to_person" else None)
            out.append(row)
        return {"offset": offset, "returned": len(out), "has_more": len(rows) >= 15,
                "next_offset": offset + len(rows) if len(rows) >= 15 else None,
                "messages": out}
