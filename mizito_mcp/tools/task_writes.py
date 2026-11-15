"""Task mutations. Every tool here:

1. resolves names -> ids and the task id -> its access token,
2. sends exactly the body the SPA sends (docs/API.md cites each call site),
3. reads the task back and checks the change landed,
4. returns {"ok": true, "verified": {...}, "task": <task row>} or raises.

Writes are never retried automatically (see client.py).
"""
from __future__ import annotations

from typing import Any, Callable

from .. import shape
from ..client import BadRequest, MizitoError
from ..tasks_api import assignees as assignees_of
from ..util import (TEHRAN, norm, parse_iso, parse_user_datetime, plain_text,
                    to_mizito_iso)
from . import Ctx


class WriteNotVerified(MizitoError):
    pass


def register(tool, ctx: Ctx) -> None:
    c, d = ctx.client, ctx.dir

    def get(task_id: str) -> dict:
        return ctx.get_task_obj(task_id)

    def token(task_id: str) -> str:
        return d.task_token(task_id)

    def verify(task_id: str, check: Callable[[dict], bool], what: str) -> dict:
        t = get(task_id)
        if not check(t):
            raise WriteNotVerified(
                f"Mizito accepted the request but the task does not show the change "
                f"({what}). Treat it as NOT done; inspect with get_task.")
        return t

    def result(t: dict, **verified: Any) -> dict:
        return {"ok": True, "verified": verified, "task": shape.task_row(t, d, 0)}

    ctx.task_write_helpers = {"get": get, "verify": verify, "result": result}

    def same_instant(a: Any, b: str | None, tolerance_s: int = 60) -> bool:
        da, db = parse_iso(a), parse_iso(b)
        return bool(da and db and abs((da - db).total_seconds()) <= tolerance_s)

    def _deadline_iso(value: str | None) -> str | None:
        return to_mizito_iso(parse_user_datetime(value)) if value else None

    def _require_deadline_feature(pid: str | None) -> None:
        """`deadline` ("مهلت انجام") only exists in projects with the advanced
        deadline feature. Elsewhere Mizito stores the value but never shows it
        (verified live 2026-11-12), so refuse instead of a silent no-op."""
        p = d.projects().get(pid) or {}
        if not p.get("advanced_has_deadline"):
            raise ValueError(
                f"Project {p.get('title') or pid!r} does not use deadlines (مهلت انجام). "
                "Use a reminder instead (set_task_reminder / create_task(reminder=...)): "
                "that is the date Mizito uses for today / overdue.")

    def _alarm_options(when: str) -> dict:
        """The SPA schedule dialog's minimal result (SPA_CALLSITES §1)."""
        dt = parse_user_datetime(when)
        return {"date": to_mizito_iso(dt), "time": dt.astimezone(TEHRAN).strftime("%H:%M"),
                "repeat_type": "none", "has_custom_repeat": False}

    def _labels(values: list[str] | None) -> list[str]:
        return [d.resolve_label(v) for v in values or []]

    def _project_has_chat(pid: str | None) -> bool:
        """The SPA task editor ticks "insert to chat group" whenever the
        project has a chat (SPA_CALLSITES §1). Mizito posts every later change
        of a task as a reply to that card, so a task saved without it never
        shows up in the project chat."""
        return bool(pid and (d.projects().get(pid) or {}).get("dialog"))

    # ------------------------------------------------------------ create

    @tool(write=True)
    def create_task(title: str, project: str, board: str | None = None,
                    assignees: list[str] | None = None, notes: str = "",
                    deadline: str | None = None, labels: list[str] | None = None,
                    checklist: list[str] | None = None, comment: str | None = None,
                    reminder: str | None = None,
                    post_card_to_project_chat: bool | None = None) -> dict:
        """Create a task in a project. Assignees get notified: confirm with the
        user first unless they asked for exactly this task.

        project: id or title (required: Mizito has no project-less tasks).
        board: kanban column title/id (default: the project's first column).
        assignees: names/ids/"me"; default ["me"]; [] = nobody.
        reminder: when the task is scheduled ("زمان یادآوری"): this is the date
            Mizito uses for today / overdue. "2026-11-20 14:30" | "1405/08/30 14:30".
        deadline: "مهلت انجام", only in projects with the deadline feature.
        checklist: item titles. comment: first comment text.
        post_card_to_project_chat: put a task card into the project chat.
            Default: yes when the project has a chat, like the web app. Later
            changes to the task show up in the chat only if it has this card.
        """
        title = (title or "").strip()
        if not title:
            raise ValueError("title is empty")
        pid = d.resolve_project(project, include_archived=False)
        if board:
            bid = d.resolve_board(board, pid)
        else:  # without a board the task sits in no column (seen live)
            boards = (d.projects().get(pid) or {}).get("kanban_boards") or []
            bid = boards[0]["_id"] if boards else None
        if deadline:
            _require_deadline_feature(pid)
        who = d.resolve_users(["me"] if assignees is None else assignees)
        card = (_project_has_chat(pid) if post_card_to_project_chat is None
                else bool(post_card_to_project_chat))
        body = {
            "title": title, "notes": notes or "", "assignee": who or [None],
            "project": pid, "kanban_board": bid, "labels": _labels(labels),
            "attachments": [], "deleted": False,
            "alarm_options": _alarm_options(reminder) if reminder else None,
            "progress": 0, "weight": 1, "deadline_start": None,
            "deadline": _deadline_iso(deadline), "comment": comment or "",
            "checklist": [{"title": x.strip(), "checked": False}
                          for x in checklist or [] if x and x.strip()],
            "responsible": None, "from_chat": False, "from_minute": False,
            "insert_to_chat_group": card,
        }
        resp = c.call("tasks/add", body, write=True)
        made = resp[0] if isinstance(resp, list) and resp else resp
        if not isinstance(made, dict) or not made.get("_id"):
            raise WriteNotVerified("tasks/add returned no task: check list_tasks before "
                                   "retrying (it may still have been created).")
        d.remember_tasks([made])
        d.invalidate("projects")
        try:
            t = get(made["_id"])
        except MizitoError as e:
            return {"ok": True, "verified": False, "task_id": made["_id"],
                    "warning": f"Created, but reading it back failed ({e}). Do NOT "
                               "create it again; check with get_task."}
        if norm(t.get("title")) != norm(title) or t.get("project") != pid:
            return {"ok": True, "verified": False, "task": shape.task_row(t, d, 0),
                    "warning": "Created, but title/project differ from the request."}
        return result(t, created=True, task_id=t["_id"])

    # ------------------------------------------------------------ update

    @tool(write=True)
    def update_task(task_id: str, title: str | None = None, notes: str | None = None,
                    assignees: list[str] | None = None,
                    add_assignees: list[str] | None = None,
                    remove_assignees: list[str] | None = None,
                    labels: list[str] | None = None, add_labels: list[str] | None = None,
                    remove_labels: list[str] | None = None,
                    deadline: str | None = None, clear_deadline: bool = False,
                    add_checklist: list[str] | None = None,
                    remove_checklist: list[str] | None = None) -> dict:
        """Edit a task. Only the arguments you pass change; everything else is
        sent back exactly as it is (Mizito's save replaces the whole task).

        assignees / labels replace the whole list; add_* / remove_* edit it.
        People and labels accept names or ids. remove_checklist takes item ids
        or exact titles (see get_task). add_checklist skips titles that already
        exist. To move columns use move_task; to complete use complete_task.

        Mizito has no partial update or version check: a change someone makes
        in the web app between this tool's read and its save is overwritten.
        """
        t = get(task_id)
        who = list(assignees_of(t))
        if assignees is not None:
            who = d.resolve_users(assignees)
        for u in d.resolve_users(add_assignees):
            if u not in who:
                who.append(u)
        drop = set(d.resolve_users(remove_assignees))
        who = [u for u in who if u not in drop]
        lbl = list(t.get("labels") or [])
        if labels is not None:
            lbl = _labels(labels)
        for l in _labels(add_labels):
            if l not in lbl:
                lbl.append(l)
        drop_l = set(_labels(remove_labels))
        lbl = [l for l in lbl if l not in drop_l]
        # send existing items back exactly as Mizito gave them (checked_by/at...)
        items = [dict(i) for i in t.get("checklist") or [] if isinstance(i, dict)]
        if remove_checklist:
            keys = {norm(x) for x in remove_checklist}
            items = [i for i in items
                     if i.get("_id") not in remove_checklist and norm(i.get("title")) not in keys]
        have = {norm(i.get("title")) for i in items}
        for x in add_checklist or []:
            if x and x.strip() and norm(x) not in have:
                have.add(norm(x))
                items.append({"title": x.strip(), "checked": False})
        if clear_deadline:
            dl = None
        elif deadline:
            _require_deadline_feature(t.get("project"))
            dl = _deadline_iso(deadline)
        else:
            dl = t.get("deadline") if t.get("has_deadline") else None
        new_title = title.strip() if title and title.strip() else t.get("title")
        body = {
            "title": new_title,
            "notes": t.get("notes") or "" if notes is None else notes,
            "assignee": who or [None], "project": t.get("project"),
            "kanban_board": t.get("kanban_board"), "labels": lbl,
            "attachments": t.get("attachments") or [], "deleted": False,
            "alarm_options": t.get("alarm_options"), "progress": t.get("progress") or 0,
            "weight": t.get("weight") or 1,
            "deadline_start": t.get("deadline_start") if t.get("has_deadline_start") else None,
            "deadline": dl, "comment": "", "checklist": items,
            "responsible": t.get("responsible"), "from_chat": False,
            "from_minute": False,
            "insert_to_chat_group": _project_has_chat(t.get("project")),
            "task_id": t["_id"], "token": token(task_id),
        }
        c.call("tasks/save", body, write=True)

        def ok(x: dict) -> bool:
            return (norm(x.get("title")) == norm(new_title)
                    and (notes is None or plain_text(x.get("notes")) == plain_text(notes))
                    and sorted(assignees_of(x)) == sorted(who)
                    and sorted(x.get("labels") or []) == sorted(lbl)
                    and len(x.get("checklist") or []) == len(items)
                    and (bool(x.get("has_deadline")) == bool(dl))
                    and (not dl or same_instant(x.get("deadline"), dl)))
        t = verify(task_id, ok, "fields passed to update_task")
        return result(t, updated=True)

    # ------------------------------------------------------------ comment

    @tool(write=True)
    def add_task_comment(task_id: str, text: str, reply_to: str | None = None,
                         mention: list[str] | None = None) -> dict:
        """Post a comment on a task (the task's people are notified).
        reply_to = a comment id from get_task; mention = names/ids to @."""
        text = (text or "").strip()
        if not text:
            raise ValueError("text is empty")
        before = {x.get("_id") for x in _comments(task_id)}
        mids = d.resolve_users(mention)
        c.call("tasks/newComment", {"token": token(task_id), "comment": text,
                                    "attachments": [], "mention": mids,
                                    "reply_id": reply_to}, write=True)
        me = d.me()
        new = [x for x in _comments(task_id) if x.get("_id") not in before
               and x.get("comment_owner") == me]
        if not new:
            raise WriteNotVerified("Comment did not appear: treat as NOT posted.")
        return {"ok": True, "comment": shape.comment(new[0], d)}

    # ------------------------------------------------------------ status

    @tool(write=True, idempotent=True)
    def complete_task(task_id: str) -> dict:
        """Mark a task done (notifies the task's people, like the web app)."""
        t = get(task_id)
        if t.get("completed"):
            return result(t, completed=True, note="was already done")
        c.call("tasks/setCompleted", {"token": token(task_id), "completed": True,
                                      "project": t.get("project")}, write=True)
        t = verify(task_id, lambda x: bool(x.get("completed")), "completed=true")
        return result(t, completed=True)

    @tool(write=True, idempotent=True)
    def reopen_task(task_id: str) -> dict:
        """Mark a done task as not done again."""
        t = get(task_id)
        if not t.get("completed"):
            return result(t, completed=False, note="was already open")
        c.call("tasks/setCompleted", {"token": token(task_id), "project": t.get("project"),
                                      "completed": False, "progress": t.get("progress") or 0,
                                      "undone_user_id": d.me()}, write=True)
        t = verify(task_id, lambda x: not x.get("completed"), "completed=false")
        return result(t, completed=False)

    @tool(write=True, idempotent=True)
    def set_task_progress(task_id: str, percent: int) -> dict:
        """Set a task's progress percentage (0-99). For 100 use complete_task:
        in the web app 100% means done, and it asks before completing."""
        if percent == 100:
            raise ValueError("100% means done in Mizito: the web app asks first, then "
                             "completes the task. Ask the user, then call complete_task.")
        if not 0 <= percent <= 100:
            raise ValueError("percent must be 0-99 (use complete_task for 100)")
        c.call("tasks/updateProgress", {"token": token(task_id), "progress": percent},
               write=True)
        t = verify(task_id, lambda x: (x.get("progress") or 0) == percent,
                   f"progress={percent}")
        return result(t, progress=percent)

    @tool(write=True, idempotent=True)
    def set_task_deadline(task_id: str, deadline: str | None) -> dict:
        """Set or clear (deadline=None) a task's deadline.

        Accepts "2026-11-20 14:30" (Gregorian, Tehran time), "1405/08/30 14:30"
        (Jalali) or ISO with Z. A date without time means 23:59 Tehran.
        """
        t = get(task_id)
        if deadline:
            _require_deadline_feature(t.get("project"))
        iso = to_mizito_iso(parse_user_datetime(deadline)) if deadline else None
        c.call("tasks/updateDeadline", {"token": token(task_id), "project": t.get("project"),
                                        "deadline": iso}, write=True)
        if iso:
            t = verify(task_id, lambda x: bool(x.get("has_deadline")) and
                       same_instant(x.get("deadline"), iso), f"deadline={iso}")
        else:
            t = verify(task_id, lambda x: not x.get("has_deadline"), "deadline cleared")
        return result(t, deadline=iso)

    @tool(write=True, idempotent=True)
    def set_task_reminder(task_id: str, when: str | None) -> dict:
        """Schedule a task ("زمان یادآوری"), or clear it with when=None. This
        is the date Mizito uses to put a task under today / overdue /
        upcoming, and when it reminds the assignees. Same date formats as
        create_task. (The web app calls this "snooze".)"""
        t = get(task_id)
        iso = to_mizito_iso(parse_user_datetime(when)) if when else None
        c.call("tasks/snooze", {"token": token(task_id), "project": t.get("project"),
                                "alarm_at": iso, "update_repeat_base": False}, write=True)
        if iso:
            t = verify(task_id, lambda x: same_instant(x.get("alarm_at") or x.get("sort_date"), iso),
                       f"reminder={iso}")
        else:
            t = verify(task_id, lambda x: not x.get("alarm_at"), "reminder cleared")
        return result(t, reminder=iso)

    # ------------------------------------------------------------ kanban

    @tool(write=True, idempotent=True)
    def move_task(task_id: str, board: str, position: str = "bottom") -> dict:
        """Move a task to another kanban board (column) of its project.

        board: board title or id (within the task's project).
        position: "top" or "bottom" of the target column.
        """
        t = get(task_id)
        pid = t.get("project")
        if not pid:
            raise ValueError("Personal tasks (no project) have no kanban boards.")
        bid = d.resolve_board(board, pid)
        from ..tasks_api import collect
        siblings = [x for x in collect(c, d, [{"project_id": pid}], "all")
                    if x.get("kanban_board") == bid and x.get("_id") != task_id]
        weights = [x.get("kanban_weight") or 0 for x in siblings]
        if position not in ("top", "bottom"):
            raise ValueError("position must be 'top' or 'bottom'")
        # The SPA's kanban drop (SPA_CALLSITES): empty column 1000, bottom =
        # last + 100, top = half the first. Halving cannot get above a weight
        # <= 0 (older versions of this tool wrote min - 100), so fall back.
        if not weights:
            weight = 1000
        elif position == "bottom":
            weight = max(weights) + 100
        else:
            first = min(weights)
            weight = first / 2 if first > 0 else first - 100
        c.call("tasks/setKanbanWeight", {"token": token(task_id), "projectId": pid,
                                         "kanbanBoardId": bid, "kanbanWeight": weight},
               write=True)
        t = verify(task_id, lambda x: x.get("kanban_board") == bid, f"board={bid}")
        return result(t, board=d.board_title(bid), position=position)

    # ------------------------------------------------------------ checklist

    @tool(write=True, idempotent=True)
    def set_checklist_item(task_id: str, item: str, checked: bool = True) -> dict:
        """Tick or untick one checklist item. `item` = the item id from
        get_task, or its exact/unique title.

        Same rules as the web app: no changes on a done or deleted task; an
        item someone else ticked can be unticked only by a project admin.
        When the last item gets ticked the result says all_items_done: the
        web app then asks whether to mark the task done, so ask the user and
        call complete_task (this tool never completes the task itself)."""
        if not item or not item.strip():
            raise ValueError("item is empty: pass a checklist item id or title")
        t = get(task_id)
        if t.get("completed") or t.get("deleted"):
            raise ValueError("The task is done or deleted: Mizito does not allow checklist "
                             "changes. Reopen it first (reopen_task).")
        items = t.get("checklist") or []
        hit = [i for i in items if i.get("_id") == item] or \
              [i for i in items if norm(i.get("title")) == norm(item)] or \
              [i for i in items if norm(item) in norm(i.get("title"))]
        if len(hit) != 1:
            raise ValueError(f"checklist item {item!r} matched {len(hit)} items; "
                             "pass the item id from get_task")
        cid = hit[0]["_id"]
        if not checked and hit[0].get("checked") and hit[0].get("checked_by") != d.me():
            p = d.projects().get(t.get("project")) or {}
            if not (p.get("is_advanced") and d.me() in (p.get("members_admin") or [])):
                raise ValueError("Someone else ticked this item: only a project admin can "
                                 "untick it (web app rule).")
        c.call("tasks/setChecklistCheckedValue", {"token": token(task_id),
                                                  "checklistId": cid, "checked": checked},
               write=True)
        t = verify(task_id, lambda x: any(i.get("_id") == cid and bool(i.get("checked")) == checked
                                          for i in x.get("checklist") or []),
                   f"checklist {cid} checked={checked}")
        out = result(t, item=hit[0].get("title"), checked=checked)
        now = t.get("checklist") or []
        if checked and now and all(i.get("checked") for i in now):
            out["all_items_done"] = True
            out["next"] = ("Every checklist item is ticked. The web app now asks whether "
                           "to mark the task done: ask the user, then call complete_task.")
        return out

    # ------------------------------------------------------------ comments

    def _comments(task_id: str) -> list[dict]:
        return c.call("tasks/getComments", {"token": token(task_id)}) or []

    @tool(write=True, idempotent=True)
    def edit_task_comment(task_id: str, comment_id: str, text: str) -> dict:
        """Replace the text of one of my task comments (ids from get_task)."""
        text = (text or "").strip()
        if not text:
            raise ValueError("text is empty")
        c.call("tasks/editComment", {"token": token(task_id), "commentId": comment_id,
                                     "newComment": text}, write=True)
        got = next((x for x in _comments(task_id) if x.get("_id") == comment_id), None)
        if not got or plain_text(got.get("comment")) != plain_text(text):
            raise WriteNotVerified("Comment text did not change; treat as NOT done.")
        return {"ok": True, "comment": shape.comment(got, d)}

    @tool(write=True, destructive=True, idempotent=True)
    def delete_task_comment(task_id: str, comment_id: str) -> dict:
        """Delete one of my task comments."""
        c.call("tasks/deleteComment", {"token": token(task_id), "commentId": comment_id},
               write=True)
        got = next((x for x in _comments(task_id) if x.get("_id") == comment_id), None)
        if got and not got.get("deleted"):
            raise WriteNotVerified("Comment is still there; treat as NOT deleted.")
        return {"ok": True, "deleted_comment_id": comment_id,
                "verified": "flagged deleted" if got else
                            "no longer listed (most likely deleted)"}

    # ------------------------------------------------------------ delete

    @tool(write=True, destructive=True)
    def delete_task(task_id: str) -> dict:
        """Delete a task (Mizito keeps it restorable: see restore_task).
        Confirm with the user first."""
        t = get(task_id)
        title = t.get("title")
        c.call("tasks/removeTask", {"token": token(task_id)}, write=True)
        try:
            after = c.call("tasks/get", {"token": token(task_id)}) or {}
        except BadRequest:
            after = {"deleted": True}  # the token no longer opens the task
        except MizitoError as e:
            raise WriteNotVerified(f"Delete sent, but the check failed ({e}). The task "
                                   "may or may not be deleted: look with get_task.") from None
        if not (after.get("deleted") or after.get("no_access_deleted")):
            raise WriteNotVerified("Task still looks alive; treat as NOT deleted.")
        return {"ok": True, "deleted_task_id": task_id, "title": title,
                "undo": "restore_task(task_id)"}

    @tool(write=True)
    def restore_task(task_id: str) -> dict:
        """Undo delete_task for a task id deleted earlier."""
        c.call("tasks/removeTaskUndo", {"token": token(task_id)}, write=True)
        t = verify(task_id, lambda x: not x.get("deleted"), "deleted=false")
        return result(t, restored=True)

    # ------------------------------------------------------------ misc

    @tool(write=True, idempotent=True)
    def bookmark_task(task_id: str, bookmarked: bool = True) -> dict:
        """Star/unstar a task in my own task list (private to me)."""
        c.call("tasks/toggleBookmark", {"token": token(task_id), "bookmarked": bookmarked},
               write=True)
        t = get(task_id)
        return result(t, bookmarked=bookmarked,
                      note="bookmark state is not returned by tasks/get; not re-checked")
