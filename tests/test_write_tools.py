"""Write tools against a stateful fake: exact request bodies + read-back."""
import copy

import pytest

from tests.conftest import B1, B2, B3, DLG_P1, DLG_SARA, LBL, ME, P1, P2, SARA, task


@pytest.fixture
def store(fake):
    """A tiny stateful task backend keyed by access_token."""
    tasks = {}

    def put(t):
        tasks[t["access_token"]] = t
        fake.tasks.setdefault(t["project"], [])
        if t not in fake.tasks[t["project"]]:
            fake.tasks[t["project"]].append(t)
        return t

    def by_tok(b):
        return tasks.get(b.get("token")) or 400

    fake.route("tasks/get", lambda b: copy.deepcopy(by_tok(b)))

    def set_completed(b):
        tasks[b["token"]]["completed"] = b["completed"]
        return True
    fake.route("tasks/setCompleted", set_completed)

    def save(b):
        t = tasks[b["token"]]
        for k in ("title", "notes", "assignee", "labels", "deadline", "kanban_board"):
            t[k] = b[k]
        t["has_deadline"] = bool(b["deadline"])
        t["checklist"] = [dict(i, _id=i.get("_id") or f"new{n}") for n, i in enumerate(b["checklist"])]
        return t
    fake.route("tasks/save", save)

    def add(b):
        t = task(500, project=b["project"], board=b["kanban_board"] or B1,
                 title=b["title"], assignee=b["assignee"], notes=b["notes"])
        return put(t)
    fake.route("tasks/add", add)

    comments = []

    def new_comment(b):
        comments.insert(0, {"_id": f"c{len(comments)}", "comment": b["comment"],
                            "comment_owner": ME, "replied_comment_id": b["reply_id"],
                            "mention": b["mention"]})
        return True
    fake.route("tasks/newComment", new_comment)
    fake.route("tasks/getComments", lambda b: comments)

    def weight(b):
        t = tasks[b["token"]]
        t["kanban_board"], t["kanban_weight"] = b["kanbanBoardId"], b["kanbanWeight"]
        return True
    fake.route("tasks/setKanbanWeight", weight)

    def tick(b):
        for i in tasks[b["token"]]["checklist"]:
            if i["_id"] == b["checklistId"]:
                i["checked"] = b["checked"]
                i["checked_by"] = ME if b["checked"] else None
        return True
    fake.route("tasks/setChecklistCheckedValue", tick)
    return put


def test_complete_task_body_and_verify(call, fake, store):
    t = store(task(1))
    r = call("complete_task", task_id=t["_id"])
    assert r["ok"] and r["task"]["completed"]
    assert fake.bodies("tasks/setCompleted") == [
        {"token": t["access_token"], "completed": True, "project": P1}]
    assert "access_token" not in str(r)


def test_write_that_does_not_land_raises(call, fake, store):
    t = store(task(2))
    fake.route("tasks/setCompleted", True)  # server says OK, changes nothing
    with pytest.raises(Exception, match="NOT done"):
        call("complete_task", task_id=t["_id"])


def test_create_task_sends_spa_body(call, fake, store):
    r = call("create_task", title="  hello ", project="پشتیبانی", assignees=["سارا", "me"],
             checklist=["a", " ", "b"], reminder="1405/08/30 14:30", labels=["در حال انجام"])
    body = fake.bodies("tasks/add")[0]
    assert body["title"] == "hello"
    assert body["assignee"] == [SARA, ME]
    assert body["checklist"] == [{"title": "a", "checked": False}, {"title": "b", "checked": False}]
    assert body["deadline"] is None
    assert body["alarm_options"] == {"date": "2026-11-21T11:00:00.000Z", "time": "14:30",
                                     "repeat_type": "none", "has_custom_repeat": False}
    assert body["kanban_board"] == "5e00000000000000000000b3"  # first column by default
    assert body["labels"] == [LBL]
    assert body["insert_to_chat_group"] is True  # the project has a chat, like the web app
    assert r["verified"]["created"] and r["task"]["title"] == "hello"


def test_create_task_nobody_assigned(call, fake, store):
    call("create_task", title="x", project="پشتیبانی", assignees=[])
    assert fake.bodies("tasks/add")[0]["assignee"] == [None]


def test_update_task_round_trips_untouched_fields(call, fake, store):
    t = store(task(3, notes="keep me", labels=[LBL], assignee=[ME],
                   checklist=[{"_id": "k1", "title": "old", "checked": True}]))
    call("update_task", task_id=t["_id"], title="new", add_assignees=["سارا"],
         add_checklist=["fresh"], remove_checklist=["old"])
    b = fake.bodies("tasks/save")[0]
    assert b["title"] == "new" and b["notes"] == "keep me" and b["labels"] == [LBL]
    assert b["assignee"] == [ME, SARA]
    assert b["checklist"] == [{"title": "fresh", "checked": False}]
    assert b["task_id"] == t["_id"] and b["token"] == t["access_token"]


def test_add_comment_with_reply_and_mention(call, fake, store):
    t = store(task(4))
    r = call("add_task_comment", task_id=t["_id"], text="سلام", reply_to="c9",
             mention=["سارا"])
    assert fake.bodies("tasks/newComment") == [{"token": t["access_token"], "comment": "سلام",
                                                "attachments": [], "mention": [SARA],
                                                "reply_id": "c9"}]
    assert r["comment"]["text"] == "سلام"


def test_move_task_to_bottom_of_board(call, fake, store):
    store(task(5, board=B2, kanban_weight=300))
    t = store(task(6, board=B1))
    r = call("move_task", task_id=t["_id"], board="بررسی")
    b = fake.bodies("tasks/setKanbanWeight")[0]
    assert b["kanbanBoardId"] == B2 and b["kanbanWeight"] == 400 and b["projectId"] == P1
    assert r["task"]["board"] == "بررسی"


# ---------------------------------------------------------------- chat

@pytest.fixture
def chat(fake):
    history = []

    def send(b):
        history.insert(0, {"_id": f"{len(history) + 1:024x}", "from": ME,
                           "message": b["message"], "dialog": b["dialog"],
                           "reply_to": b.get("reply_to"),
                           "date": "2099-01-01T00:00:00.000Z"})
        return True
    fake.route("chat/send", send)
    fake.route("chat/getHistory", lambda b: history[b.get("offset", 0):b.get("offset", 0) + b["limit"]])
    return history


def test_send_message_verified_and_body(call, fake, chat):
    r = call("send_message", text="hi\nthere", to="سارا", reply_to="a" * 24)
    assert fake.bodies("chat/send") == [{"dialog": DLG_SARA, "message": "hi\nthere",
                                         "reply_to": "a" * 24}]
    assert r["ok"] and r["message"]["text"] == "hi\nthere"


def test_send_message_rejects_empty_and_ambiguous(call, fake, chat):
    with pytest.raises(Exception, match="empty"):
        call("send_message", text="   ", dialog_id=DLG_P1)
    assert not fake.bodies("chat/send")


def test_send_message_opens_dm_for_person_without_chat(call, fake, chat):
    fake.route("chat/createDialog", lambda b: {"_id": "e" * 24} if b == {"user": "5e0000000000000000000003"} else 400)
    r = call("send_message", text="yo", to="مهدی فرهمند")  # exact full name only
    assert r["chat_id"] == "e" * 24


def test_send_message_unverified_raises(call, fake, chat):
    fake.route("chat/send", True)  # accepted but never shows up
    with pytest.raises(Exception, match="BEFORE sending again"):
        call("send_message", text="ghost", dialog_id=DLG_SARA)


def test_edit_and_delete_message(call, fake):
    mid = "b" * 24
    state = {"message": "old", "deleted": False}
    fake.route("chat/updateSentMessage", lambda b: state.update(message=b["newMessage"]) or True)
    fake.route("chat/removeSentMessage", lambda b: state.update(deleted=True) or True)
    fake.route("chat/getMessages", lambda b: [dict(state, _id=mid, **{"from": ME})])
    assert call("edit_message", chat="سارا", message_id=mid, text="new")["message"]["text"] == "new"
    assert fake.bodies("chat/updateSentMessage") == [{"dialog": DLG_SARA, "mid": mid, "newMessage": "new"}]
    assert call("delete_message", chat="سارا", message_id=mid)["ok"]


def test_read_only_mode_registers_no_write_tools(make_server):
    _, reg = make_server(read_only=True)
    assert reg and all(v == "read" for v in reg.values())
    _, reg = make_server()
    assert {"send_message", "create_task", "update_task"} <= {k for k, v in reg.items() if v == "write"}


def test_switch_workspace_keeps_tokens_in_memory(call, fake):
    fake.route("dashboard/getAllSummary", [{"workspace_id": "w1", "workspace_title": "A"},
                                           {"workspace_id": "w2", "workspace_title": "آزمایشی"}])
    state = {"wid": "w1"}
    fake.route("workspace/switch", lambda b: state.update(wid=b["workspace_id"]) or {"token": "t2"})
    fake.route("workspace/userId", lambda b: {"uid": ME, "wid": state["wid"]})
    r = call("switch_workspace", workspace="آزمایشی")
    assert r == {"ok": True, "workspace_id": "w2", "workspace": "آزمایشی", "previous_workspace_id": "w1"}
    assert "t2" not in str(r)


# ---------------------------------------------------------------- review regressions

def test_to_never_opens_dm_on_fuzzy_name(call, fake, chat):
    fake.route("chat/createDialog", {"_id": "e" * 24})
    with pytest.raises(Exception, match="not the exact full name"):
        call("send_message", text="x", to="فرهم")  # substring of مهدی فرهمند
    assert not fake.bodies("chat/createDialog") and not fake.bodies("chat/send")


def test_to_exact_full_name_reuses_existing_dm(call, fake, chat):
    r = call("send_message", text="x", to=SARA)
    assert r["chat_id"] == DLG_SARA and not fake.bodies("chat/createDialog")


def test_identical_earlier_message_is_not_taken_as_proof(call, fake, chat):
    chat.append({"_id": "f" * 24, "from": ME, "message": "+1", "dialog": DLG_SARA,
                 "date": "2099-01-01T00:00:00.000Z"})
    fake.route("chat/send", True)  # accepted, never delivered
    with pytest.raises(Exception, match="BEFORE sending again"):
        call("send_message", text="+1", dialog_id=DLG_SARA)


def test_html_stored_text_still_verifies(call, fake, chat):
    def send(b):
        chat.insert(0, {"_id": "9" * 24, "from": ME, "dialog": b["dialog"],
                        "message": "<div>hi</div><div>there &amp; you</div>"})
        return True
    fake.route("chat/send", send)
    assert call("send_message", text="hi\nthere & you", dialog_id=DLG_SARA)["ok"]


def test_checklist_empty_item_rejected(call, fake, store):
    t = store(task(7, checklist=[{"_id": "i1", "title": "only", "checked": False}]))
    with pytest.raises(Exception, match="item is empty"):
        call("set_checklist_item", task_id=t["_id"], item=" ")
    assert not fake.bodies("tasks/setChecklistCheckedValue")


def test_delete_task_with_failing_check_is_not_reported_ok(call, fake, store):
    t = store(task(8))
    fake.route("tasks/removeTask", True)
    calls = {"n": 0}

    def get(b):
        calls["n"] += 1
        return t if calls["n"] == 1 else 502
    fake.route("tasks/get", get)
    with pytest.raises(Exception, match="may or may not be deleted"):
        call("delete_task", task_id=t["_id"])


def test_create_task_read_back_failure_still_reports_created(call, fake, store):
    fake.route("tasks/get", 502)
    r = call("create_task", title="x", project="پشتیبانی")
    assert r["ok"] and r["verified"] is False and "Do NOT create it again" in r["warning"]


def test_deadline_only_in_projects_with_the_feature(call, fake, store):
    with pytest.raises(Exception, match="does not use deadlines"):
        call("create_task", title="x", project="پشتیبانی", deadline="2026-12-01")
    assert not fake.bodies("tasks/add")
    call("create_task", title="x", project="فروشگاه آنلاین", deadline="2026-12-01 10:00")
    assert fake.bodies("tasks/add")[0]["deadline"] == "2026-12-01T06:30:00.000Z"


def test_set_task_reminder_uses_snooze(call, fake, store):
    t = store(task(11))

    def snooze(b):
        t["alarm_at"] = t["sort_date"] = b["alarm_at"]
        return True
    fake.route("tasks/snooze", snooze)
    r = call("set_task_reminder", task_id=t["_id"], when="2026-12-01 09:30")
    assert fake.bodies("tasks/snooze") == [{"token": t["access_token"], "project": P1,
                                            "alarm_at": "2026-12-01T06:00:00.000Z",
                                            "update_repeat_base": False}]
    assert r["task"]["reminder_fa"] == "1405/09/10 09:30"


# ---------------------------------------------------------------- web-app parity

OTHER = "7" * 24


def _projects(fake, **changes):
    """Edit the fake projects/getList rows: changes = {project_id: {field: value}}."""
    rows = copy.deepcopy(fake.routes["projects/getList"](None)["projects"])
    for p in rows:
        p.update(changes.get(p["_id"], {}))
    fake.route("projects/getList", {"projects": rows})


def test_create_task_card_follows_project_chat(call, fake, store):
    _projects(fake, **{P1: {"dialog": None}})
    call("create_task", title="x", project=P1)
    call("create_task", title="y", project=P2, post_card_to_project_chat=False)
    call("create_task", title="z", project=P1, post_card_to_project_chat=True)
    assert [b["insert_to_chat_group"] for b in fake.bodies("tasks/add")] == [False, False, True]


def test_update_task_sends_card_flag_like_the_editor(call, fake, store):
    a = store(task(20))
    b = store(task(21, project=P2, board=B3))
    _projects(fake, **{P2: {"dialog": None}})
    call("update_task", task_id=a["_id"], title="a2")
    call("update_task", task_id=b["_id"], title="b2")
    assert [x["insert_to_chat_group"] for x in fake.bodies("tasks/save")] == [True, False]


def _items(*states):
    return [{"_id": f"i{n}", "title": f"item {n}", "checked": c, "checked_by": by}
            for n, (c, by) in enumerate(states)]


def test_checklist_refused_on_done_or_deleted_task(call, fake, store):
    done = store(task(22, completed=True, checklist=_items((False, None))))
    gone = store(task(23, deleted=True, checklist=_items((False, None))))
    for t in (done, gone):
        with pytest.raises(Exception, match="done or deleted"):
            call("set_checklist_item", task_id=t["_id"], item="i0")
    assert not fake.bodies("tasks/setChecklistCheckedValue")


def test_checklist_untick_other_persons_item_needs_project_admin(call, fake, store):
    t = store(task(24, checklist=_items((True, OTHER), (True, ME))))
    with pytest.raises(Exception, match="only a project admin"):
        call("set_checklist_item", task_id=t["_id"], item="i0", checked=False)
    assert not fake.bodies("tasks/setChecklistCheckedValue")
    call("set_checklist_item", task_id=t["_id"], item="i1", checked=False)  # my own tick
    assert len(fake.bodies("tasks/setChecklistCheckedValue")) == 1


def test_checklist_project_admin_may_untick_other_persons_item(call, fake, store):
    _projects(fake, **{P1: {"members_admin": [ME]}})
    t = store(task(25, checklist=_items((True, OTHER))))
    r = call("set_checklist_item", task_id=t["_id"], item="i0", checked=False)
    assert r["ok"] and r["verified"]["checked"] is False


def test_checklist_last_tick_reports_all_items_done(call, fake, store):
    t = store(task(26, checklist=_items((True, ME), (False, None), (False, None))))
    r = call("set_checklist_item", task_id=t["_id"], item="i1")
    assert "all_items_done" not in r
    r = call("set_checklist_item", task_id=t["_id"], item="i2")
    assert r["all_items_done"] is True and "complete_task" in r["next"]
    assert not fake.bodies("tasks/setCompleted")  # never completes on its own


def test_move_task_weights_like_kanban_drop(call, fake, store):
    t = store(task(27, board=B1))
    call("move_task", task_id=t["_id"], board=B2)  # empty column
    store(task(28, board=B2, kanban_weight=800))
    u = store(task(29, board=B1))
    call("move_task", task_id=u["_id"], board=B2, position="top")  # half of 800
    store(task(30, board=B1, kanban_weight=-50))  # left by the old min - 100 rule
    v = store(task(31, board=B2))
    call("move_task", task_id=v["_id"], board=B1, position="top")
    weights = [b["kanbanWeight"] for b in fake.bodies("tasks/setKanbanWeight")]
    assert weights == [1000, 400, -150]


def test_progress_100_is_refused_in_favour_of_complete_task(call, fake, store):
    t = store(task(32))
    with pytest.raises(Exception, match="complete_task"):
        call("set_task_progress", task_id=t["_id"], percent=100)
    assert not fake.bodies("tasks/updateProgress") and not fake.bodies("tasks/setCompleted")
