# Mizito API: what the MCP uses (verified)

Hand-maintained. Every row here is wired into a tool. "live" = called against
the real API on the date shown; "offline" = body taken from the SPA call site
(docs/SPA_CALLSITES.md) and covered by tests/test_write_tools.py, but not yet
executed against the real workspace. The full list of 349+ endpoints the SPA
knows is generated in docs/ENDPOINTS.md.

## Transport

- `POST https://app.mizito.ir/api/<ns>/<method>`, JSON body (`{}` when none).
  SPA form: `invokeApi("ns.method", body)`; `.` becomes `/`.
- Only header that matters: `x-token: <session JWT>`. No workspace header, no
  client-version header (the SPA sends `origin`/`referer` implicitly; we copy them).
- Login (not used by the MCP; done by `tools/refresh-auth.sh` in a browser):
  `POST /capi/session/create {username, password: md5(pw)+"|"+sha256(pw), ...}`.
- The token has claims `{jti, iat}` only: no expiry. It dies on server-side
  revocation (logout elsewhere, password change).
- Errors:
  - HTTP 401 token revoked; 405 endpoint unknown; 400 body wrong or no permission.
    Bodies are HTML error pages with no detail.
  - HTTP 200 can still be a failure: `{error:"<i18n key>"}`, `{error:true,msg}`,
    `{success:false,msg|message}`, `{ok:false,errorMessage}`. `client.py`
    raises `AppError` for all of these.
  - `tasks/get` returns `{no_access_deleted:true}` for deleted tasks.
- Realtime (not used): socket.io, emits `authenticate {token}`, events `"m"`.

## Workspace

| endpoint | body | returns | status |
|---|---|---|---|
| `workspace/userId` | `{"regId":null}` | `uid, wid, phone, is_guest, remain_days, is_enterprise_plan, ...` | live 2026-11-12 |
| `workspace/name` | `{}` | bare JSON string | live |
| `workspace/getUsers` | `{}` | `{users:[{_id, first_name, last_name, username, role, status:{_, was_online}, work_status:{last_working_on_title, last_working_on_date}, deleted, invited, phone, email}]}` | live |
| `workspace/planInfo` | `{}` | `{used, volume, remain_days}` (bytes) | live |
| `workspace/switch` | `{"workspace_id": id}` | `{token}`: a NEW token bound to that workspace. The old token stays valid (verified live 2026-11-12) | live |
| `dashboard/getAllSummary` | `{}` | per workspace: `workspace_id, workspace_title, inbox, chat, task:{today,overdue,with_time,no_time}, meetings` | live |
| `dashboard/getAllBadges` | `{"only_badges":true}` | `{<wid>: {inbox, chat, task}}` (an object keyed by workspace id) | live (not wired) |
| `tasks/badge` | `{}` | `{today, count, total_count}` | live |

Roles: 0 member, 1 admin, 2 guest, 3 system/bot (e.g. «دستيار ميزيتو»). The
workspace owner is `planInfo.owner_id`, not a role.

## Projects

| endpoint | body | returns | status |
|---|---|---|---|
| `projects/getList` | `{}` | `{projects:[{_id, title, archived, deleted, owner, members_admin, kanban_boards:[{_id,title,color}], dialog, labels, is_advanced, advanced_*}]}` (archived included, flagged) | live |
| `projects/full` | `{"project_id": id}` | same + `members` | live |
| `projects/chatSummary` | `{"dialog": dlg, "project": id, "withBoards": true}` | counts + `boards:{<board_id>: counts}` | live |
| `projects/allSummary` | `{"with_details": true}` | `{summaries:[{project, name, total_tasks, me_completed, others_completed, me_overdue, me_today, me_remain_count, ...}]}` | live |
| `labels/getAll` | `{"type":"task"\|"project"}` | `{labels:[{_id,title,color,type,deleted}]}` | live |

Counts: done = `me_completed + others_completed`; open = `total_tasks - done`.
`allSummary[].is_archived` is NOT the archive flag (it is true for active
projects); use `getList[].archived`.

## Tasks: reads

A task is addressed by its **`access_token`** (JWT, embeds the session token:
secret), returned on every task in every list. `_id` alone is not accepted.

| endpoint | body | notes | status |
|---|---|---|---|
| `tasks/upcoming` | `{<scope>, "sort_type":"default", "filter": F, "from": offset}` | scope = `inbox:true` \| `outbox:true` \| `project_id` \| `label_id`. 25 rows per page; `from` = rows already loaded. `F.done_status` true -> done tasks only, false/null -> open only | live |
| `tasks/upcoming` (search) | `{"search":true, "search_str": s, "from": n, "filter": null \| {"done_status":true,"completed":true}}` | the SPA search page; includes archived projects | live |
| `tasks/getAll` | same scope, no `from` | the SPA's first page; not used (upcoming covers it) | live |
| `tasks/get` | `{"token": access_token}` | full task | live |
| `tasks/getComments` | `{"token"}` | `[{_id, comment, comment_owner, comment_at, mention, replied_comment_id, attachments, edited, deleted, can_edit}]` newest first | live |
| `tasks/history` | `{"token", "tid": _id}` | `[{user, date, changes:{from:{field:v}, to:{field:v}}}]` | live |
| `tasks/getSeenDetails` | `{"token"}` | `{created, first_user_seen, last_user_seen}` | live |

Filter object `F` (SPA default): `{owner, assignee, with_assignee, assignee_not_me,
check_overdue, overdue, check_with_time, with_time, with_progress, labels, board,
done_status, title_active, title}`. The MCP sends it only to pick open vs done;
all other filtering is local (tasks_api.apply_filters).

Task fields used: `_id, title, notes, owner, assignee[], responsible, project,
kanban_board, kanban_weight, labels[], checklist[{_id,title,checked,checked_by,checked_at}],
attachments[], completed, completed_at, completed_by[], progress, has_deadline,
deadline, has_deadline_start, deadline_start, alarm_at, alarm_options, is_repeat,
has_comments, last_comment, created_at, modified_at, dialog, dialog_message`.

## Tasks: writes (bodies from SPA call sites)

| tool | endpoint | body | status |
|---|---|---|---|
| create_task | `tasks/add` | `{title, notes, assignee:[uid]\|[null], project, kanban_board\|null, labels:[id], attachments:[], deleted:false, alarm_options:null, progress:0, weight:1, deadline_start:null, deadline:ISO\|null, comment:"", checklist:[{title,checked:false}], responsible:null, from_chat:false, from_minute:false, insert_to_chat_group:bool}` -> task (or array with `copy_users`) | live 2026-11-12 |
| update_task | `tasks/save` | the full object above built from the current task + `task_id`, `token`. No partial patch: always send everything | live 2026-11-12 |
| complete_task | `tasks/setCompleted` | `{token, completed:true, project}` | live 2026-11-12 |
| reopen_task | `tasks/setCompleted` | `{token, project, completed:false, progress, undone_user_id:<me>}` | live 2026-11-12 |
| set_task_progress | `tasks/updateProgress` | `{token, progress}` | live 2026-11-12 |
| set_task_deadline | `tasks/updateDeadline` | `{token, project, deadline:ISO\|null}`. Only meaningful when the project has `advanced_has_deadline`: elsewhere the value is stored but `has_deadline` stays false and the UI never shows it (live 2026-11-12). The tool refuses up front in such projects | live 2026-11-12 (stores; feature-enabled project not tested) |
| set_task_reminder | `tasks/snooze` | `{token, project, alarm_at:ISO\|null, update_repeat_base:false}`; sets `alarm_at` and `sort_date` | live 2026-11-12 |
| move_task | `tasks/setKanbanWeight` | `{token, projectId, kanbanBoardId, kanbanWeight}` | live 2026-11-12 |
| set_checklist_item | `tasks/setChecklistCheckedValue` | `{token, checklistId, checked}` | live 2026-11-12 |
| add_task_comment | `tasks/newComment` (dynamic name in SPA) | `{token, comment, attachments:[], mention:[uid], reply_id:<commentId>\|null}`; response ignored, re-read comments | live 2026-11-12 |
| edit_task_comment | `tasks/editComment` | `{token, commentId, newComment}` | live 2026-11-12 |
| delete_task_comment | `tasks/deleteComment` | `{token, commentId}` | live 2026-11-12 |
| delete_task | `tasks/removeTask` | `{token}` | live 2026-11-12 |
| restore_task | `tasks/removeTaskUndo` | `{token}` | live 2026-11-12 |
| bookmark_task | `tasks/toggleBookmark` | `{token, bookmarked}` | live 2026-11-12 |

**Due dates: reminder vs deadline (important).** The SPA groups tasks by
`sort_date` (= the reminder `alarm_at`, "زمان یادآوری", set via `tasks/snooze` or
`alarm_options` on add/save): overdue when its DAY is before today, today when
equal (`services.getRelativeTimeForTask`). `deadline` ("مهلت انجام") exists only in
projects with `advanced_has_deadline` and is shown only when `deadline_used`.
`alarm_options` on `tasks/add`: `{date:ISO, time:"HH:mm" (Tehran), repeat_type:"none",
has_custom_repeat:false}` (live 2026-11-12). `kanban_board:null` on add leaves the
task in no column (live), so create_task defaults to the first board.

Dates: JS `Date.toJSON()` = `YYYY-MM-DDTHH:MM:SS.mmmZ` UTC. Jalali is display
only. `has_deadline` and `alarm_at` are derived server-side, never sent.

## Chat

| endpoint | body | notes | status |
|---|---|---|---|
| `chat/getDialogs` | `{}` | `{dialogs:[{_id, title\|null, peer_user, is_group, is_project_group, project_entity, unread_count, messages_count, last_message_date, members, pinned_messages}], pin_dialogs}` | live |
| `chat/getHistory` | `{dialog, offset, limit?, filter?, filterSearch?, filterSender?}` | newest first; offset counts back from newest. SPA omits `limit` (server default 15); 200 honoured. `filter:"search"`+`filterSearch` or `filter:"sender"`+`filterSender` filter server-side | live |
| `chat/search` | `{mode:"chat", offset, search_str}` | global; 15 per page; each hit has `chat_full` (DMs titled "to_person") | live |
| `chat/getMessages` | `{mids:[id], dialog}` | specific messages (with `{}` it returns `[]`) | live 2026-11-12 |
| `chat/send` | `{dialog, message, reply_to?, mention?}` | returns bare `true`; verify by history. SPA sends a fuller local object (`_:"message", from, date, randomId, pending...`); the 4 fields suffice (dialog+message live 2026-09-01) | live 2026-11-12 (reply_to + mention too) |
| `chat/createDialog` | `{user: uid}` | opens/returns the DM dialog | live 2026-11-12 (group form; DM form offline) |
| `chat/updateSentMessage` | `{dialog, mid, newMessage}` | SPA allows only own, unseen messages | live 2026-11-12 |
| `chat/removeSentMessage` | `{dialog, mid}` | admins: `removeSentMessageAdmin` | live 2026-11-12. Deleted messages stay in history as `message:"."`, `deleted:true` |
| `chat/seen` | `{dialog, seen_count: messages_count}` | mark read up to a count | live 2026-11-12 |

Message fields: `_id, msg_index, from, date, message, media{_:...}, reply_to,
mention[], edited, deleted, _` ("message" or a service type). Task cards:
`media._ == "messageMediaTask"`, `media.task.{_id,title}`.

## Not wired yet (known bodies in SPA_CALLSITES.md)

- Files: upload `POST /api/content/upload` multipart (`upload`, `sendAsFile`),
  returns a media object; attach as `{media}` in tasks/comments, `media` in
  chat.send. Download: `content/getDownloadLink {content}` ->
  `https://cdn1.mizito.ir/cdn/dl/<s>?download=true`.
- Letters `inbox/*`, notes `notes/*`, minutes, polls, meetings, attendance.
- Pins: `chat/addPinMessage {dialog, message}`, `chat/pinDialog {dialog}`.
- Project admin (used once by hand for the test sandbox, 2026-11-12):
  `projects/add {title, color, members:[uid]}` -> `true`; the project gets NO
  boards and NO chat dialog. `projects/addKanbanBoard {projectId,
  kanbanBoard:[{title,color}]}` -> the boards with `_id`s. `projects/archive`
  -> **405** (gone). The SPA archives via `chat/archiveProject {dialog, project,
  withArchiveTasks}`, which returns 400 without a project chat dialog.
  `chat/deleteDialog {dialog}` -> `true` (live).
- `monitor/*` returned 400 for this account (2026-11-12).
