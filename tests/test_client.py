import httpx
import pytest

from mizito_mcp.client import (AuthError, BadRequest, EndpointMissing,
                               MizitoClient, UpstreamError)


def make(handler, **kw):
    return MizitoClient("tok", transport=httpx.MockTransport(handler),
                        sleep=lambda _s: None, **kw)


def test_dotted_endpoint_and_headers():
    seen = {}

    def h(req):
        seen["path"] = req.url.path
        seen["token"] = req.headers.get("x-token")
        return httpx.Response(200, json={"ok": True})
    assert make(h).call("tasks.get", {"token": "t"}) == {"ok": True}
    assert seen == {"path": "/api/tasks/get", "token": "tok"}


@pytest.mark.parametrize("code,exc", [(401, AuthError), (403, AuthError),
                                      (405, EndpointMissing), (400, BadRequest),
                                      (502, UpstreamError)])
def test_status_mapping(code, exc):
    c = make(lambda r: httpx.Response(code, text="<html/>"))
    with pytest.raises(exc):
        c.call("x/y")


def test_reads_retry_transient_errors():
    n = {"i": 0}

    def h(req):
        n["i"] += 1
        return httpx.Response(503) if n["i"] < 3 else httpx.Response(200, json=[1])
    assert make(h).call("tasks/upcoming") == [1]
    assert n["i"] == 3


def test_writes_are_never_retried():
    n = {"i": 0}

    def h(req):
        n["i"] += 1
        return httpx.Response(503)
    with pytest.raises(UpstreamError):
        make(h).call("tasks/add", {}, write=True)
    assert n["i"] == 1


def test_network_error_on_write_says_read_back():
    def h(req):
        raise httpx.ConnectTimeout("boom")
    with pytest.raises(UpstreamError, match="read the object back"):
        make(h).call("chat/send", {}, write=True)


def test_auth_message_never_contains_token():
    c = make(lambda r: httpx.Response(401))
    with pytest.raises(AuthError) as e:
        c.call("workspace/userId")
    assert "tok" not in str(e.value).replace("token", "")


def test_missing_token_fails_fast():
    c = MizitoClient("", transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    with pytest.raises(AuthError, match="MIZITO_TOKEN"):
        c.call("workspace/userId")


def test_write_5xx_says_it_may_have_landed():
    c = make(lambda r: httpx.Response(502))
    with pytest.raises(UpstreamError, match="may still have been applied"):
        c.call("tasks/add", {}, write=True)


def test_http_200_error_body_raises():
    from mizito_mcp.client import AppError
    c = make(lambda r: httpx.Response(200, json={"error": "please_select_project"}))
    with pytest.raises(AppError, match="please_select_project"):
        c.call("tasks/add", {}, write=True)
