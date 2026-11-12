"""Projects, kanban boards, labels."""
from __future__ import annotations

from .. import shape
from ..client import MizitoError
from . import Ctx


def register(tool, ctx: Ctx) -> None:
    c, d = ctx.client, ctx.dir

    def _summaries() -> dict[str, dict]:
        rows = (c.call("projects/allSummary", {"with_details": True}) or {}).get("summaries") or []
        return {s.get("project"): s for s in rows if s.get("project")}

    @tool()
    def list_projects(include_archived: bool = False,
                      with_counts: bool = True) -> list[dict]:
        """Projects in the workspace with boards, admins, chat id and (by
        default) task counts: total / done / open / overdue / mine_open.

        Archived projects are hidden unless include_archived=True.
        `project` arguments elsewhere accept these ids or titles.
        """
        sums = _summaries() if with_counts else {}
        out = []
        for p in d.projects().values():
            if p.get("deleted") or (p.get("archived") and not include_archived):
                continue
            row = shape.project(p, d)
            if p["_id"] in sums:
                row["counts"] = shape.summary_counts(sums[p["_id"]])
            out.append(row)
        return out

    @tool()
    def get_project(project: str) -> dict:
        """Full detail for one project (id or title): members, admins, boards
        with per-board open/done/overdue counts, settings, labels."""
        pid = d.resolve_project(project)
        full = c.call("projects/full", {"project_id": pid}) or {}
        out = shape.project(full or d.projects().get(pid, {}), d)
        out["members"] = d.user_names(full.get("members"))
        out["member_ids"] = full.get("members") or []
        out["settings"] = {k: v for k, v in full.items()
                           if k.startswith("advanced_") and v not in (None, False, "")}
        dialog = full.get("dialog")
        try:
            s = c.call("projects/chatSummary",
                       {"dialog": dialog, "project": pid, "withBoards": True}) or {}
        except MizitoError:
            s = {}
        if s:
            out["counts"] = shape.summary_counts(s)
            per_board = s.get("boards") or {}
            out["boards"] = [
                dict(b, counts=shape.summary_counts(per_board[b["id"]]))
                if b["id"] in per_board else b
                for b in out.get("boards") or []]
        return out

    @tool()
    def get_projects_summary(include_archived: bool = False) -> list[dict]:
        """Per-project task statistics only (fast status overview): total,
        done, open, overdue, due today, my open/overdue, last completion."""
        projects = d.projects()
        out = []
        for pid, s in _summaries().items():
            p = projects.get(pid) or {}
            if p.get("archived") and not include_archived:
                continue
            out.append({"project_id": pid,
                        "title": s.get("project_title") or s.get("name") or p.get("title"),
                        **shape.summary_counts(s)})
        return sorted(out, key=lambda r: -(r.get("open") or 0))

    @tool()
    def list_labels(type: str = "task") -> list[dict]:
        """Labels of a kind: "task" (default) or "project". Task tools accept
        these titles or ids in their `label` arguments."""
        return [{"id": lid, "title": l.get("title"), "color": l.get("color")}
                for lid, l in d.labels(type).items()]
