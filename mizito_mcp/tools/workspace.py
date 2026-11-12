"""Identity, workspace, members, dashboard and health."""
from __future__ import annotations

import time

from .. import __version__
from .. import shape
from ..client import MizitoError
from ..directory import ROLE_NAMES
from ..util import fa_datetime
from . import Ctx


def register(tool, ctx: Ctx) -> None:
    c, d = ctx.client, ctx.dir

    @tool()
    def whoami() -> dict:
        """Current user and workspace: ids, name, role, plan days left, storage.

        Call first when you need your own user id (it appears as owner /
        assignee / message sender elsewhere).
        """
        ident = d.identity()
        name = c.call("workspace/name")
        me = d.users().get(ident.get("uid")) or {}
        plan = {}
        try:
            plan = c.call("workspace/planInfo") or {}
        except MizitoError:
            pass
        return {
            "user_id": ident.get("uid"),
            "name": d.user_name(ident.get("uid")),
            "role": ROLE_NAMES.get(me.get("role"), me.get("role")),
            "workspace_id": ident.get("wid"),
            "workspace_name": name if isinstance(name, str) else None,
            "is_guest": ident.get("is_guest"),
            "enterprise_plan": ident.get("is_enterprise_plan"),
            "plan_days_left": ident.get("remain_days"),
            "storage_used_gb": round((plan.get("used") or 0) / 2**30, 2) if plan else None,
            "storage_total_gb": round((plan.get("volume") or 0) / 2**30, 2) if plan else None,
            "read_only_mode": ctx.settings.read_only,
        }

    @tool()
    def list_workspace_users(include_contact: bool = False,
                             include_deleted: bool = False) -> list[dict]:
        """Members of the current workspace: id, name, role, online/last seen,
        and what each one last worked on.

        `include_contact=True` adds phone/email (personal data: only when the
        user actually needs it).
        """
        out = []
        for u in d.users().values():
            if u.get("deleted") and not include_deleted:
                continue
            out.append(shape.user(u, d, include_contact=include_contact))
        return sorted(out, key=lambda x: (not x.get("online"), x.get("name") or ""))

    @tool()
    def list_workspaces() -> list[dict]:
        """Every workspace this account belongs to, with unread chat/inbox and
        task counts per workspace. `current` marks the one tools act on."""
        cur = d.identity().get("wid")
        rows = c.call("dashboard/getAllSummary") or []
        out = []
        for w in rows if isinstance(rows, list) else [rows]:
            t = w.get("task") or {}
            out.append({
                "id": w.get("workspace_id"),
                "title": w.get("workspace_title"),
                "current": w.get("workspace_id") == cur,
                "unread_chat": w.get("chat"),
                "unread_inbox": w.get("inbox"),
                "tasks_today": t.get("today"),
                "tasks_overdue": t.get("overdue"),
                "tasks_with_deadline": t.get("with_time"),
                "tasks_without_deadline": t.get("no_time"),
                "meetings": len(w.get("meetings") or []) or None,
            })
        return out

    tokens: dict[str, str] = {}  # workspace id -> session token, memory only

    @tool()
    def switch_workspace(workspace: str) -> dict:
        """Point every tool at another workspace (id or title from
        list_workspaces) for the rest of this MCP session.

        Mizito binds a workspace to the token: `workspace/switch` mints a new
        token, and the previous one stays valid (verified 2026-11-12), so
        switching back is free. Kept in memory only: a restart returns to the
        workspace of the token in .env.
        """
        rows = c.call("dashboard/getAllSummary") or []
        items = [(w.get("workspace_id"), w.get("workspace_title") or w.get("workspace_id"))
                 for w in rows if isinstance(w, dict) and w.get("workspace_id")]
        from ..directory import Directory
        wid = Directory._pick(workspace, items, "workspace")
        cur = d.identity().get("wid")
        title = dict(items).get(wid)
        if wid == cur:
            return {"ok": True, "workspace_id": wid, "workspace": title, "note": "already current"}
        tokens[cur] = c.token_for_swap()
        if wid in tokens:
            c.set_token(tokens[wid])
        else:
            resp = c.call("workspace/switch", {"workspace_id": wid}) or {}
            if not resp.get("token"):
                raise MizitoError("workspace/switch returned no token.")
            tokens[wid] = resp["token"]
            c.set_token(resp["token"])
        d.reset()
        try:
            now = d.identity().get("wid")
        except MizitoError as e:
            now, err = None, e
        else:
            err = None
        if now != wid:
            # never leave the session half-switched: the next call would act
            # on a workspace the agent does not expect
            c.set_token(tokens[cur])
            d.reset()
            raise MizitoError(f"Switch did not take effect ({err or f'still {now}'}); "
                              "reverted to the previous workspace.")
        return {"ok": True, "workspace_id": wid, "workspace": title,
                "previous_workspace_id": cur}

    @tool()
    def get_dashboard_summary() -> list[dict]:
        """Raw cross-workspace rollup (unread + task buckets). Prefer
        list_workspaces, which is the same data, cleaned up."""
        d_ = c.call("dashboard/getAllSummary")
        return d_ if isinstance(d_, list) else [d_]

    @tool()
    def get_task_counts() -> dict:
        """My task badge counts in this workspace: due today and total open."""
        b = c.call("tasks/badge") or {}
        return {"due_today": b.get("today"), "open": b.get("count"),
                "total": b.get("total_count"), "raw": b}

    @tool()
    def health_check() -> dict:
        """Check the Mizito connection: token accepted, workspace, latency.

        Use when other tools fail, before telling the user Mizito is down.
        """
        t0 = time.monotonic()
        try:
            ident = c.call("workspace/userId", {"regId": None}) or {}
            ok, err = True, None
        except MizitoError as e:
            ident, ok, err = {}, False, str(e)
        return {
            "ok": ok,
            "error": err,
            "latency_ms": int((time.monotonic() - t0) * 1000),
            "workspace_id": ident.get("wid"),
            "user_id": ident.get("uid"),
            "plan_days_left": ident.get("remain_days"),
            "server_version": __version__,
            "read_only_mode": ctx.settings.read_only,
            "checked_at_fa": fa_datetime(time.time() * 1000),
        }
