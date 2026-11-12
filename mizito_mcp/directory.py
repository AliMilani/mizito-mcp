"""Cached reference data and name -> id resolution.

Tools accept either an id or a human name ("سارا", "فروشگاه آنلاین", "Done") for
users, projects, boards, labels and chats. Resolution rules (see `_pick`):
exact id -> exact normalised name -> unique substring -> error listing the
candidates. Ambiguity is always an error, never a guess.

Tasks are special: Mizito addresses a task by its per-task `access_token`
(a JWT), not by `_id`. Every task the server sees is remembered here
(`remember_tasks`), and `task_token()` searches inbox/outbox/projects when an
id was never seen. Tokens never leave this module's callers (see util.scrub).
"""
from __future__ import annotations

import threading
import time
from typing import Any, Callable, Iterable

from .client import LookupError_, MizitoClient
from .util import is_object_id, norm

ROLE_NAMES = {0: "member", 1: "admin", 2: "guest", 3: "bot"}
PAGE = 25  # Config.App.tasks_page_size in the SPA


class Directory:
    def __init__(self, client: MizitoClient, ttl: float = 300.0,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.c = client
        self.ttl = ttl
        self._clock = clock
        self._cache: dict[str, tuple[float, Any]] = {}
        self._lock = threading.RLock()
        self._tasks: dict[str, dict[str, Any]] = {}  # id -> {token, project}

    # --------------------------------------------------------------- cache

    def _cached(self, key: str, loader: Callable[[], Any]) -> Any:
        with self._lock:
            hit = self._cache.get(key)
            if hit and self._clock() - hit[0] < self.ttl:
                return hit[1]
        val = loader()
        with self._lock:
            self._cache[key] = (self._clock(), val)
        return val

    def invalidate(self, *prefixes: str) -> None:
        with self._lock:
            if not prefixes:
                self._cache.clear()
                return
            for k in list(self._cache):
                if k.startswith(prefixes):
                    del self._cache[k]

    def reset(self) -> None:
        """Forget everything (used after switching workspace)."""
        with self._lock:
            self._cache.clear()
            self._tasks.clear()

    # --------------------------------------------------------------- loaders

    def identity(self) -> dict:
        return self._cached("identity",
                            lambda: self.c.call("workspace/userId", {"regId": None}) or {})

    def me(self) -> str:
        uid = self.identity().get("uid")
        if not uid:
            raise LookupError_("Could not determine the current user id.")
        return uid

    def users(self) -> dict[str, dict]:
        def load():
            d = self.c.call("workspace/getUsers")
            rows = d.get("users", d) if isinstance(d, dict) else d
            return {u["_id"]: u for u in rows or [] if isinstance(u, dict) and u.get("_id")}
        return self._cached("users", load)

    def projects(self) -> dict[str, dict]:
        def load():
            d = self.c.call("projects/getList") or {}
            return {p["_id"]: p for p in d.get("projects") or [] if p.get("_id")}
        return self._cached("projects", load)

    def boards(self) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for pid, p in self.projects().items():
            for i, b in enumerate(p.get("kanban_boards") or []):
                if b.get("_id"):
                    out[b["_id"]] = {"id": b["_id"], "title": b.get("title"),
                                     "color": b.get("color"), "index": i,
                                     "project_id": pid,
                                     "project": p.get("title")}
        return out

    def labels(self, type_: str = "task") -> dict[str, dict]:
        def load():
            d = self.c.call("labels/getAll", {"type": type_}) or {}
            return {l["_id"]: l for l in d.get("labels") or []
                    if l.get("_id") and not l.get("deleted")}
        return self._cached(f"labels:{type_}", load)

    def dialogs(self) -> dict:
        return self._cached("dialogs", lambda: self.c.call("chat/getDialogs") or {})

    # --------------------------------------------------------------- names

    def user_name(self, uid: str | None) -> str | None:
        if not uid:
            return None
        u = self.users().get(uid)
        if not u:
            return None
        name = f"{u.get('first_name') or ''} {u.get('last_name') or ''}".strip()
        return name or u.get("username") or u.get("name")

    def user_names(self, uids: Iterable[str] | None) -> list[str]:
        return [self.user_name(u) or u for u in (uids or []) if u]

    def project_title(self, pid: str | None) -> str | None:
        return (self.projects().get(pid) or {}).get("title") if pid else None

    def board_title(self, bid: str | None) -> str | None:
        return (self.boards().get(bid) or {}).get("title") if bid else None

    def label_title(self, lid: str, type_: str = "task") -> str:
        return (self.labels(type_).get(lid) or {}).get("title") or lid

    def dialog_title(self, dialog: dict) -> str | None:
        if dialog.get("title"):
            return dialog["title"]
        peer = dialog.get("peer_user")
        return self.user_name(peer) or (f"DM {peer[:8]}" if peer else None)

    # --------------------------------------------------------------- resolve

    @staticmethod
    def _pick(query: str, items: list[tuple[str, str]], kind: str) -> str:
        """items = [(id, display name)]. Returns the id or raises."""
        q = (query or "").strip()
        if not q:
            raise LookupError_(f"Empty {kind}.")
        if any(i == q for i, _ in items):
            return q
        nq = norm(q)
        exact = [(i, n) for i, n in items if norm(n) == nq]
        if len(exact) == 1:
            return exact[0][0]
        pool = exact or [(i, n) for i, n in items if nq and nq in norm(n)]
        if len(pool) == 1:
            return pool[0][0]
        if not pool:
            names = ", ".join(repr(n) for _, n in items[:15])
            raise LookupError_(f"No {kind} matches {query!r}. Known: {names}")
        cands = ", ".join(f"{n!r} ({i})" for i, n in pool[:10])
        raise LookupError_(f"{kind} {query!r} is ambiguous: {cands}. "
                           "Pass the id or a longer name.")

    def resolve_user(self, query: str) -> str:
        if query in ("me", "self", "من"):
            return self.me()
        items = []
        for uid, u in self.users().items():
            if u.get("deleted"):
                continue
            items.append((uid, self.user_name(uid) or uid))
            if u.get("username"):
                items.append((uid, u["username"]))
        # de-duplicate ids so a name+username hit is not "ambiguous"
        try:
            return self._pick(query, items, "user")
        except LookupError_ as e:
            if "ambiguous" in str(e):
                nq = norm(query)
                ids = {i for i, n in items if nq in norm(n)}
                if len(ids) == 1:
                    return ids.pop()
            raise

    def resolve_users(self, queries: Iterable[str] | None) -> list[str]:
        return [self.resolve_user(q) for q in (queries or [])]

    def resolve_project(self, query: str, include_archived: bool = True) -> str:
        items = [(pid, p.get("title") or pid) for pid, p in self.projects().items()
                 if include_archived or not p.get("archived")]
        return self._pick(query, items, "project")

    def resolve_board(self, query: str, project_id: str | None = None) -> str:
        boards = self.boards()
        items = [(bid, b["title"] or bid) for bid, b in boards.items()
                 if project_id is None or b["project_id"] == project_id]
        return self._pick(query, items, "board")

    def resolve_label(self, query: str, type_: str = "task") -> str:
        items = [(lid, l.get("title") or lid) for lid, l in self.labels(type_).items()]
        return self._pick(query, items, f"{type_} label")

    def resolve_dialog(self, query: str, refresh_on_miss: bool = True) -> str:
        d = self.dialogs()
        rows: dict[str, dict] = {}
        for r in (d.get("dialogs") or []) + (d.get("pin_dialogs") or []):
            if r.get("_id"):
                rows.setdefault(r["_id"], r)  # a pinned chat is listed twice
        if is_object_id(query) and query in rows:
            return query
        items = [(i, self.dialog_title(r) or i) for i, r in rows.items()]
        try:
            return self._pick(query, items, "chat")
        except LookupError_ as e:
            if refresh_on_miss and "No chat matches" in str(e):
                self.invalidate("dialogs")  # a chat created since the cache filled
                return self.resolve_dialog(query, refresh_on_miss=False)
            raise

    def dm_with(self, uid: str) -> str | None:
        """Existing direct-chat dialog id with a user, if any."""
        for r in self.dialogs().get("dialogs") or []:
            if r.get("peer_user") == uid and not r.get("is_group"):
                return r.get("_id")
        return None

    def resolve_user_exact(self, query: str) -> str:
        """Like resolve_user but only an id or an exact (normalised) full name
        or username counts. Used where a fuzzy match would act on the wrong
        person (opening a DM and messaging them)."""
        if query in self.users():
            return query
        nq = norm(query)
        ids = {uid for uid, u in self.users().items() if not u.get("deleted")
               and (norm(self.user_name(uid)) == nq or norm(u.get("username")) == nq)}
        if len(ids) == 1:
            return ids.pop()
        raise LookupError_(
            f"No chat matches {query!r}, and it is not the exact full name of one "
            "person. Use list_chats / list_workspace_users and pass an id.")

    # --------------------------------------------------------------- tasks

    def remember_tasks(self, tasks: Iterable[dict]) -> None:
        with self._lock:
            for t in tasks or []:
                if isinstance(t, dict) and t.get("_id") and t.get("access_token"):
                    self._tasks[t["_id"]] = {"token": t["access_token"],
                                             "project": t.get("project")}

    def known_task(self, task_id: str) -> dict | None:
        with self._lock:
            return self._tasks.get(task_id)

    def task_token(self, task_id: str) -> str:
        """Per-task access token for `task_id`, searching if never seen."""
        hit = self.known_task(task_id)
        if hit:
            return hit["token"]
        if not is_object_id(task_id):
            raise LookupError_(f"{task_id!r} is not a task id (24 hex chars). "
                               "Use search_tasks or list_tasks to find it.")
        from .tasks_api import fetch_scope  # local import: avoids a cycle
        active = self.search_scopes(include_archived=False)
        archived = [s for s in self.search_scopes(include_archived=True) if s not in active]
        # cheapest and likeliest first: open tasks of active projects
        for scopes, done in ((active, False), (active, True),
                             (archived, False), (archived, True)):
            for scope in scopes:
                fetch_scope(self.c, self, scope, done)
                hit = self.known_task(task_id)
                if hit:
                    return hit["token"]
        raise LookupError_(
            f"Task {task_id} is not visible to this account (not in inbox, outbox "
            "or any project it can see). It may be deleted or private.")

    def search_scopes(self, include_archived: bool = False) -> list[dict]:
        """Scopes that together cover every task this account can see."""
        scopes: list[dict] = [{"inbox": True}, {"outbox": True}]
        for pid, p in self.projects().items():
            if p.get("deleted") or (p.get("archived") and not include_archived):
                continue
            scopes.append({"project_id": pid})
        return scopes
