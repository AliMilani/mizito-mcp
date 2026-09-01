# Mizito MCP

MCP server for [Mizito](https://office.mizito.ir), the Iranian
project-management and team-chat tool. Projects, tasks, and internal chat.
Reads are broad; the only write is sending a chat message.

Built by reverse-engineering the SPA's own API; Mizito publishes no docs.

## Quick start

```bash
python3 -m venv .venv && .venv/bin/pip install fastmcp "httpx[socks]" websockets
./tools/refresh-auth.sh     # opens isolated Chrome, you log in, writes .env
```

Register `run-mcp.sh` as a stdio server in your MCP client. If the API starts
returning 401/403, the token expired: run `./tools/refresh-auth.sh` again and
restart the client.

## Tools

| Tool | What it answers |
|---|---|
| `whoami` | my user id, workspace id/name, plan days |
| `list_workspace_users` | members + ids (resolve an assignee id to a name) |
| `list_projects(include_archived=False)` | open projects, kanban boards, chat id |
| `get_projects_summary(with_details=True)` | per-project total/completed/overdue |
| `list_my_tasks(inbox=True, limit=50)` | what I'm assigned / what's due |
| `get_task_counts` | badge counts (due today, total open) |
| `get_dashboard_summary` | cross-workspace unread + task rollup |
| `list_chats(only_unread=False, limit=60)` | DMs + project groups, names resolved |
| `read_chat(dialog_id, limit=30)` | messages with sender names |
| `get_project_chat(project_id, limit=30)` | a project's group chat by project id |
| `send_message(text, dialog_id=None, to=None)` | **write** — post a message to a DM or group |

Typical chains:
- "any unread messages?" → `list_chats(only_unread=True)` → `read_chat(id)`
- "how's project X doing?" → `get_projects_summary` → filter by title
- "what's on my plate?" → `list_my_tasks`

## Layout

```
server.py            the MCP server (the only file that matters at runtime)
run-mcp.sh           launcher; sources .env, execs .venv/bin/python server.py
Dockerfile           portable build; token injected via --env-file
.env                 MIZITO_TOKEN (0600, gitignored)
tools/               reverse-engineering + maintenance kit
  refresh-auth.sh     re-login flow when the token expires
  launch-chrome.sh     isolated Chrome w/ CDP :9333 (Wayland-aware)
  capture.py           record all XHR traffic -> capture.jsonl
  grab_auth.py        pull token from the page's localStorage -> .env
  probe_api.py         probe endpoint names/params from inside the page
```

## API notes (reverse-engineered, 2026-08-30)

- Base `https://app.mizito.ir`. **Every** endpoint is `POST`; body `{}` when no args.
- Auth: one `x-token` header. Minted by `POST /capi/session/create`
  `{username, password}`, stored by the SPA in `localStorage.token`.
  **Verified by decoding it (2026-08-30):** HS256, claims are only `{jti, iat}` —
  there is **no `exp` claim**, so the token does not self-expire. It stays valid
  until Mizito revokes it server-side (logout elsewhere, password change, session
  purge). Two consequences:
  - Reliability: the MCP will not spontaneously break on a timer. If it 401s,
    something actively invalidated the session.
  - Security: `.env` holds a **non-expiring bearer credential equal to full
    account access**. Keep it 0600, never commit it, and re-run
    `tools/refresh-auth.sh` after any Mizito password change.
- **Status codes are the discovery oracle:** `405` = endpoint doesn't exist,
  `400` = exists but wrong params, `200` = correct. This turns name-guessing
  into a fast binary search.

| Endpoint | Body | Returns |
|---|---|---|
| `workspace/userId` | `{"regId":null}` | uid, wid, plan info |
| `workspace/name` | `{}` | workspace name (bare JSON string) |
| `workspace/getUsers` | `{}` | members |
| `projects/getList` | `{}` | `{projects:[...]}` w/ `kanban_boards`, `dialog` |
| `projects/allSummary` | `{"with_details":true}` | `{summaries:[...]}` |
| `tasks/upcoming` | `{"inbox":true,"from_dashboard":true,"from":null,"filter":null}` | task list |
| `tasks/badge` | `{}` | `{today,count,total_count}` |
| `chat/getDialogs` | `{}` | `{dialogs:[...], pin_dialogs:[...]}` |
| `chat/getHistory` | `{"dialog":"<id>","limit":20}` | message list |
| `chat/send` | `{"dialog":"<id>","message":"<text>"}` | `true` |
| `dashboard/getAllSummary` | `{}` | per-workspace rollup |
| `labels/getAll` | `{"type":"project"}` | labels |

Gotchas:
- `chat/getMessages` exists but always returns `[]` — **use `chat/getHistory`**.
- Chat messages are often task cards, not text: `media._ == "messageMediaTask"`.
  `read_chat` flags these as `type: "task_card"` so an empty `text` isn't
  mistaken for an empty message.
- DM dialogs have `title: null`; the name must be resolved via `peer_user`
  against `workspace/getUsers`.

## Known gap

**No per-project task list.** `tasks/getProjectTasks`, `projects/tasks`,
`tasks/list`, `tasks/getAll`, `tasks/getAllByProject` all return 405.
`tasks/get` returns 400 (exists, params unknown). To find it: run
`tools/capture.py`, open a project's task view in the browser, and read the
captured call. Until then `list_my_tasks` + `get_projects_summary` cover most
questions.

## Scope

**Reads plus one write: `send_message`.** No create/update/delete on projects or
tasks — that traffic was never captured, and untested writes against a live,
shared workspace are not worth the risk. Adding more writes = capture the
mutation in the browser first, then implement.

`send_message` notes (found 2026-09-01 by 405/400/200 probing, not by capture):
- Endpoint is `chat/send`; `chat/sendMessage` and friends are all 405.
- `{}` and `{dialog}` alone → 400. `{dialog, message}` → `200 true`.
- **`message:""` returns 200 too** and posts a blank message, so the tool
  rejects empty text before calling the API.
- The API returns bare `true`, no message object — the tool re-reads the last 15
  messages and matches the text, and raises if it isn't there. Don't trust a 200.
  The 15 (not 3) matters: bot peers like دستيار ميزيتو fire several auto-replies
  in the same second and push your own echo down the list.
- `to=` resolves a name/title substring against `list_chats`; ambiguous matches
  (e.g. a word shared by several project titles) raise with the candidates listed.
