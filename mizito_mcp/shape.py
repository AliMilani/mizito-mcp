"""Raw Mizito objects -> compact, agent-friendly dicts.

Conventions every tool follows:
- ids are kept (`*_id`) next to resolved human names so the agent can chain
  calls without another lookup;
- dates stay as Mizito's UTC ISO strings, plus a `*_fa` twin in Tehran local
  time on the Jalali calendar ("1405/08/21 14:30") for Persian replies;
- empty/false noise is dropped from list rows to save tokens;
- secrets never appear (util.scrub is applied again at the tool boundary).
"""
from __future__ import annotations

from typing import Any

from .directory import ROLE_NAMES, Directory
from .tasks_api import assignees, is_overdue
from .util import fa_datetime, truncate


def _compact(d: dict) -> dict:
    return {k: v for k, v in d.items() if v not in (None, "", [], {}, False)}


# ---------------------------------------------------------------- users

def user(u: dict, d: Directory, include_contact: bool = False) -> dict:
    status = u.get("status") or {}
    work = u.get("work_status") or {}
    out = {
        "id": u.get("_id"),
        "name": d.user_name(u.get("_id")),
        "username": u.get("username"),
        "role": ROLE_NAMES.get(u.get("role"), u.get("role")),
        "online": status.get("_") == "userStatusOnline",
        "last_seen": status.get("was_online"),
        "last_seen_fa": fa_datetime(status.get("was_online")),
        "working_on": work.get("last_working_on_title") or None,
        "working_on_since_fa": fa_datetime(work.get("last_working_on_date")),
        "deleted": bool(u.get("deleted")),
        "invited_pending": bool(u.get("invited")),
    }
    if include_contact:
        out["phone"] = u.get("phone")
        out["email"] = u.get("email")
    return _compact(out) | {"id": u.get("_id"), "online": out["online"]}


# ---------------------------------------------------------------- projects

def project(p: dict, d: Directory) -> dict:
    return _compact({
        "id": p.get("_id"),
        "title": p.get("title"),
        "archived": bool(p.get("archived")),
        "color": p.get("color"),
        "owner": d.user_name(p.get("owner")),
        "owner_id": p.get("owner"),
        "admins": d.user_names(p.get("members_admin")),
        "advanced": bool(p.get("is_advanced")),
        "chat_dialog_id": p.get("dialog"),
        "labels": [d.label_title(l, "project") for l in p.get("labels") or []],
        "boards": [{"id": b.get("_id"), "title": b.get("title")}
                   for b in p.get("kanban_boards") or []],
    })


def summary_counts(s: dict) -> dict:
    """Counts block shared by allSummary rows, chatSummary and its boards."""
    done = (s.get("me_completed") or 0) + (s.get("others_completed") or 0)
    total = s.get("total_tasks") or 0
    return _compact({
        "total": total,
        "done": done,
        "open": max(total - done, 0),
        "overdue": (s.get("me_overdue") or 0) + (s.get("others_overdue") or 0),
        "due_today": (s.get("me_today") or 0) + (s.get("others_today") or 0),
        "mine_open": s.get("me_remain_count"),
        "mine_overdue": s.get("me_overdue"),
        "mine_done": s.get("me_completed"),
        "last_completed": s.get("last_completed") or None,
        "last_completed_fa": fa_datetime(s.get("last_completed")),
    }) | {"total": total, "done": done, "open": max(total - done, 0)}


# ---------------------------------------------------------------- tasks

def checklist_progress(t: dict) -> str | None:
    items = t.get("checklist") or []
    if not items:
        return None
    return f"{sum(1 for i in items if i.get('checked'))}/{len(items)}"


def task_row(t: dict, d: Directory, notes_chars: int = 160) -> dict:
    """One line of a task list."""
    a = assignees(t)
    return _compact({
        "id": t.get("_id"),
        "title": t.get("title"),
        "project": d.project_title(t.get("project")),
        "project_id": t.get("project"),
        "board": d.board_title(t.get("kanban_board")),
        "board_id": t.get("kanban_board"),
        "assignees": d.user_names(a),
        "owner": d.user_name(t.get("owner")),
        "completed": bool(t.get("completed")),
        "progress": t.get("progress") or None,
        "deadline": t.get("deadline") if t.get("has_deadline") else None,
        "deadline_fa": fa_datetime(t.get("deadline")) if t.get("has_deadline") else None,
        "reminder": t.get("sort_date") or t.get("alarm_at"),
        "reminder_fa": fa_datetime(t.get("sort_date") or t.get("alarm_at")),
        "overdue": is_overdue(t),
        "labels": [d.label_title(l) for l in t.get("labels") or []],
        "checklist": checklist_progress(t),
        "comments": bool(t.get("has_comments")),
        "attachments": len(t.get("attachments") or []) or None,
        "notes": truncate(t.get("notes"), notes_chars) if notes_chars else None,
        "modified_fa": fa_datetime(t.get("modified_at")),
    })


def attachment(a: dict) -> dict:
    m = a.get("media") or a
    doc = m.get("document") or m.get("photo") or m
    return _compact({
        "id": doc.get("_id") or m.get("_id") or a.get("_id"),
        "name": doc.get("file_name") or doc.get("name") or m.get("caption"),
        "mime": doc.get("mime_type") or doc.get("type"),
        "size": doc.get("size"),
        "kind": m.get("_"),
    })


def task_full(t: dict, d: Directory) -> dict:
    out = task_row(t, d, notes_chars=0)
    out.update(_compact({
        "notes": t.get("notes") or None,
        "assignee_ids": assignees(t),
        "owner_id": t.get("owner"),
        "responsible": d.user_name(t.get("responsible")),
        "deadline_start": t.get("deadline_start") if t.get("has_deadline_start") else None,
        "deadline_start_fa": fa_datetime(t.get("deadline_start")) if t.get("has_deadline_start") else None,
        "created": t.get("created_at"),
        "created_fa": fa_datetime(t.get("created_at")),
        "modified": t.get("modified_at"),
        "completed_at": t.get("completed_at"),
        "completed_at_fa": fa_datetime(t.get("completed_at")),
        "completed_by": d.user_names(t.get("completed_by")),
        "repeat": (t.get("alarm_options") or {}).get("repeat_type")
                  if (t.get("alarm_options") or {}).get("repeat_type") not in (None, "none") else None,
        "deadline_feature": bool(t.get("deadline_used")) or None,
        "label_ids": t.get("labels") or None,
        "checklist_items": [_compact({
            "id": c.get("_id"), "title": c.get("title"),
            "checked": bool(c.get("checked")),
            "checked_by": d.user_name(c.get("checked_by")) if c.get("checked") else None,
            "checked_at_fa": fa_datetime(c.get("checked_at")) if c.get("checked") else None,
        }) | {"checked": bool(c.get("checked"))} for c in t.get("checklist") or []],
        "attachment_files": [attachment(a) for a in t.get("attachments") or []],
        "custom_fields": [_compact({"title": p.get("title"), "value": p.get("value")})
                          for p in t.get("custom_params") or [] if isinstance(p, dict)],
        "chat_dialog_id": t.get("dialog"),
        "chat_message_id": t.get("dialog_message"),
        "form_request": bool(t.get("is_form_request")),
    }))
    return out


def comment(c: dict, d: Directory) -> dict:
    return _compact({
        "id": c.get("_id"),
        "author": d.user_name(c.get("comment_owner")),
        "author_id": c.get("comment_owner"),
        "date": c.get("comment_at"),
        "date_fa": fa_datetime(c.get("comment_at")),
        "text": c.get("comment"),
        "mentions": d.user_names(c.get("mention")),
        "reply_to": c.get("replied_comment_id"),
        "edited": bool(c.get("edited")),
        "deleted": bool(c.get("deleted")),
        "attachments": [attachment(a) for a in c.get("attachments") or []],
    })


_HISTORY_SKIP = {"modified_at", "automation_board_revert", "kanban_weight"}


def _hist_value(field: str, v: Any, d: Directory) -> Any:
    if field in ("assignee", "completed_by") and isinstance(v, list):
        return d.user_names(v)
    if field in ("owner", "responsible") and isinstance(v, str):
        return d.user_name(v) or v
    if field == "kanban_board" and isinstance(v, str):
        return d.board_title(v) or v
    if field == "project" and isinstance(v, str):
        return d.project_title(v) or v
    if field == "labels" and isinstance(v, list):
        return [d.label_title(x) for x in v]
    if field in ("deadline", "alarm_at", "completed_at", "deadline_start"):
        return fa_datetime(v) or v
    if isinstance(v, str):
        return truncate(v, 300)
    return v


def history_entry(h: dict, d: Directory) -> dict:
    ch = h.get("changes") or {}
    frm, to = ch.get("from") or {}, ch.get("to") or {}
    changes = {}
    for field in sorted(set(frm) | set(to)):
        if field in _HISTORY_SKIP:
            continue
        if field == "created":
            changes["created"] = True
            continue
        changes[field] = {"from": _hist_value(field, frm.get(field), d),
                          "to": _hist_value(field, to.get(field), d)}
    return _compact({
        "user": d.user_name(h.get("user")),
        "date": h.get("date"),
        "date_fa": fa_datetime(h.get("date")),
        "changes": changes,
    })


# ---------------------------------------------------------------- chat

def dialog(c: dict, d: Directory) -> dict:
    return _compact({
        "id": c.get("_id"),
        "title": d.dialog_title(c),
        "kind": ("project" if c.get("is_project_group") else
                 "group" if c.get("is_group") else
                 "customer" if c.get("is_customer_entity") else "dm"),
        "project_id": c.get("project_entity"),
        "peer_user_id": c.get("peer_user"),
        "unread": c.get("unread_count") or 0,
        "messages": c.get("messages_count"),
        "last_message": c.get("last_message_date"),
        "last_message_fa": fa_datetime(c.get("last_message_date")),
        "members": len(c.get("members") or []) or None,
        "pinned_messages": len(c.get("pinned_messages") or []) or None,
    }) | {"unread": c.get("unread_count") or 0}


def message(m: dict, d: Directory) -> dict:
    media = m.get("media") or {}
    kind = media.get("_")
    out = {
        "id": m.get("_id"),
        "index": m.get("msg_index"),
        "from": d.user_name(m.get("from")),
        "from_id": m.get("from"),
        "date": m.get("date"),
        "date_fa": fa_datetime(m.get("date")),
        "text": m.get("message") or "",
        "reply_to": m.get("reply_to"),
        "mentions": d.user_names(m.get("mention")),
        "edited": bool(m.get("edited")),
        "deleted": bool(m.get("deleted")),
        "service": m.get("_") if m.get("_") not in (None, "message") else None,
    }
    if kind == "messageMediaTask":
        task = media.get("task") or {}
        out["type"] = "task_card"
        out["task"] = _compact({"id": task.get("_id"), "title": task.get("title"),
                                "completed": bool(task.get("completed"))})
    elif kind:
        out["type"] = kind
        att = attachment({"media": media})
        if len(att) > 1:
            out["attachment"] = att
    return _compact(out) | {"id": m.get("_id"), "text": out["text"]}
