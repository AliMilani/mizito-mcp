# Mizito SPA call sites: request bodies (static analysis, 2026-11-12)


Source: the SPA bundle https://office.mizito.ir/a_.js (gzip without Content-Encoding;
`tools/extract_endpoints.py` shows how to fetch and decompress it). `@N` offsets refer to
the 2026-11-12 build (`app.css?v=1.0.4-591`) and drift with every Mizito release; search
for the quoted snippet instead (`tools/extract_endpoints.py` and plain grep are enough).
Offsets (`@N`) are Python character offsets into the decompressed bundle `a_dec.js` (not byte
offsets: the file has non-ASCII template literals, so `grep -b` offsets differ).

Minified variable names are local to each function. "SPA reads" means fields the client uses after the call.

Endpoints that appear **only in ternaries or variables**, so a plain `invokeApi("...")` scan misses them:
`tasks.newComment`, `formRequestTemplate.newComment`, `chat.removeSentMessage`,
`chat.removeSentMessageAdmin`, `content.getDownloadLink`, `session.logout`,
`attendance.getHistory`, `attendance.getOnlineHistory`, `monitor.attendanceUserHistory`,
`monitor.attendanceUserOnlineHistory`, `inbox.registerInLetter`, `inbox.registerOutLetter`,
`projectAutomation.add/update`, `projectAutomationWorkflow.getTaskWorkflow`,
`formRequestTemplate.getTaskWorkflow`, `projects.getGanttData`, `projects.ganttLoadMoreTasks`,
`projects.ganttSetTaskTimeline`, `projects.ganttMoveTask`, `projects.ganttTaskLinkAdd/Remove`,
`projects.ganttSaveGroup`, `projects.ganttRemoveGroup`, `projects.ganttGroupAddTasks`,
`monitor.projectsSummary`, `monitor.project`, `projects.monitor.*`.

---

## 1. tasks.add / tasks.save

### Builder: `AppTasksManager` function `T(t)` @2148807

```
o={title:t.title,notes:t.notes,assignee:t.assignee,project:t.project,kanban_board:t.kanban_board,labels:t.labels,attachments:t.attachments,deleted:t.deleted,alarm_options:t.alarm_options,progress:t.progress,weight:t.weight,deadline_start:t.deadline_start,deadline:t.deadline,comment:t.newComment,checklist:t.checklist,responsible:null,copy_users:t.copy_users,...
```

Pre-processing on a copy of the editor model `t`:
- `t.has_description` falsy → `notes = ""`.
- `project == "null"` (string) → `null`.
- No `copy_users` and `assignee[0] == -1` → `assignee[0] = myUserId`. The new-task default is `assignee:[-1]`.

| field | type | source / notes |
|---|---|---|
| `title` | string | Required. The client rejects an empty `trim()` (`please_fill_title_field`). |
| `notes` | string (rich text / HTML from the editor) | `""` when the description is hidden. |
| `assignee` | array of user `_id` strings | `[null]` when nobody is assigned (UI placeholder). `-1` means "me" and is replaced. More than one entry is allowed. |
| `project` | project `_id` string | Required. The client rejects a falsy value (`please_select_project`). |
| `kanban_board` | board `_id` string or `null` | Reset to `null` when the project changes. |
| `labels` | array of label `_id` (task-type labels) | Added through `showLabelSelector(e,"task",n.labels,...)`. |
| `attachments` | array of `{media:<upload response>}` | See item 8. `D.addFile` → `n.attachments.push({media:e})` and sets `view_as_entity=true`. |
| `deleted` | bool | Default `false`. `true` for draft tasks created from inbox or minute attachments (`newTask(a,{deleted:!0,from_attachment:!0})`, `l.deleted=!0,l.from_minute=!0`). |
| `alarm_options` | object or `null` | The reminder/schedule. `alarm_at` is **not** sent: the server derives it. Shape below. |
| `progress` | number | Default 0. |
| `weight` | number | Default 1. In advanced projects with `advanced_tasks_has_weight`, a missing value becomes 1 and a negative value becomes its absolute value. |
| `deadline_start` | JS `Date` or moment → JSON ISO-8601 UTC string, or `null` | Advanced Gantt projects. The client validates that the value is within ±10 years. |
| `deadline` | JS `Date` or moment → ISO-8601 UTC, or `null` | Gregorian. Jalali is display-only. Other code paths use `moment(...).toDate()`. |
| `comment` | string | The initial report/comment text (`t.newComment`). |
| `checklist` | array of `{title, checked}` | New items are `{checked:!1,title:o}`. Existing items carry `_id` (used by `setChecklistCheckedValue`). Templates map to `{title,checked:false}`. |
| `responsible` | `null`, `[]` or array of user ids | `null` unless `t.responsible_enabled`. When enabled it is `[]`. If there is more than one assignee, it is filled from `t.responsible_users` (a map `{uid:true}`) restricted to assignees, and an empty result is rejected client-side. |
| `copy_users` | array of user ids or undefined | Creates one copy of the task per user. The response is then an array. |
| `from_chat` | bool | |
| `from_minute` | bool | |
| `from_template` | template `_id` | Set when a task template is chosen. |
| `insert_to_customer_entity_dialog` | dialog `_id` | CRM customer dialog. If `copy_users.length>1 && t.customer_entity_dialog`, it is set to that value and `insert_to_chat_group=true`. |
| `insert_to_chat_group` | bool | `!t.from_attachment && t.insertToChatGroup`. The editor sets `insertToChatGroup=true` by default when the project has a chat dialog, the task is new and not from chat/minute (enterprise or non-trial plan). This posts a task card into the project chat. |

**No** `has_deadline`, `deadline_has_time`, `alarm_at` or `repeat` top-level fields are sent. `has_deadline`, `has_deadline_start`, `hide_deadline`, `alarm_at` and `is_repeat` appear only in responses.

`alarm_options` shape (schedule dialog `showSchedule` @2238317, final result `setFinalResult`):
`{date:<moment, hours/minutes applied from time>, time:"HH:mm", repeat_type, has_custom_repeat:bool, repeat_options:{...}}`
- `repeat_type` ∈ `none, daily, bidaily, bidailyEven, bidailyOdd, weekly, biweekly, triweekly, monthly, bimonthly, quarterly, firstMonthly, lastMonthly, yearly, custom` (keys of const `q`).
- `repeat_options` keys seen: `week_days` (map 0..6 → bool, 0 = Saturday), `monthly_interval` (1/2/3), `day_of_week` (0..6), `special_day_in_month` (`"firstDay"`, `"lastDay"`, a day number, or `null`), `interval`/`repeat_interval` (legacy, read only).
- Minimal form used by the app: `{date:<Date>,time:"08:00",repeat_type:"none",has_custom_repeat:!1}` (calendar `addTask` @~1968433, template select @2207242).

### tasks.add

```
if(!t._id)return r.invokeApi("tasks.add",o).then(o=>!angular.isArray(o)&&o.error?(r.showToastError(l(o.error)),s.reject()):(angular.isArray(o)||(o=[o]),angular.forEach(o,function(o){o.is_new=!0,...y(o),e.$broadcast("new_task",o)}),o))
```

- Response: a **task object, or an array of task objects** (array when `copy_users` is used). On failure: `{error:"<i18n key>"}`, shown with `showToastError(_(error))`.
- The SPA stores each task with `y(o)` (saveTask). That function uses `_id`, `access_token`, `title`, `assignee`, `project`, `kanban_board`, `deadline`, `deadline_start`, `has_deadline`, `has_deadline_start`, `alarm_at`, `alarm_options`, `completed`, `completed_at`, `completed_by`, `responsible`, `responsible_done_at`, `labels`, `dialog`, `dialog_message`, `created_at`, `notes`. The new task is therefore returned with `_id` and `access_token`. UNCERTAIN: the field list is inferred from `y()` reading these on any task, not from a response sample.
- A second `tasks.add` call site @~2382675 (cloning minute tasks) sends `h.copyTaskParams(f)` (function `M`, @~2185000): `{title,notes,assignee,responsible,project,kanban_board,labels,attachments,deleted:false,alarm_options,progress:0,weight,deadline_start,deadline,checklist:[{title,checked:false}],from_chat:false,from_minute:false,insert_to_chat_group:false}` plus `deleted=true,from_minute=true`.

### tasks.save

```
o.task_id=t._id,o.token=t.access_token;var a=P(t._id).rDateForGroup;return r.invokeApi("tasks.save",o).then(function(e){return e.error?(r.showToastError(l(e.error)),s.reject()):(e.rDateFrom=a,e.is_modified=!0,y(e),e)})
```

- Body: the same object `o` as tasks.add, plus `task_id` (task `_id`) and `token` (task `access_token`). The full object is always sent (no partial patch).
- Response: the updated task object, or `{error}`.

### Related: tasks.get @~2184100

```
if(e.startsWith("sl"))s={taskId:e};else if(a)s={token:a};else throw new Error("invalid task_id");t.show_as_form_request_preview&&(s.show_as_form_request_preview=!0);const n=await r.invokeApi("tasks.get",s);if(n.no_access_deleted)throw ...
```

- `{token}`: the cached `access_token`, or the id itself when `id.length>24`.
- `{taskId}`: for ids starting with `sl` (share links).
- Optional `show_as_form_request_preview:true`.
- Response: a task, or `{no_access_deleted:true}`.

### Related: tasks.upcoming @2210148

`loadUpcoming(e,t,o)` sends `{...e, from:o, filter:t}`.
- `from` is the number of results already loaded (an offset).
- Search sends `e={search:true,search_str}` or `{search:true,bookmarked:true}`, and `filter={done_status:true,completed:true}` for done tasks.
- Response: an array of tasks.

---

## 2. New task comment: the real endpoint is `tasks.newComment` (dynamic name)

@2177179, task editor `D.sendNewComment`:

```
r.invokeApi(n.is_form_request_for_user_view?"formRequestTemplate.newComment":"tasks.newComment",{token:n.access_token,comment:n.newComment,attachments:n.newCommentAttachments,mention:n.newCommentMention,reply_id:n.newCommentReply?n.newCommentReply._id:null})
```

| field | type | source |
|---|---|---|
| `token` | string | task `access_token` |
| `comment` | string (rich text/HTML from the emoji wysiwyg editor) | Required. The client rejects an empty string. |
| `attachments` | array of `{media:<upload response>}` | `D.addCommentFile` → `n.newCommentAttachments.push({media:e})` |
| `mention` | array of user ids | `D.showMentionSelector` (enterprise plan only). Replying to someone else's comment auto-sets `[comment_owner]`. |
| `reply_id` | comment `_id` or `null` | `D.replyComment` sets `n.newCommentReply=o` (the comment object). |

- The response body is not read. On success the SPA re-fetches with `tasks.getComments {token}`.
- Comments returned by `getComments` carry `_id`, `comment`, `attachments`, `mention` (array), `replied_comment_id`, `comment_owner`.
- `formRequestTemplate.newComment` takes the same body, for form-request tasks.
- When a new or edited task is saved with pending comment text, `sendNewComment()` runs before `tasks.add`/`tasks.save`. The `comment` field of tasks.add also carries `newComment`.

---

## 3. Chat (`AppImManager` @2064799, `AppPeersManager` ~@2049000, `ChatViewCtrl` ~@1729000)

### chat.send

The call is `function z(b){return h.invokeApi("chat.send",b)...}` (@2073795). It is triggered by `sendMessage:z` and by `$on("im_send_message",…)`.

Body = the full local message object built in `ChatViewCtrl` `H(a)` @~1729900:

```
const c={_:"message",_id:ja,local:ja,dialog:ga,out:!0,message:k,media:a.media,from:ia,date:Date.now(),reply_to:a.reply_to,mention:f,seen_count:1,randomId:ka,pending:!0};ja++,c.media&&(c.media.randomId=c.randomId),n.saveMessages([c]),ta(c),...,n.sendMessage(c)
```

| field | type | source |
|---|---|---|
| `_` | `"message"` | constant |
| `_id`, `local` | int | Local counter `ja` starting at 1. This is not a server id. |
| `dialog` | dialog `_id` | `ga = b.dialog._id` |
| `out` | `true` | |
| `message` | string (HTML from the wysiwyg editor, e.g. `<div>..</div>`) | `prepareMessageToSend` is the identity. For media other than photo/document/video (e.g. audio, poll, minute), text is forced to `""`. For photo/document/video the text acts as the caption. |
| `media` | object or undefined | The upload response (item 8) or a constructed media (below). Gets `media.randomId`. |
| `from` | my user id | `ia=k.getUserId()` |
| `date` | ms epoch number | `Date.now()` |
| `reply_to` | message `_id` (24-hex) or `null`/undefined | Set by `$broadcast("chat_reply_to_message",e)` only when `24===e?.length`. |
| `mention` | array of user ids or `null` | `showMentionSelector` (enterprise). |
| `seen_count` | `1` | |
| `randomId` | float | `n.getRandomId()` returns `E=Math.random()` once per session (not per message). |
| `pending` | `true` | |
| `show_sent_message` | `true` | Only in `shareDocument` (@~2061600). The client toasts on success. |

- The response is not read. The message is delivered back through the socket. On HTTP error the client broadcasts `chat_send_error` with `_id`.
- **Media constructed client-side** (in `media`):
  - `{_:"messageMediaPolling",polling:{anonymous,admin_visible,multiple_answers,quiz_mode,multiple_questions?,questions:[{subject,options:[{text}],description,correct_answer:-1}]}}`
  - `{_:"messageMediaMinute",minute:{subject,location,date,time:"HH:mm",notes,tasks:[],attachments:[{media}]}}` (the date is combined with the time into a Date)
  - `{_:"messageMediaMinuteAdvanced",minute:{subject,location,date,time,notes_pre,member_owner,member_executive,member_executive2,member_observer,members:[],members_other:[],notes,tasks:[],has_reminder:true,reminder_hours_before:3,project,state:0}}`
  - Also `messageMediaSticker`, `messageMediaAnimatedEmoji`, `messageMediaMultiEmoji`, `messageMediaCallLog`. Shapes not traced.
- **No forward and no reactions**: zero hits for `fwd_from`/`forward_from`/`reaction`. "Share document" re-sends the media through chat.send to a chosen dialog.

### chat.getHistory @2075160

```
getHistory:function d(a,b,c){function e(){var a=[],d=angular.extend({dialog:g,offset:b},c);return h.invokeApi("chat.getHistory",d).then(function(b){return u(b),angular.forEach(b,function(b){a.push(b.mid)}),{history:a}})}
```

- Body: `{dialog, offset, filter?, filterSearch?, filterSender?}`.
- `offset` is an index counted from the **newest** message: `0` is the latest page, and the next older page uses offset = messages already loaded. The page size is fixed at **15** server-side: the client treats `15==j` as "has more". Forward (newer) loading uses `offset = oldestLoadedOffset - 15`, clamped at ≥0.
- The filter comes from `ChatViewCtrl.W`: `b.filter&&(g.filter=b.filter,"search"==b.filter?g.filterSearch=b.filterSearchStr:"sender"==b.filter&&(g.filterSender=b.filterSender))`. So `filter` is `"search"` with `filterSearch:<string>`, or `"sender"` with `filterSender:<uid>`. Other filter values come from templates (UNCERTAIN).
- No `limit`, `max_id`, `min_id` or `before`.
- Before the first `getHistory` for a dialog, the client calls `chat.getChatView {dialog}` once. Its response is a dialog object passed to `saveDialog`.
- Response: an array of messages. The client sets `mid=id=_id`. Fields read: `_id`, `msg_index`, `from`, `date` (ms or ISO, fed to moment), `message` (HTML), `media` (`_` type plus payload), `action` (`_` service type), `reply_to`, `seen_count`, `seen`, `deleted`, `bookmarked`, `pending`.

### Every chat.* endpoint

| endpoint | body | notes |
|---|---|---|
| `chat.getDialogs` | none | Response `{dialogs:[…], pin_dialogs:[…]}`. Dialog fields used: `_id`, `dialog_type` (e.g. `"customer_entity"`), `is_group`, `is_channel`, `is_project_group`, `is_customer_entity`, `project_entity`, `customer_entity`, `peerId`, `peer_user`, `title`, `photo`, `unread_count`, `messages_count`, `history_unread_count`, `last_message_date`, `seen[]`, `kicked`, `labels`, `members`. |
| `chat.getChatView` | `{dialog}` | Dialog view object, before history. |
| `chat.getFullChat` | `{dialog}` | Profile: `_id`, `participants`, `group_admins`, `is_group`, `chat_photo`, `customer_entity`, `project_entity`, `settings` (`mute`). |
| `chat.getHistory` | `{dialog, offset, filter?, filterSearch?, filterSender?}` | See above. |
| `chat.getMessages` | `{mids:[msgId…], dialog}` | Batched lazy fetch of specific messages (100 ms debounce, grouped per dialog). Also used to refresh a poll: `{mids:[polling.message],dialog:polling.dialog}`. Returns an array of messages. |
| `chat.getMessageIndex` | `{dialog, mid}` | Returns `{msg_index, mid}`. Used to jump to a message. |
| `chat.getMessageByDate` | `{dialog, date}` | Jump to a date. Date format not traced (UNCERTAIN). |
| `chat.send` | message object | See above. |
| `chat.updateSentMessage` | `{dialog, mid, newMessage}` | Edit text. The client allows only own, text-only, unseen messages (`seen_count<=1`, `seen!==true`). For call-log messages: `{dialog, mid, log:{…,date:Date}}`. |
| `chat.removeSentMessage` / `chat.removeSentMessageAdmin` | `{dialog, mid}` | Delete for everyone. The admin variant is used when `getStatusDetails().can_delete_admin`. |
| `chat.getStatusDetails` | `{dialog, mid}` | Returns `{can_delete, can_delete_admin, can_delete_admin_, last_msg, …}` plus seen details. Called when a message's details menu opens. |
| `chat.seen` | `{dialog, seen_count:<dialog.messages_count>}` | Mark-as-read up to a count, not an id. |
| `chat.setTyping` | `{dialog}` | Throttled to once per 5 s. |
| `chat.search` | `{offset, mode, search_str?, bookmarked?}` | `mode` is `"chat"` or `"customers"`. `offset` = number of results already shown. Returns an array of messages (`_id` used). This is in-chat and global message search. |
| `chat.toggleBookmark` | `{dialog, mid, bookmarked:bool}` | |
| `chat.addPinMessage` / `chat.removePinMessage` | `{dialog, message:<mid>}` | Pin a message in a dialog. |
| `chat.pinDialog` | `{dialog}` | Returns `{success, pin_dialogs, msg}`. |
| `chat.unpinDialog` | `{dialog}` | Returns `{pin_dialogs}`. |
| `chat.createDialog` | DM: `{user:<uid>}`. Group: `{title, is_public:bool, is_project_group:bool, members:[uid], is_channel?:true, color?:"grey", labels?:[…], photo?:<photo _id>}` | Returns a dialog object (`_id` …). For a DM, the client first looks for a local existing DM (`s(b)`), else calls createDialog. The server returns the DM. |
| `chat.inviteUser` | `{dialog, user}` | |
| `chat.deleteUser` | `{dialog, user}` | |
| `chat.setAdmin` | `{dialog, user, isAdmin}` | |
| `chat.updateTitle` | `{dialog, title}` | |
| `chat.updatePhoto` | `{dialog, photo:<photo _id>}` | From `showUploaderWithCropper`. |
| `chat.removePhoto` | `{dialog}` | |
| `chat.deleteDialog` | `{dialog}` | |
| `chat.convertDialogToNotPublic` | `{dialog}` | |
| `chat.saveSettings` | `{dialog, mute:bool}` | |
| `chat.loadSettings` | none | Array of `{dialog, mute,…}`. |
| `chat.archiveProject` | `{dialog, project, withArchiveTasks}` | |
| `chat.fixDialogs` | `{dialog}` | |
| `chat.getDialogUnDoneTasksCount` | `{dialog}` | |
| `chat.convertMentionToUnProcessed` | `{dialog, mid}` | Mention inbox. |
| `chat.removeMentionMessage` | `{mid, dialog}` | |
| `chat.removeTaskSnoozeMessage` | `{mid, dialog, task_id}` | |

Realtime traffic uses socket.io (`io(Config.App.io_url,{transports:["websocket"],reconnection:false,path?})`). On connect the client emits `authenticate {token}`. Events arrive as `"m"` with `{type, body, workspace_id}` and are re-broadcast as Angular events.

---

## 4. inbox.* (internal letters / secretariat), `AppInboxManager` @~2138000

### inbox.getInbox

```
loadInbox:function(a,b,c){var d={mode:a,offset:b};return c&&(d=angular.extend(d,c)),g.invokeApi("inbox.getInbox",d)
```

- `mode` ∈ `"inbox"`, `"outbox"`, `"archived"`, `"secretariat-in"`, `"secretariat-out"`, `"search"`. Filter, label and global search all use `"search"`.
- `offset` = rows already loaded (`C+=c.length`).
- Extra keys, from `AppInboxController.v` @~1793777: `var d=b.filter_active?E:{};…selected_label_id&&(d.label_id=…),"outbox"==b.mode&&(d.outbox_mode=b.outbox_mode)`.
  - `label_id`
  - `outbox_mode` (`"all"` or others; values come from the template, UNCERTAIN)
  - When the filter panel is active, the filter object `E`: `{from:<uid>, to, read_unread_status:-1|…, has_attach_status:-1|…, search_str, labels:[], dialog:<customer dialog id>, date_range, only_secretariat:bool, secretariat_letter_type:0|1|2, secretariat_register_from, secretariat_register_to, secretariat_sec_num}`. Secretariat letter type 1 = incoming, 2 = outgoing.
  - Global search: `{search_str}` or `{bookmarked:true}`.
  - CRM: `{dialog}` or `{only_secretariat:true,secretariat_letter_type:1|2,dialog}`.
- There is no `archived` flag. Archive is a mode.
- Response: an array of rows with `thread`, `_id`, `send_date`, `unread`, `count`, `ischild`, ….

### Other inbox endpoints

- `inbox.expandInboxRow {thread, mode}`: child rows of a thread.
- `inbox.getHistory {thread}`: returns a thread object with `thread`, `_id`, `from`, `to:[{user,unread}]`, `receivers`, `subject`, `content`, `attachments`, `messages:[…]`, `labels`, `dialogs`, `reply_to`, `send_date`. Guests then call `inbox.getMessageLabels {thread}`.
- `inbox.send`: built in `showCompose` @~2140000:
  - Default object: `var e={to:[],subject:"",content:"",attachments:[],tasks_insert_to_chat_groups:[],labels:[]}`, plus for a reply `e.reply_to=b.reply_to,e.thread=b.thread`.
  - On send, `to` (user objects) is mapped to an array of `_id`.
  - Body: `{to:[uid], subject, content:<HTML>, attachments:[<upload media> | {_:"messageMediaTask",task}], tasks_insert_to_chat_groups:[taskId], labels:[labelId], reply_to?:<msgId>, thread?:<threadId>}`.
  - `workspace.sendContactUsage {user_id:[uids]}` is called before it.
  - Task attachments are created first as `tasks.add` with `deleted:true, from_attachment:true`.
- `inbox.seen {thread}`: mark read.
- `inbox.getSeenDetails {thread, msgId}`
- `inbox.archive {thread}` / `inbox.unArchive {thread}`. In outbox mode these become `inbox.archive.sender` / `inbox.unArchive.sender`.
- `inbox.deleteMessage {mid, isDeleteThread:bool}`: returns `{ok, deletedThread, error, errorMessage}`.
- `inbox.toggleBookmark {thread, bookmarked}`
- `inbox.changeMessageLabels {thread, labels}`
- `inbox.changeMessageDialogs {thread, dialogs}`: attach CRM customers.
- `inbox.getMessageDialogs {thread}`
- `inbox.setTyping {thread}`
- `inbox.getLastSecretariatStatus`: no body. Returns `{next_sec_number,…}`.
- `inbox.registerOutLetter` / `inbox.registerInLetter {thread, letterOptions}`: secretariat registration. Returns `{success,msg}`.

---

## 5. notes / meeting / minute / polling / attendance

**notes.\*** (Keep-style personal notes):
- `notes.getAll {label_id, deleted:bool, archived:bool}`: list.
- `notes.create <note>`: create. Base object `{title:"",note:"",photo:null,color:"white",checklist:[],labels:[]}`. Color ∈ white, red, orange, yellow, grey, blue, cyan, green.
- `notes.update <note incl. _id>`: full object (copy of the client note).
- `notes.updatePinState {pinned, noteId}`
- `notes.setColor {note_id, color}`
- `notes.setLabels {note_id, labels}`
- `notes.setChecklistValue {note_id, check_index, checked}`
- `notes.archiveNote {note_id, archived}`
- `notes.deleteNote {note_id, deleted}`: soft delete and undelete.

**meeting.\*** (in-app audio/video calls):
- `meeting.create {dialog, members, tab:<browserTabId>}`
- `meeting.get {meeting, socket:<socket.io id>, tab}`
- `meeting.ping {meeting, socket, tab}`
- `meeting.endCall {meeting, socket, tab}`
- `meeting.reject {meeting}`
- `meeting.broadcastMeetingMessage {meeting, message}`

**minute.\*** (simple meeting minutes, posted as a chat message `messageMediaMinute`):
- Create through `chat.send` media.
- `minute.update {dialog, minute}`: the minute's `date` is combined with `time`.
- `minute.history {minute_id}`
- `minute.getTemplates`
- `minute.getTemplate {template}`
- `minute.setMinuteAsTemplate <d>` (body not traced)

**minuteAdvanced.\*** (formal minutes with signatures and SMS):
- `get {minuteId}`
- `update {minute, dialog, project}`
- `getComments {minuteId}`
- `newComment {minuteId, comment, attachments}`
- `editComment {minuteId, commentId, newComment}`
- `deleteComment {minuteId, commentId}`
- `sendDraft {minuteId, dialog, project}`
- `sendForSign {minuteId, dialog, project}`
- `sign {mid, dialog, minuteId}`
- `sendSms {minuteId, dialog, project, template}`
- `getSmsHistory {minuteId}`
- `getTemplates`
- `setMinuteAsTemplate {minuteId, isActive}`

**polling.\*** (polls/quizzes in chat; created via `chat.send` media `messageMediaPolling`):
- `setPollingVote {dialog, polling, my_votes}`: `my_votes` is a map of question `_id` → [option `_id`], per `n.my_answers[i._id].push(d._id)`.
- `retractVote {dialog, polling}`
- `stopPolling {dialog, polling}`
- `printPollingResults {dialog, polling}`: returns HTML.
- `getTemplates`
- `setPollingAsTemplate <d>`
- Errors come back as `{error, msg}`.

**attendance.\*** (manual clock-in/out and online-time log):
- `attendance.start` (no body)
- `attendance.stop` (no body)
- `attendance.delete {attendanceId}`
- `attendance.getHistory {fromIndex, userId?}`: manual log, paged by index.
- `attendance.getOnlineHistory {fromDate:ISO, toDate:ISO, userId?}`: 14-day windows. Returns an array, or `{rows, legacy_uncertain_before}`.
- Monitoring variants: `monitor.attendanceUserHistory`, `monitor.attendanceUserOnlineHistory`.

---

## 6. projects

- `projects.full {project_id}`: full project object, stored in the project cache. UNCERTAIN: field list inferred from usage. Fields seen: `_id`, `title`, `color`, `members`, `members_admin`, `kanban_boards`, `dialog`, `is_advanced`, `advanced_*` flags.
- `projects.get {projectId, token}`: `token` is a **task access_token**. Used to read a project you are not a member of, through a task you can see.
- `projects.getList`: no body. Returns `{projects:[…], project_status:[{project_id, order}]}`.
- `projects.getListAdmin`: no body. Returns an array of projects the user administers.
- `projects.getListAdminForMember {user}`: returns `{projects}`.
- `projects.history {project_id}`: an array of history entries `{data:{…project snapshot}}`.
- `projects.getProjectFiles`, @1820517: `var a={project:o,filterType:b.filterType,fromIndex:r};return"filename"==b.filterType&&(a.filename=b.searchFilename),j.invokeApi("projects.getProjectFiles",a)`
  - Body: `{project, filterType:null|"filename"|…, fromIndex:<count loaded>, filename?}`.
  - Response: an array of `{_id, task_id, attach_at, attachment:<media>}`.
  - Page size: `Config.App.tasks_page_size`.
  - Other `filterType` values come from the template (UNCERTAIN).
- `projects.add {title, color, members:[uid]}` and `projects.save {project_id, title, color, members}`
- `projects.addKanbanBoard {projectId, kanbanBoard:[{title, color}, …]}`: always an **array** (`f=[f]`, or a template that expands to several boards).
  - Color ∈ green2, yellow, orange, green, blue, light-blue, brown, red-dark, purple.
  - Templates: kanban, weekday, single_team (one board per member), departments, custom.
  - The added boards arrive through socket event `projects_kanban_board_added {project, boards}`.
- `projects.updateKanbanBoard {projectId, kanbanBoardId, kanbanBoard:<board object minus tasks>}`: fields `_id`, `title`, `color` (the edited copy of the board).
- `projects.removeKanbanBoard {projectId, boardId}`
- `projects.setKanbanBoardOrder {projectId, boardId, oldPosition, newPosition}`
- Gantt: `projects.ganttSetTaskTimeline {project, tasks:[{_id,start_date,finish_date,alarm_at}]}`, plus the other gantt* calls (bodies not traced).

---

## 7. workspace.* / dashboard

- **Workspace switching is token-based. There is no workspace header.** @2350684:
  `a.invokeApi("workspace.switch",{workspace_id:b}).then(function(b){a.setToken(b.token),e.go("workspace_switching")})`
  - The response `{token}` replaces `x-token` (stored in sessionStorage, and in localStorage unless `is_afta`).
  - Then `workspace.userId {regId}` returns the session: `uid`, `wid`, `phone`, `workspaces[]` (`_id`, `title`), `verified`, `plan_*`, `remain_days`, `has_no_workspace`, `access_owner`, `options`, `do_not_disturb_until`, `wallpaper`, ….
- Roles (`user.role`):
  - `0` = member
  - `1` = admin (`access_admin=1==e.role`)
  - `2` = guest (`access_is_guest=2==e.role`; `inviteMember is_guest` sets role 2)
  - `3` = special/system account, excluded from user lists and always visible to guests (UNCERTAIN: likely a bot or support user)
  - The owner is `planInfo.owner_id`, not a role.
  - Custom display role names: `workspace_role_name`, behind `access_workspace_role_names`.
- `workspace.getUsers`: returns `{users, user_status}`.
- `workspace.name`: returns the name string.
- `workspace.getPermissions`
- `workspace.updateUserPermission {user, permission, access}`
- `workspace.changeRole {user_id, role}`: returns `{msg}` on refusal.
- `workspace.inviteMember {name, email_phone, is_guest}`: returns `{success, user, message}`.
- `workspace.removeMember {member_id}` / `workspace.reJoinMember {member_id}`
- `workspace.planInfo {details}`: returns `{volume, used, owner_id, users, guest_count, members_count, …}`.
- `workspace.add {name, members:[{name,email_phone}]}`
- `workspace.updateTitle {title}`
- `workspace.setWorkspaceSettings {title, value}`
- `workspace.changeOwner {owner, pinCode, password}`
- `workspace.sendContactUsage {user_id}`
- `workspace.getSettingsHistory {before, filters}`
- `workspace.updateWorkspaceRoleName {user_id, workspaceRoleName}`
- `dashboard.getAllBadges {only_badges:true}`: returns an array `[{workspace_id, chat, inbox, task}]`. The client sums them into `unread_count` per workspace.
- `dashboard.getAllSummary`: no body. Returns an array per workspace (`workspace_id`, `unread_count`, `meetings`, …).
- `dashboard.getAllWorkspacesUsers`: returns `[{workspace_id, users}]`.
- `dashboard.notifySeen`

---

## 8. Upload, attaching, and CDN URLs

### Upload: `AppFilesManager` function `m(a,c,h)` @~2116000

```
var j=new FormData;j.append("upload",a),f.maxWidthHeight&&j.append("maxWidthHeight",f.maxWidthHeight),j.append("sendAsFile",f.sendAsFile?"true":"false");var k=$.ajax({url:e.getUploadPath(),type:"POST",data:j,processData:!1,contentType:!1,headers:{"x-token":e.getToken()},
```

- `POST Config.App.api_url + "/api/content/upload"` (`getUploadPath`). Multipart form data, one file per request.
- Fields:
  - `upload`: the file
  - `maxWidthHeight`: optional. `1000` for profile or crop photos.
  - `sendAsFile`: `"true"` or `"false"`. `"true"` keeps an image as a document. Non-images are always `"true"` (`f.sendAsFile=!a.image||!!d`).
- Header: `x-token`.
- Limits: at most 10 files at once; total size ≤ `Config.App.max_upload_size` MB.
- Response: a **media object**, `{_:"messageMediaPhoto"|"messageMediaDocument"|"messageMediaVideo"|"messageMediaAudio", photo|document|video|audio:{…}}`.
  - Photo: `photo._id`, `photo.photo_large.{content,content_key}`, `photo.photo_medium.{content,content_key}`.
  - Document: `document.{_id,name,content}`.
  - Audio: `audio.{content,content_key,name}`.
  - Errors: `{error:true, msg:"<i18n key>"}`.
- Crop flow: `content.getCroppedPhoto {base:<photo._id>, points:{top,left,width,height}}` returns `{success, photo}`.

### Attaching the upload

| target | how |
|---|---|
| Task | `attachments: [{media:<resp>}]` in tasks.add/save |
| Task comment | `attachments: [{media:<resp>}]` in tasks.newComment |
| Chat message | `chat.send` with `media:<resp>` directly (plus optional caption text in `message`) |
| Inbox letter | `attachments: [<resp>]` directly (no `{media}` wrapper) |
| Deal / simple minute | `attachments: [{media:<resp>}]` |

The client adds `view_as_entity:true` to the media before sending.

### CDN URLs (`services` @2867778)

```
function te(e){return Config.App.cdn_url+"/cdn/"+e}function oe(e){return Config.App.cdn_url+"/cdn/dl/"+e}
```

- Inline view: `cdn_url + "/cdn/" + <media.*.content>`, fetched with header `x-token` (`_e` → `fetch(d,{mode:"cors",headers:{"x-token":Te}})`). The `content` string inside the media object is the JWT path segment, so no endpoint call is needed.
- Download link: `content.getDownloadLink {content:<media.*.content>}` (`v("content.getDownloadLink",{content:e}).then(e=>oe(e))`). The response is a string, used as `cdn_url + "/cdn/dl/" + resp`, and the client appends `?download=true`. On Safari: `te(content)+"?safari=1&download=true"`.
- Dedicated logo: `cdn_url + "/cdn/de/logo/" + id`.

---

## 9. Search

There is no dedicated global search endpoint. `AppSearchController` @1825417 fans out:
- **Tasks**: `tasks.upcoming {search:true, search_str | bookmarked:true, from:<offset>, filter:null}`. Done tasks use `filter:{done_status:true,completed:true}`. The "show more" path for done tasks passes `filter=null`, which looks like a client bug.
- **Inbox**: `inbox.getInbox {mode:"search", offset, search_str | bookmarked:true}`
- **Chat**: `chat.search {mode:"chat", offset, search_str?, bookmarked?}`
- **Customers' chats**: `chat.search {mode:"customers", …}`
- **In one dialog**: `chat.getHistory {dialog, offset, filter:"search", filterSearch}`
- **Project files by name**: `projects.getProjectFiles {filterType:"filename", filename}`
- Others: `support.searchContent` (support admin), `fix/*/getAll {filter}` (admin repair tools).
- Projects: UNCERTAIN, probably filtered client-side from `projects.getList` (`rSearchableTitle`).

---

## 10. invokeApi: headers and errors (`services` factory `v(e,a,n)` @~2858500)

```
var r=function(e){i.reject(e)},d={"x-token":Te};return"contentType"in n&&(d["Content-Type"]=n.contentType),o({method:"POST",url:Config.App.api_url+"/api/"+e.replaceAll(".","/"),data:a,headers:d}).then(function(e){i.resolve(e.data)},function(e){e.data&&e.data.db_error&&ce("خطا در برقراری ارتباط ..."),401==e.status&&(z(),c.go("login.login")),r(e)})
```

- Every call is `POST`, with the body as JSON (Angular `$http` default `application/json`; empty `{}` when no body).
- **The only custom header is `x-token`** (the session token for the current workspace).
  - There is no client-version or workspace header.
  - There are no `$http` interceptors and no `defaults.headers`.
  - `n.layer=Config.App.api_layer` is set on the options object but **not sent**.
  - An optional `opts.contentType` overrides `Content-Type`.
- If no token exists, the call rejects and the client routes to logout.
- **No-session calls** (`{no_session:true}`: session.create/register/forgot/userInfo/…) go to `/capi/<ns>/<method>` with `x-token: <common_token>` when one is stored. The response may carry `common_token`, which is saved.
- Login: `POST /capi/session/create {username, password: md5(pw)+"|"+sha256(pw) (raw for AD/SSO), loginCode, twoStepMethod, twoStepChallenge, twoStepRecoveryToken, regId}`. On `status` 1 or 5 the response `token` is stored. A `blocked` flag shows a "restricted by admin" dialog.
- Logout: `session.logout {regId?}`.
- **Error signalling**:
  - HTTP 401: token cleared, redirect to `login.login`.
  - Non-2xx with `data.db_error`: generic toast "خطا در برقراری ارتباط ..." ("connection error"). The promise rejects with the HTTP response.
  - Application errors arrive in HTTP 200 bodies, with no single convention:
    - `{error:"<i18n key>"}` (tasks.add/save → `showToastError(_(error))`)
    - `{error:true, msg:"<i18n key>"}` (upload, polling)
    - `{success:false, msg|message}` (pinDialog, reJoinMember, registerLetter, inviteMember)
    - `{message}` (planInfo-related, inviteMember)
    - `{ok:false, error, errorMessage}` (inbox.deleteMessage)
    - `{no_access_deleted:true}` (tasks.get)
  - Counts found: `.message` 136×, `.error` 119×, `.success` 58×, `.msg` 47×.
