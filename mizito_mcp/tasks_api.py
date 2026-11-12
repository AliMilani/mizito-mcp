"""Task listing shared by list_tasks / search_tasks / workload tools.

How Mizito lists tasks (from the SPA, verified live 2026-11-12):

- `tasks/upcoming` with one scope key and `from` = offset, page size 25:
    {"inbox": true}            tasks assigned to me (+ my personal tasks)
    {"outbox": true}           tasks I created for others
    {"project_id": "<id>"}     every task of a project
    {"label_id": "<id>"}       tasks carrying a label
  plus "sort_type": "default" and "filter": <filter object or null>.
- Open and done tasks are disjoint: the filter's `done_status` picks one set.
- `tasks/getAll` is the SPA's first-page call (no `from`); it returns the
  same rows, so this module only uses `tasks/upcoming`.

Server-side we only choose scope + done/open. Every other filter (assignee,
board, label, overdue, text) is applied locally so behaviour is
deterministic and does not depend on undocumented filter semantics.
"""
from __future__ import annotations

from typing import Any, Iterable

from .client import MizitoClient
from .directory import PAGE, Directory
from .util import TEHRAN, norm, now_utc, parse_iso

MAX_PAGES = 80  # 2000 tasks per scope and status; a hard stop, not a target


def base_filter() -> dict[str, Any]:
    """The SPA's default filter object (AppTasksController `p()`)."""
    return {"owner": None, "assignee": None, "with_assignee": False,
            "assignee_not_me": False, "check_overdue": False, "overdue": False,
            "check_with_time": False, "with_time": False, "with_progress": False,
            "labels": [], "board": None, "done_status": False,
            "title_active": False, "title": ""}


def fetch_scope(c: MizitoClient, d: Directory, scope: dict, done: bool) -> list[dict]:
    flt = base_filter()
    flt["done_status"] = done
    rows: list[dict] = []
    seen: set[str] = set()
    for page in range(MAX_PAGES):
        batch = c.call("tasks/upcoming", dict(scope, sort_type="default",
                                              filter=flt, **{"from": page * PAGE}))
        batch = batch if isinstance(batch, list) else []
        d.remember_tasks(batch)
        for t in batch:
            if isinstance(t, dict) and t.get("_id") not in seen:
                seen.add(t["_id"])
                rows.append(t)
        if len(batch) < PAGE:
            break
    return rows


def collect(c: MizitoClient, d: Directory, scopes: Iterable[dict],
            status: str) -> list[dict]:
    if status not in ("open", "done", "all"):
        raise ValueError("status must be 'open', 'done' or 'all'")
    out: list[dict] = []
    seen: set[str] = set()
    for scope in scopes:
        for done in ((False,) if status == "open" else (True,) if status == "done"
                     else (False, True)):
            for t in fetch_scope(c, d, scope, done):
                if t["_id"] not in seen:
                    seen.add(t["_id"])
                    out.append(t)
    return out


def scheduled_at(t: dict):
    """When the task is scheduled: Mizito's `sort_date` (the reminder,
    "زمان یادآوری", set by tasks/snooze; falls back to alarm_at). This, not
    `deadline`, drives the SPA's overdue / today / upcoming groups."""
    return parse_iso(t.get("sort_date") or t.get("alarm_at"))


def due_at(t: dict):
    """Deadline when the project uses deadlines ("مهلت انجام"), else the
    scheduled date. None = no date at all."""
    if t.get("has_deadline"):
        dl = parse_iso(t.get("deadline"))
        if dl:
            return dl
    return scheduled_at(t)


def is_overdue(t: dict, now=None) -> bool:
    """SPA rule (services.getRelativeTimeForTask): overdue when the scheduled
    DAY is before today (local time). A passed deadline also counts."""
    if t.get("completed"):
        return False
    now = now or now_utc()
    sched = scheduled_at(t)
    if sched and sched.astimezone(TEHRAN).date() < now.astimezone(TEHRAN).date():
        return True
    dl = parse_iso(t.get("deadline")) if t.get("has_deadline") else None
    return bool(dl and dl < now)


def is_due_today(t: dict, now=None) -> bool:
    if t.get("completed"):
        return False
    today = (now or now_utc()).astimezone(TEHRAN).date()
    return any(x and x.astimezone(TEHRAN).date() == today for x in (
        scheduled_at(t), parse_iso(t.get("deadline")) if t.get("has_deadline") else None))


def assignees(t: dict) -> list[str]:
    a = t.get("assignee")
    if isinstance(a, list):
        return [x for x in a if x]
    return [a] if a else []


def apply_filters(tasks: list[dict], *, assignee: str | None = None,
                  unassigned: bool = False, owner: str | None = None,
                  board: str | None = None, label: str | None = None,
                  overdue_only: bool = False, query: str | None = None) -> list[dict]:
    now = now_utc()
    nq = norm(query) if query else ""
    out = []
    for t in tasks:
        if assignee and assignee not in assignees(t):
            continue
        if unassigned and assignees(t):
            continue
        if owner and t.get("owner") != owner:
            continue
        if board and t.get("kanban_board") != board:
            continue
        if label and label not in (t.get("labels") or []):
            continue
        if overdue_only and not is_overdue(t, now):
            continue
        if nq:
            hay = norm(t.get("title")) + " " + norm(t.get("notes")) + " " + " ".join(
                norm(c.get("title")) for c in t.get("checklist") or [])
            if not all(tok in hay for tok in nq.split()):
                continue
        out.append(t)
    return out


def sort_tasks(tasks: list[dict], mode: str, d: Directory) -> list[dict]:
    if mode == "board":
        boards = d.boards()
        return sorted(tasks, key=lambda t: (
            d.project_title(t.get("project")) or "~",
            (boards.get(t.get("kanban_board")) or {}).get("index", 999),
            t.get("kanban_weight") or 0))
    if mode == "modified":
        return sorted(tasks, key=lambda t: t.get("modified_at") or "", reverse=True)
    if mode == "created":
        return sorted(tasks, key=lambda t: t.get("created_at") or "", reverse=True)
    if mode == "deadline":
        far = "9999"
        def key(t):
            due = due_at(t)
            return (bool(t.get("completed")), due.isoformat() if due else far,
                    t.get("modified_at") or "")
        return sorted(tasks, key=key)
    raise ValueError("sort must be one of: deadline, board, modified, created")
