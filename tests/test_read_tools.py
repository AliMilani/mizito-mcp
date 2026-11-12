"""End-to-end through FastMCP's in-memory client against the fake API."""
from tests.conftest import B1, B2, FAKE_JWT, LBL, ME, P1, P2, SARA, task


def test_list_tasks_project_filters_and_paging(call, fake):
    fake.tasks[P1] = ([task(i, assignee=[SARA] if i % 2 else [ME],
                            board=B2 if i % 3 == 0 else B1) for i in range(1, 61)]
                      + [task(100, completed=True)])
    r = call("list_tasks", project="فروشگاه آنلاین", limit=10)
    assert r["total"] == 60 and r["returned"] == 10 and r["has_more"]
    assert r["next_offset"] == 10
    # paging walked 3 pages of 25 for open + nothing else
    pages = [b["from"] for b in fake.bodies("tasks/upcoming")]
    assert pages == [0, 25, 50]
    r = call("list_tasks", project=P1, assignee="سارا", board="بررسی", limit=100)
    assert r["total"] == len([i for i in range(1, 61) if i % 2 and i % 3 == 0])
    assert all(t["assignees"] == ["سارا کاظمی"] for t in r["tasks"])
    r = call("list_tasks", project=P1, status="done")
    assert r["total"] == 1 and r["tasks"][0]["completed"]


def test_list_tasks_query_and_overdue(call, fake):
    fake.tasks[P1] = [
        task(1, title="رفع باگ صفحه پرداخت"),
        task(2, title="something else", notes="باگ inside notes"),
        task(3, title="late", has_deadline=True, deadline="2020-01-01T00:00:00.000Z"),
    ]
    r = call("list_tasks", project=P1, query="باگ")
    assert {t["title"] for t in r["tasks"]} == {"رفع باگ صفحه پرداخت", "something else"}
    r = call("list_tasks", project=P1, overdue_only=True)
    assert [t["title"] for t in r["tasks"]] == ["late"]
    assert r["tasks"][0]["overdue"] is True


def test_no_access_token_ever_leaves_the_server(call, fake):
    fake.tasks["inbox"] = [task(1)]
    fake.route("tasks/get", lambda b: task(1, notes="n"))
    fake.route("tasks/getComments", [])
    out = str(call("list_my_tasks")) + str(call("get_task", task_id=task(1)["_id"]))
    assert FAKE_JWT not in out and "access_token" not in out


def test_get_task_uses_token_and_shapes(call, fake):
    t = task(5, project=P2, checklist=[{"_id": "c1", "title": "a", "checked": True,
                                        "checked_by": SARA}],
             labels=[LBL])
    fake.tasks["inbox"] = [t]
    fake.route("tasks/get", lambda b: t if b == {"token": t["access_token"]} else 400)
    fake.route("tasks/getComments", [{"_id": "k", "comment": "hi", "comment_owner": SARA}])
    r = call("get_task", task_id=t["_id"])
    assert r["checklist_items"][0]["checked_by"] == "سارا کاظمی"
    assert r["labels"] == ["در حال انجام"]
    assert r["comment_list"][0]["author"] == "سارا کاظمی"


def test_read_chat_pages_with_offset(call, fake):
    msgs = [{"_id": f"{i:024x}", "from": SARA, "message": f"m{i}", "msg_index": i,
             "date": "2026-11-11T13:08:56.571Z"} for i in range(100, 0, -1)]
    fake.route("chat/getHistory",
               lambda b: msgs[b.get("offset", 0):b.get("offset", 0) + b["limit"]])
    r = call("read_chat", chat="سارا", limit=10)
    assert [m["index"] for m in r["messages"]][:2] == [100, 99] and r["has_more"]
    r = call("read_chat", chat="سارا", limit=10, offset=r["next_offset"])
    assert r["messages"][0]["index"] == 90


def test_daily_brief_runs(call, fake):
    fake.tasks["inbox"] = [task(1, has_deadline=True, deadline="2020-01-01T00:00:00.000Z")]
    fake.route("projects/allSummary", {"summaries": [{"project": P1, "name": "x",
                                                      "total_tasks": 3, "me_completed": 1}]})
    r = call("daily_brief")
    assert r["my_open"] == 1 and len(r["my_overdue"]) == 1
    assert r["unread_chats"][0]["title"] == "سارا کاظمی"


def test_overdue_follows_the_reminder_day_like_the_spa(call, fake):
    fake.tasks[P1] = [
        task(1, title="yesterday", sort_date="2020-01-01T08:00:00.000Z"),
        task(2, title="no date"),
        task(3, title="future", sort_date="2099-01-01T08:00:00.000Z"),
    ]
    r = call("list_tasks", project=P1, overdue_only=True)
    assert [t["title"] for t in r["tasks"]] == ["yesterday"]
    r = call("list_tasks", project=P1, sort="deadline")
    assert [t["title"] for t in r["tasks"]] == ["yesterday", "future", "no date"]


def test_read_chat_hides_deleted_but_pages_on_raw_rows(call, fake):
    msgs = [{"_id": f"{i:024x}", "from": SARA, "message": "." if i == 9 else f"m{i}",
             "deleted": i == 9, "msg_index": i} for i in range(10, 0, -1)]
    fake.route("chat/getHistory",
               lambda b: msgs[b.get("offset", 0):b.get("offset", 0) + b["limit"]])
    r = call("read_chat", chat="سارا", limit=3)
    assert [m["index"] for m in r["messages"]] == [10, 8] and r["next_offset"] == 3
    r = call("read_chat", chat="سارا", limit=3, include_deleted=True)
    assert [m["index"] for m in r["messages"]] == [10, 9, 8]
