import pytest

from mizito_mcp.client import LookupError_
from mizito_mcp.directory import Directory
from tests.conftest import MEHDI, B1, B3, DLG_SARA, LBL, ME, P1, P2, SARA, task


@pytest.fixture
def d(client):
    return Directory(client)


def test_resolve_user_by_name_id_me_and_arabic_letters(d):
    assert d.resolve_user("سارا") == SARA
    assert d.resolve_user(SARA) == SARA
    assert d.resolve_user("me") == ME
    assert d.resolve_user("دستیار") == "6" * 24  # stored with Arabic ي


def test_resolve_ambiguous_raises_with_candidates(d):
    with pytest.raises(LookupError_, match="ambiguous"):
        d.resolve_project("فروشگاه")


def test_resolve_project_exact_beats_substring(d):
    assert d.resolve_project("پشتیبانی") == P2
    assert d.resolve_project("فروشگاه آنلاین") == P1


def test_resolve_board_scoped_to_project(d):
    with pytest.raises(LookupError_, match="ambiguous"):
        d.resolve_board("برای انجام")
    assert d.resolve_board("برای انجام", P1) == B1
    assert d.resolve_board("برای انجام", P2) == B3


def test_resolve_unknown_lists_known(d):
    with pytest.raises(LookupError_, match="No user matches"):
        d.resolve_user("nobody")


def test_dialog_titles_and_resolution(d):
    assert d.resolve_dialog("سارا کاظمی") == DLG_SARA
    assert d.resolve_label("در حال انجام") == LBL


def test_cache_avoids_refetch(d, fake):
    d.users(); d.users(); d.user_name(MEHDI)
    assert len(fake.bodies("workspace/getUsers")) == 1


def test_task_token_searches_scopes_and_caches(d, fake):
    t = task(7, project=P2)
    fake.tasks[P2] = [t]
    assert d.task_token(t["_id"]) == t["access_token"]
    n = len(fake.calls)
    d.task_token(t["_id"])
    assert len(fake.calls) == n  # second lookup is free


def test_task_token_unknown_id(d):
    with pytest.raises(LookupError_, match="not visible"):
        d.task_token("f" * 24)
    with pytest.raises(LookupError_, match="not a task id"):
        d.task_token("hello")


def test_pinned_chat_listed_twice_is_not_ambiguous(d, fake):
    rows = fake.routes["chat/getDialogs"](None)
    rows["pin_dialogs"] = [rows["dialogs"][0]]
    fake.route("chat/getDialogs", rows)
    assert d.resolve_dialog("سارا کاظمی") == DLG_SARA


def test_task_token_finds_open_task_in_archived_project(d, fake):
    t = task(9, project="a" * 24)
    fake.tasks["a" * 24] = [t]
    assert d.task_token(t["_id"]) == t["access_token"]
