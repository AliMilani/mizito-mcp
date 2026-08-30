#!/usr/bin/env python3
"""Isolated-Chrome CDP network capture.

Attaches to every page target on the debug port, records XHR/fetch traffic
(request headers+body, response headers+body) to JSONL. Never touches the
user's real Chrome profile.
"""
import asyncio, json, sys, time, urllib.request, os

PORT = int(os.environ.get("CDP_PORT", "9333"))
OUT = os.environ.get("CAPTURE_OUT", "capture.jsonl")
KEEP = {"XHR", "Fetch"}

os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
import websockets

reqs = {}          # requestId -> record
seen_targets = set()
out_f = open(OUT, "a", buffering=1)


def emit(rec):
    out_f.write(json.dumps(rec, ensure_ascii=False) + "\n")


async def pump(ws_url, tag):
    """Drive one target's CDP session."""
    try:
        async with websockets.connect(ws_url, max_size=60 * 1024 * 1024,
                                      ping_interval=None) as ws:
            mid = [0]

            async def send(method, params=None):
                mid[0] += 1
                await ws.send(json.dumps({"id": mid[0], "method": method,
                                          "params": params or {}}))
                return mid[0]

            await send("Network.enable", {"maxResourceBufferSize": 50_000_000,
                                          "maxTotalBufferSize": 200_000_000})
            await send("Page.enable")
            pending_body = {}

            async for raw in ws:
                msg = json.loads(raw)
                m = msg.get("method")

                if m == "Network.requestWillBeSent":
                    p = msg["params"]
                    reqs[p["requestId"]] = {
                        "target": tag,
                        "ts": time.time(),
                        "url": p["request"]["url"],
                        "method": p["request"]["method"],
                        "req_headers": p["request"].get("headers", {}),
                        "post_data": p["request"].get("postData"),
                        "type": p.get("type"),
                    }

                elif m == "Network.responseReceived":
                    p = msg["params"]
                    r = reqs.get(p["requestId"])
                    if not r:
                        continue
                    r["type"] = p.get("type") or r.get("type")
                    r["status"] = p["response"]["status"]
                    r["mime"] = p["response"].get("mimeType")
                    r["resp_headers"] = p["response"].get("headers", {})

                elif m == "Network.loadingFinished":
                    rid = msg["params"]["requestId"]
                    r = reqs.get(rid)
                    if not r:
                        continue
                    if r.get("type") in KEEP:
                        i = await send("Network.getResponseBody",
                                       {"requestId": rid})
                        pending_body[i] = rid
                    else:
                        reqs.pop(rid, None)

                elif "id" in msg and msg["id"] in pending_body:
                    rid = pending_body.pop(msg["id"])
                    r = reqs.pop(rid, None)
                    if not r:
                        continue
                    body = (msg.get("result") or {}).get("body")
                    if body and len(body) > 400_000:
                        body = body[:400_000] + "...TRUNC"
                    r["resp_body"] = body
                    emit(r)
    except Exception as e:
        print(f"[pump {tag}] {type(e).__name__}: {e}", file=sys.stderr)


async def main():
    tasks = {}
    while True:
        try:
            data = json.load(urllib.request.urlopen(
                f"http://127.0.0.1:{PORT}/json", timeout=5))
        except Exception:
            await asyncio.sleep(1); continue

        for t in data:
            if t.get("type") != "page":
                continue
            tid = t["id"]
            if tid in seen_targets:
                continue
            seen_targets.add(tid)
            url = (t.get("url") or "")[:60]
            print(f"[attach] {tid} {url}", flush=True)
            tasks[tid] = asyncio.create_task(
                pump(t["webSocketDebuggerUrl"], url))
        await asyncio.sleep(2)


asyncio.run(main())
