import json, urllib.request, asyncio, websockets, sys, os

PORT = int(os.environ.get("CDP_PORT", "9333"))


async def main():
    d = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json", timeout=5))
    t = [x for x in d if x["type"] == "page" and "mizito" in x.get("url", "")][0]
    async with websockets.connect(t["webSocketDebuggerUrl"],
                                  max_size=100 * 1024 * 1024,
                                  ping_interval=None) as ws:
        i = [0]
        async def call(method, params=None):
            i[0] += 1; mid = i[0]
            await ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
            while True:
                m = json.loads(await ws.recv())
                if m.get("id") == mid:
                    return m

        async def ev(expr, await_p=False):
            r = await call("Runtime.evaluate", {"expression": expr,
                                                "returnByValue": True,
                                                "awaitPromise": await_p})
            res = (r.get("result") or {})
            if "exceptionDetails" in res:
                return "EXC: " + str(res["exceptionDetails"])[:200]
            return ((res.get("result") or {}).get("value"))

        print("URL:", await ev("location.href"))

        # Probe endpoints directly with the app's own token, using its fetch.
        probe = r"""(async () => {
          const tok = localStorage.getItem('token') || localStorage.getItem('x-token') ||
                      (Object.keys(localStorage).filter(k=>/tok/i.test(k)).map(k=>localStorage.getItem(k))[0]);
          const eps = %s;
          const out = {};
          for (const ep of eps) {
            try {
              const r = await fetch('https://app.mizito.ir/api/' + ep, {
                method:'POST',
                headers:{'content-type':'application/json','x-token':tok},
                body: JSON.stringify(%s)
              });
              const txt = await r.text();
              out[ep] = {status:r.status, body: txt.slice(0, 1200)};
            } catch(e) { out[ep] = {err:String(e)}; }
          }
          return JSON.stringify(out);
        })()"""

        eps = json.loads(sys.argv[1])
        body = sys.argv[2] if len(sys.argv) > 2 else "{}"
        res = await ev(probe % (json.dumps(eps), body), await_p=True)
        try:
            data = json.loads(res)
        except Exception:
            print("RAW:", str(res)[:800]); return
        for k, v in data.items():
            st = v.get("status")
            b = (v.get("body") or v.get("err") or "")
            flag = "OK " if st == 200 and not b.startswith('{"status":0') else "-- "
            print(f"{flag}{st} {k}\n     {b[:420]}\n")

asyncio.run(main())
