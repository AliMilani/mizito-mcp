"""Task reads: list/filter/search, full detail, comments, history, workload."""
from __future__ import annotations

from collections import Counter, defaultdict

from .. import shape
from ..client import MizitoError
from ..tasks_api import (apply_filters, collect, due_at, is_due_today, is_overdue,
                         sort_tasks)
from ..util import fa_datetime, now_utc
from . import Ctx

MAX_LIMIT = 200


def register(tool, ctx: Ctx) -> None:
    c, d = ctx.client, ctx.dir

    def _page(rows: list[dict], offset: int, limit: int, notes_chars: int) -> dict:
        limit = max(1, min(limit, MAX_LIMIT))
        offset = max(0, offset)
        chunk = rows[offset:offset + limit]
        return {
            "total": len(rows),
            "offset": offset,
            "returned": len(chunk),
            "has_more": offset + len(chunk) < len(rows),
            "next_offset": offset + len(chunk) if offset + len(chunk) < len(rows) else None,
            "tasks": [shape.task_row(t, d, notes_chars) for t in chunk],
        }

    def _scopes(scope: str | None, project: str | None, label_id: str | None) -> list[dict]:
        if project:
            if project.strip().lower() == "all":
                return [{"project_id": pid} for pid, p in d.projects().items()
                        if not p.get("archived") and not p.get("deleted")]
            return [{"project_id": d.resolve_project(project)}]
        if scope in (None, "", "mine", "inbox"):
            return [{"label_id": label_id}] if label_id and scope is None else [{"inbox": True}]
        if scope == "outbox":
            return [{"outbox": True}]
        if scope == "everything":
            return d.search_scopes()
        raise ValueError("scope must be one of: mine, outbox, everything "
                         "(or pass project=...)")

    def _task_obj(task_id: str) -> dict:
        t = c.call("tasks/get", {"token": d.task_token(task_id)})
        if not isinstance(t, dict) or not t.get("_id"):
            raise MizitoError(f"Task {task_id} could not be loaded.")
        if t.get("no_access_deleted"):
            raise MizitoError(f"Task {task_id} was deleted.")
        d.remember_tasks([t])
        return t

    ctx.get_task_obj = _task_obj  # shared with task_writes

    @tool()
    def list_tasks(project: str | None = None, scope: str | None = None,
                   board: str | None = None, assignee: str | None = None,
                   unassigned: bool = False, owner: str | None = None,
                   label: str | None = None, status: str = "open",
                   overdue_only: bool = False, query: str | None = None,
                   sort: str | None = None, offset: int = 0, limit: int = 50,
                   notes_chars: int = 160) -> dict:
        """List tasks with filters. The main task query tool.

        Where to look (pick one):
        - project="<id or title>"  every task of that project; project="all"
          = every open project
        - scope="mine" (default)   tasks assigned to me + my personal tasks
        - scope="outbox"           tasks I created for other people
        - scope="everything"       inbox + outbox + every open project

        Filters (combine freely, applied exactly):
        board (title/id, needs project), assignee (name/id/"me"), unassigned,
        owner (creator), label (title/id), status "open"|"done"|"all",
        overdue_only, query (words that must all appear in title/notes/
        checklist; Persian/Arabic letter variants match).

        sort: "deadline" (default; overdue first), "board" (kanban order,
        default for a project), "modified", "created".
        Paginated: returns total, has_more and next_offset.
        """
        pid = d.resolve_project(project) if project and project.lower() != "all" else None
        lid = d.resolve_label(label) if label else None
        rows = collect(c, d, _scopes(scope, project, lid), status)
        rows = apply_filters(
            rows,
            assignee=d.resolve_user(assignee) if assignee else None,
            unassigned=unassigned,
            owner=d.resolve_user(owner) if owner else None,
            board=d.resolve_board(board, pid) if board else None,
            label=lid, overdue_only=overdue_only, query=query)
        rows = sort_tasks(rows, sort or ("board" if pid else "deadline"), d)
        return _page(rows, offset, limit, notes_chars)

    @tool()
    def list_my_tasks(status: str = "open", limit: int = 50, offset: int = 0) -> dict:
        """My tasks (assigned to me or personal), overdue first. Shortcut for
        list_tasks(scope="mine")."""
        rows = sort_tasks(collect(c, d, [{"inbox": True}], status), "deadline", d)
        return _page(rows, offset, limit, 160)

    def _server_search(query: str, done: bool, max_pages: int = 20) -> list[dict]:
        """The SPA search page: tasks/upcoming {search:true, search_str}.
        Covers archived projects too. 25 per page via `from`."""
        flt = {"done_status": True, "completed": True} if done else None
        out: list[dict] = []
        for page in range(max_pages):
            rows = c.call("tasks/upcoming", {"search": True, "search_str": query,
                                             "from": page * 25, "filter": flt})
            rows = rows if isinstance(rows, list) else []
            d.remember_tasks(rows)
            out.extend(rows)
            if len(rows) < 25:
                break
        return out

    @tool()
    def search_tasks(query: str, status: str = "open", project: str | None = None,
                     limit: int = 30, offset: int = 0) -> dict:
        """Find tasks by text, the way Mizito's own search page does (server
        side, includes archived projects), merged with an exact local match
        on title/notes/checklist of visible projects. status "open" | "done" |
        "all". Optional project narrows the result. Returns ids for get_task."""
        if not query or not query.strip():
            raise ValueError("query is empty")
        if status not in ("open", "done", "all"):
            raise ValueError("status must be 'open', 'done' or 'all'")
        rows: dict[str, dict] = {}
        for done in ((False,) if status == "open" else (True,) if status == "done"
                     else (False, True)):
            for t in _server_search(query.strip(), done):
                rows.setdefault(t["_id"], t)
        pid = d.resolve_project(project) if project else None
        if status == "open":  # cheap: open tasks of visible projects
            scopes = [{"project_id": pid}] if pid else d.search_scopes()
            for t in apply_filters(collect(c, d, scopes, "open"), query=query):
                rows.setdefault(t["_id"], t)
        found = [t for t in rows.values() if not pid or t.get("project") == pid]
        return _page(sort_tasks(found, "modified", d), offset, limit, 200)

    @tool()
    def get_task(task_id: str, include_comments: bool = True,
                 include_history: bool = False) -> dict:
        """Everything about one task: full notes, assignees, deadline,
        checklist items (with ids), attachments, labels, completion, and its
        comments (+ change history if include_history=True)."""
        t = _task_obj(task_id)
        out = shape.task_full(t, d)
        token = d.task_token(task_id)
        if include_comments:
            rows = c.call("tasks/getComments", {"token": token}) or []
            out["comment_list"] = [shape.comment(x, d) for x in rows
                                   if isinstance(x, dict) and not x.get("deleted")]
        if include_history:
            rows = c.call("tasks/history", {"token": token, "tid": task_id}) or []
            out["history"] = [shape.history_entry(h, d) for h in rows if isinstance(h, dict)]
        return out

    @tool()
    def get_task_comments(task_id: str, include_deleted: bool = False) -> list[dict]:
        """Comments on a task, newest first, with author names and mentions."""
        rows = c.call("tasks/getComments", {"token": d.task_token(task_id)}) or []
        return [shape.comment(x, d) for x in rows
                if isinstance(x, dict) and (include_deleted or not x.get("deleted"))]

    @tool()
    def get_task_history(task_id: str) -> list[dict]:
        """Change log of a task: who changed what (title, notes, assignees,
        board, deadline, completion...) and when, oldest first."""
        rows = c.call("tasks/history", {"token": d.task_token(task_id),
                                        "tid": task_id}) or []
        return [shape.history_entry(h, d) for h in rows if isinstance(h, dict)]

    @tool()
    def get_task_seen(task_id: str) -> dict:
        """Who has opened a task, and when (first and last view per person)."""
        s = c.call("tasks/getSeenDetails", {"token": d.task_token(task_id)}) or {}
        def rows(key):
            return [{"user": d.user_name(r.get("user")), "date_fa": fa_datetime(r.get("date"))}
                    for r in s.get(key) or []]
        created = s.get("created") or {}
        return {"created_by": d.user_name(created.get("owner")),
                "created_fa": fa_datetime(created.get("created_at")),
                "first_seen": rows("first_user_seen"), "last_seen": rows("last_user_seen")}

    @tool()
    def get_user_workload(user: str, include_done: bool = False) -> dict:
        """What one person (name/id/"me") has on their plate across all open
        projects: open task count, overdue, per project and per board, plus
        the task list (overdue first). Done tasks only if include_done."""
        uid = d.resolve_user(user)
        scopes = [{"project_id": pid} for pid, p in d.projects().items()
                  if not p.get("archived") and not p.get("deleted")]
        if uid == d.me():
            scopes.append({"inbox": True})
        rows = apply_filters(collect(c, d, scopes, "all" if include_done else "open"),
                             assignee=uid)
        rows = sort_tasks(rows, "deadline", d)
        now = now_utc()
        by_project: dict[str, Counter] = defaultdict(Counter)
        for t in rows:
            key = d.project_title(t.get("project")) or "(personal)"
            by_project[key]["done" if t.get("completed") else "open"] += 1
            if is_overdue(t, now):
                by_project[key]["overdue"] += 1
        open_rows = [t for t in rows if not t.get("completed")]
        return {
            "user": d.user_name(uid), "user_id": uid,
            "open": len(open_rows),
            "overdue": sum(1 for t in open_rows if is_overdue(t, now)),
            "with_date": sum(1 for t in open_rows if due_at(t)),
            "by_project": {k: dict(v) for k, v in by_project.items()},
            "tasks": [shape.task_row(t, d, 0) for t in rows[:100]],
            "truncated": len(rows) > 100,
        }

    @tool()
    def daily_brief() -> dict:
        """One-call standup: my overdue / due-today / no-deadline task counts
        with the urgent tasks listed, unread chats, and per-project open and
        overdue counts. Good first call for "what's going on?"."""
        mine = collect(c, d, [{"inbox": True}], "open")
        now = now_utc()
        today = fa_datetime(now.isoformat(), with_time=False)
        overdue = [t for t in mine if is_overdue(t, now)]
        due_today = [t for t in mine if is_due_today(t, now) and not is_overdue(t, now)]
        d.invalidate("dialogs")
        dialogs = (d.dialogs().get("dialogs") or [])
        unread = [shape.dialog(x, d) for x in dialogs if x.get("unread_count")]
        sums = (c.call("projects/allSummary", {"with_details": True}) or {}).get("summaries") or []
        projects = d.projects()
        return {
            "today_fa": today,
            "my_open": len(mine),
            "my_overdue": [shape.task_row(t, d, 0) for t in sort_tasks(overdue, "deadline", d)],
            "my_due_today": [shape.task_row(t, d, 0) for t in due_today],
            "my_without_date": sum(1 for t in mine if not due_at(t)),
            "unread_chats": unread,
            "projects": [{"title": s.get("name") or s.get("project_title"),
                          **{k: v for k, v in shape.summary_counts(s).items()
                             if k in ("open", "overdue", "mine_open", "due_today")}}
                         for s in sums
                         if not (projects.get(s.get("project")) or {}).get("archived")],
        }
