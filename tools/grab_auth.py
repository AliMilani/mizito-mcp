import json, urllib.request, asyncio, websockets, os, stat

PORT = int(os.environ.get("CDP_PORT", "9333"))
OUT = os.environ.get("MIZITO_ENV_FILE") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")


async def main():
    d = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json", timeout=5))
    t = [x for x in d if x["type"] == "page" and "mizito" in x.get("url", "")][0]
    async with websockets.connect(t["webSocketDebuggerUrl"],
                                  max_size=50 * 1024 * 1024, ping_interval=None) as ws:
        await ws.send(json.dumps({
            "id": 1, "method": "Runtime.evaluate",
            "params": {"returnByValue": True, "expression": """(() => {
                const o = {};
                for (let i = 0; i < localStorage.length; i++) {
                  const k = localStorage.key(i);
                  o[k] = (localStorage.getItem(k) || '').slice(0, 3000);
                }
                return JSON.stringify(o);
            })()"""}}))
        while True:
            m = json.loads(await ws.recv())
            if m.get("id") == 1:
                break
    store = json.loads(m["result"]["result"]["value"])
    tok = None
    for k, v in store.items():
        if isinstance(v, str) and v.startswith("eyJ") and len(v) > 60:
            if "token" in k.lower() or tok is None:
                tok = v
                tk = k
    print("localStorage keys:", list(store.keys()))
    if not tok:
        print("NO TOKEN FOUND"); return
    print(f"token key={tk} len={len(tok)}")

    wid = None
    for k, v in store.items():
        if "workspace" in k.lower() and isinstance(v, str) and len(v) == 24:
            wid = v
    with open(OUT, "w") as f:
        f.write(f"MIZITO_TOKEN={tok}\n")
        if wid:
            f.write(f"MIZITO_WORKSPACE_ID={wid}\n")
    os.chmod(OUT, stat.S_IRUSR | stat.S_IWUSR)
    print(f"wrote {OUT} (0600), workspace={wid}")

asyncio.run(main())
