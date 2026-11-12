"""Offline test harness: a fake Mizito behind httpx.MockTransport.

No test here may reach the network. `FakeMizito` routes POST /api/<ep> to a
handler (dict body -> JSON-able result or an int status code) and records
every call so tests can assert on request bodies.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mizito_mcp.client import MizitoClient  # noqa: E402
from mizito_mcp.config import Settings  # noqa: E402

ME = "5e0000000000000000000001"
SARA = "5e0000000000000000000002"
MEHDI = "5e0000000000000000000003"
P1 = "5e00000000000000000000a1"
P2 = "5e00000000000000000000a2"
B1, B2, B3 = "5e00000000000000000000b1", "5e00000000000000000000b2", "5e00000000000000000000b3"
DLG_SARA = "5e00000000000000000000d1"
DLG_P1 = "5e00000000000000000000d2"
LBL = "5e00000000000000000000c1"
FAKE_JWT = "eyJhbGciOiJIUzI1NiJ9.eyJ0YXNrIjoieCIsInRva2VuIjoic2VjcmV0In0.c2lnbmF0dXJlLXNpZw"


def task(i: int, project: str = P1, board: str = B1, **kw) -> dict:
    tid = f"{i:024x}"
    base = {"_id": tid, "title": f"task {i}", "notes": "", "owner": ME,
            "assignee": [ME], "project": project, "kanban_board": board,
            "kanban_weight": i * 100, "completed": False, "labels": [],
            "checklist": [], "attachments": [], "has_deadline": False,
            "created_at": "2026-11-01T08:00:00.000Z",
            "modified_at": f"2026-11-{(i % 28) + 1:02d}T08:00:00.000Z",
            "access_token": f"{FAKE_JWT}{i}"}
    base.update(kw)
    return base


class FakeMizito:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.routes: dict[str, Callable[[Any], Any]] = {}
        self.tasks: dict[str, list[dict]] = {}  # scope key -> tasks
        self._defaults()

    def route(self, ep: str, fn: Callable[[Any], Any] | Any) -> None:
        self.routes[ep] = fn if callable(fn) else (lambda _b, v=fn: v)

    def _defaults(self) -> None:
        self.route("workspace/userId", {"uid": ME, "wid": "w1", "remain_days": 10})
        self.route("workspace/name", "شرکت نمونه")
        self.route("workspace/getUsers", {"users": [
            {"_id": ME, "first_name": "نیما", "last_name": "رستمی", "role": 1,
             "status": {"_": "userStatusOnline"}, "phone": "+15550100"},
            {"_id": SARA, "first_name": "سارا", "last_name": "کاظمی", "role": 0,
             "status": {"_": "userStatusOffline", "was_online": "2026-11-12T09:00:00.000Z"}},
            {"_id": MEHDI, "first_name": "مهدی", "last_name": "فرهمند", "role": 1,
             "status": {"_": "userStatusOffline"}},
            {"_id": "6" * 24, "first_name": "دستيار", "last_name": "ميزيتو", "role": 3,
             "status": {}},
        ]})
        self.route("projects/getList", {"projects": [
            {"_id": P1, "title": "فروشگاه آنلاین (فاز دوم)", "dialog": DLG_P1,
             "owner": MEHDI, "members_admin": [MEHDI], "archived": False,
             "is_advanced": True, "advanced_has_deadline": True,
             "kanban_boards": [{"_id": B1, "title": "برای انجام"},
                               {"_id": B2, "title": "بررسی"}]},
            {"_id": P2, "title": "پشتیبانی مشتری", "dialog": "d2", "archived": False,
             "kanban_boards": [{"_id": B3, "title": "برای انجام"}]},
            {"_id": "a" * 24, "title": "فروشگاه قدیمی", "archived": True,
             "kanban_boards": []},
        ]})
        self.route("labels/getAll", lambda b: {"labels": [
            {"_id": LBL, "title": "در حال انجام", "type": "task"}] if b.get("type") == "task" else []})
        self.route("chat/getDialogs", {"dialogs": [
            {"_id": DLG_SARA, "peer_user": SARA, "unread_count": 2,
             "last_message_date": "2026-11-11T13:08:56.571Z"},
            {"_id": DLG_P1, "title": "فروشگاه آنلاین (فاز دوم)", "is_group": True,
             "is_project_group": True, "project_entity": P1,
             "last_message_date": "2026-11-10T13:08:56.571Z"},
        ], "pin_dialogs": []})
        self.route("tasks/upcoming", self._upcoming)

    def _upcoming(self, body: dict) -> list[dict]:
        key = ("inbox" if body.get("inbox") else "outbox" if body.get("outbox")
               else body.get("project_id") or body.get("label_id"))
        done = bool((body.get("filter") or {}).get("done_status"))
        rows = [t for t in self.tasks.get(key, []) if bool(t.get("completed")) == done]
        start = body.get("from") or 0
        return rows[start:start + 25]

    def handler(self, request: httpx.Request) -> httpx.Response:
        ep = request.url.path.removeprefix("/api/")
        body = json.loads(request.content or b"{}")
        self.calls.append((ep, body))
        fn = self.routes.get(ep)
        if fn is None:
            return httpx.Response(405, text="<html>Error</html>")
        result = fn(body)
        if isinstance(result, int) and not isinstance(result, bool) and result >= 400:
            return httpx.Response(result, text="<html>Error</html>")
        return httpx.Response(200, json=result)

    def bodies(self, ep: str) -> list[Any]:
        return [b for e, b in self.calls if e == ep]


@pytest.fixture
def fake() -> FakeMizito:
    return FakeMizito()


@pytest.fixture
def client(fake: FakeMizito) -> MizitoClient:
    return MizitoClient("test-token", transport=httpx.MockTransport(fake.handler),
                        sleep=lambda _s: None)


@pytest.fixture
def settings() -> Settings:
    return Settings(token="test-token")


@pytest.fixture
def make_server(client: MizitoClient):
    from mizito_mcp.app import build

    def _make(read_only: bool = False):
        reg: dict[str, str] = {}
        srv = build(Settings(token="test-token", read_only=read_only), client, reg)
        return srv, reg
    return _make


@pytest.fixture
def call(make_server):
    """call(tool_name, **args) -> tool's structured result (sync wrapper)."""
    import asyncio

    from fastmcp import Client

    srv, _ = make_server()

    def _call(name: str, **args):
        async def run():
            async with Client(srv) as c:
                r = await c.call_tool(name, args)
                return r.structured_content if r.data is None else r.data
        return asyncio.run(run())
    return _call
