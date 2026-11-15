# Mizito MCP

MCP server for [Mizito](https://office.mizito.ir), the Iranian project-management
and team-chat tool. It covers projects, kanban boards, tasks, task comments and
history, workload, team chat, and switching between workspaces.

Mizito publishes no API. Everything was reverse-engineered from the web app's
own JavaScript and checked against the live API.

## Setup

Needs Python 3.11+, and Google Chrome for the login helper.

```bash
git clone https://github.com/AliMilani/mizito-mcp.git && cd mizito-mcp
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt websockets   # websockets: login helper only
./tools/refresh-auth.sh                                 # log in once, writes .env (0600)
```

`refresh-auth.sh` opens Chrome with a separate, empty profile, waits for you to
log in to Mizito, and copies the session token from the page into `.env`. Your
everyday browser profile is never touched. You can also paste a token into
`.env` by hand (`cp .env.example .env && chmod 600 .env`).

Then register `run-mcp.sh` as a stdio server in your MCP client. Most clients
take a JSON entry like this:

```json
{
  "mcpServers": {
    "mizito": { "command": "/absolute/path/to/mizito-mcp/run-mcp.sh" }
  }
}
```

The token never goes into the client's config: `run-mcp.sh` reads it from
`.env`. It also honours:

- `MIZITO_ENV_FILE`: another env file (for example one per workspace or account).
  Not needed when `MIZITO_TOKEN` is already in the environment.
- `MIZITO_PYTHON`: the interpreter to use (default `.venv/bin/python`, else `python3`).

Docker works too; the token stays out of the image:

```bash
docker build -t mizito-mcp .
docker run --rm -i --env-file .env mizito-mcp
```

If tools start failing with "Mizito rejected the token", the session was revoked
(logout elsewhere, password change). Run `./tools/refresh-auth.sh` again, then
restart your MCP client.

Options (in `.env`):

- `MIZITO_READ_ONLY=1`: no write tools at all.
- `MIZITO_LOG_LEVEL=INFO`: one stderr line per API call, never with bodies or the token.
- `MIZITO_CACHE_TTL=300`: seconds that users, projects, labels and chats stay cached.

## Tools

Arguments for people, projects, boards, labels and chats accept an **id or a
name**. Persian names match even with Arabic ي/ك or ZWNJ differences. `"me"` means
you. An ambiguous name is an error that lists the candidates.

Dates come back as UTC ISO plus `*_fa` in Tehran time on the Jalali calendar
(`1405/08/21 14:30`). Date inputs accept `2026-11-20 14:30`, `1405/08/30 14:30`
or ISO with `Z`.

### Read (25)

| Tool | Answers |
|---|---|
| `daily_brief` | standup in one call: my overdue / due today, unread chats, project counts |
| `whoami` / `health_check` | who am I, which workspace, plan days, storage / is Mizito reachable |
| `list_workspaces` / `switch_workspace` | every workspace with unread counts / act on another one (in memory) |
| `list_workspace_users` | members, roles, online/last seen, what each last worked on |
| `list_projects` / `get_project` | projects with boards and counts / one project: members, per-board counts |
| `get_projects_summary` | per-project open / done / overdue only |
| `list_labels` | task or project labels |
| `list_tasks` | the main task query: project / mine / outbox / everything; board, assignee, owner, label, open/done/all, overdue, text; paginated |
| `list_my_tasks` | my tasks, overdue first |
| `search_tasks` | Mizito's own search (includes archived projects) plus exact local match |
| `get_task` | full task: notes, checklist with ids, attachments, comments, optional history |
| `get_task_comments` / `get_task_history` / `get_task_seen` | comments / change log / who opened it |
| `get_user_workload` | one person's open tasks across projects, per project, overdue |
| `get_task_counts` / `get_dashboard_summary` | badge counts / raw cross-workspace rollup |
| `list_chats` | DMs, groups and project chats, unread counts, filter by kind or title |
| `read_chat` / `get_project_chat` | paged history (offset), sender names, replies, task cards |
| `search_chat` / `search_messages` | server search in one chat (text or sender) / across all chats |

### Write (19; each one reads back and fails loudly if the change did not land)

| Tool | Does |
|---|---|
| `send_message` | to a chat title, a dialog id, or a person by exact full name (opens the DM); `reply_to`, `mention` |
| `edit_message` / `delete_message` / `mark_chat_read` | my own message / for everyone / clear the unread badge |
| `create_task` | in a project: board (default first), assignees, notes, reminder, deadline, labels, checklist, first comment; posts the task card to the project chat like the web app |
| `update_task` | title, notes, assignees (set/add/remove), labels, deadline, checklist add/remove |
| `complete_task` / `reopen_task` | done / not done |
| `set_task_reminder` | schedule / clear: the date Mizito uses for today and overdue |
| `set_task_progress` / `set_task_deadline` | percentage 0-99 (100 = `complete_task`) / deadline (only projects with the deadline feature) |
| `move_task` | to another kanban column, top or bottom (same weights as the web app) |
| `set_checklist_item` | tick or untick by id or title, with the web app's rules; reports when every item is ticked |
| `add_task_comment` / `edit_task_comment` / `delete_task_comment` | with reply and mentions |
| `delete_task` / `restore_task` | soft delete with undo |
| `bookmark_task` | private star |

Write tools change shared data that teammates see and get notified about.
All write tools were verified live on 2026-11-12 in a private sandbox project ([docs/API.md](docs/API.md)).

## Typical chains

- "what's going on?": `daily_brief`
- "Sara's open tasks?": `get_user_workload(user="سارا")`
- "what is overdue in the shop project?": `list_tasks(project="فروشگاه", overdue_only=True)`
- "any message from Sara?": `list_chats(only_unread=True)`, then `read_chat(chat="سارا")`
- "mark the payment-bug task done": `search_tasks("باگ پرداخت")`, then `complete_task(task_id)`

## Tests

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest          # 65 offline tests, no network
.venv/bin/python tools/smoke.py     # live: every read tool over real stdio
```

`tools/smoke.py` only calls read tools, but it reads your real workspace.
`MIZITO_READ_ONLY=1 .venv/bin/python tools/smoke.py` also proves the write gate.

## Development

Layout:

```
server.py                 entry point (run-mcp.sh and Docker exec this path)
run-mcp.sh                sources .env, execs .venv/bin/python server.py
mizito_mcp/
  config.py               env -> Settings (MIZITO_TOKEN, MIZITO_READ_ONLY, ...)
  client.py               HTTP; error mapping; read retries; no write retries
  util.py                 Persian normalisation, Jalali/Tehran dates, scrub()
  directory.py            TTL caches + name->id resolution + task token registry
  tasks_api.py            task scopes, paging (25/page via `from`), local filters, sort
  shape.py                raw Mizito JSON -> compact dicts for the client
  tools/__init__.py       @tool decorator (annotations, scrub, read-only gate)
  tools/workspace.py      whoami, users, workspaces, health, counts
  tools/projects.py       projects, project detail (+per-board counts), labels
  tools/tasks.py          list/search/get task, comments, history, workload, brief
  tools/task_writes.py    task mutations (each verified by read-back)
  tools/chat.py           chats, paged history, project chat, search
  tools/chat_writes.py    send / reply / edit / delete messages, mark read
  app.py                  build() -> FastMCP server + instructions for the client
tests/                    offline pytest suite (fake Mizito via httpx.MockTransport)
tools/smoke.py            live: spawns run-mcp.sh over stdio, calls every read tool
tools/extract_endpoints.py  regenerates docs/ENDPOINTS.md from the live SPA bundle
tools/refresh-auth.sh     re-login flow when the token is revoked (isolated Chrome)
tools/capture.py etc.     CDP capture/probe kit for finding new endpoints
```

Rules the code relies on:

1. **Never expose a task `access_token`.** It is a JWT whose payload embeds the
   user's session token. `util.scrub()` runs on every tool result as a safety
   net. The same goes for `MIZITO_TOKEN`: never print, log or commit it.
2. **No guessed write endpoints.** Every write body comes from the SPA call site
   (cited in docs/API.md) and is verified live on a throwaway object first.
3. **Every write reads back** and raises if the change is not visible. Writes
   are never retried automatically (`client.call(..., write=True)`).
4. **Ambiguity is an error.** Name -> id resolution never guesses between
   candidates. Where a wrong match would message the wrong person (opening a
   new DM), only an id or an exact full name counts.
5. **Verify by identity, not by time.** A send or comment proves itself by a
   NEW id. When the write surely happened but the read-back failed, the tool
   returns `verified: false` instead of raising, so the caller does not retry
   and create a duplicate.

Adding a feature:

1. Find the call site in the decompressed bundle:
   `grep -o '.\{300\}invokeApi("ns.method".\{300\}' a_dec.js`
   (`tools/extract_endpoints.py` shows how to get it; it is gzip without a
   Content-Encoding header).
2. Probe reads live. 200 = right, 400 = wrong body, 405 = wrong name.
3. For writes: create a throwaway private task, exercise the write on it, read
   it back, delete it.
4. Add the tool in the right `tools/*.py`, shape its output in `shape.py`, add
   an offline test with the fake in `tests/conftest.py`, run pytest and smoke.py.
5. Update docs/API.md and the tool tables above.

MCP clients bind the tool list at session start: restart the client after
changing tools.

## Docs

- [docs/API.md](docs/API.md): verified endpoints, bodies, gotchas
- [docs/ENDPOINTS.md](docs/ENDPOINTS.md): all SPA endpoints (generated by `tools/extract_endpoints.py`)
- [docs/SPA_CALLSITES.md](docs/SPA_CALLSITES.md): how the web app builds each request

## License

[MIT](LICENSE)
