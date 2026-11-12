# Mizito API endpoint catalog (generated)

Generated 2026-11-12 by `tools/extract_endpoints.py` from the SPA bundle.
349 endpoints in 28 namespaces. All are `POST /api/<endpoint>`
with a JSON body. This lists what the SPA *calls*; whether an endpoint is
wired into the MCP, and its verified body, is in docs/API.md.

Body column = the literal argument text at the call site (minified).
`!0` = true, `!1` = false. A bare letter means the body is built elsewhere.

## attendance (3)

| endpoint | body at call site |
|---|---|
| `attendance/delete` | `{attendanceId:d._id}` |
| `attendance/start` | `{}` |
| `attendance/stop` | `{}` |

## chat (35)

| endpoint | body at call site |
|---|---|
| `chat/addPinMessage` | `{dialog:b,message:c}` |
| `chat/archiveProject` | `{dialog:e,project:b,withArchiveTasks:d}` |
| `chat/convertDialogToNotPublic` | `{dialog:k}` |
| `chat/convertMentionToUnProcessed` | `{dialog:i.dialog,mid:d}` |
| `chat/createDialog` | `b` ; `{user:b}` |
| `chat/deleteDialog` | `{dialog:k}` |
| `chat/deleteUser` | `{dialog:k,user:h}` |
| `chat/fixDialogs` | `{dialog:a._id}` |
| `chat/getChatView` | `{dialog:g}` |
| `chat/getDialogUnDoneTasksCount` | `{dialog:g._id}` |
| `chat/getDialogs` | `{}` |
| `chat/getFullChat` | `{dialog:d}` |
| `chat/getHistory` | `d` |
| `chat/getMessageByDate` | `{dialog:a,date:b}` |
| `chat/getMessageIndex` | `{dialog:a,mid:b}` |
| `chat/getMessages` | `{mids:b,dialog:c}` ; `{mids:[n.media.polling.message],dialog:n.media.polling.dialog}` |
| `chat/getStatusDetails` | `{dialog:i.dialog,mid:d}` |
| `chat/inviteUser` | `{dialog:k,user:a._id}` |
| `chat/loadSettings` | `{}` |
| `chat/pinDialog` | `{dialog:b}` |
| `chat/removeMentionMessage` | `{mid:b,dialog:a}` |
| `chat/removePhoto` | `{dialog:k}` |
| `chat/removePinMessage` | `{dialog:b,message:c}` |
| `chat/removeTaskSnoozeMessage` | `{mid:c,dialog:b,task_id:d._id}` |
| `chat/saveSettings` | `{dialog:k,mute:!a}` |
| `chat/search` | `f` |
| `chat/seen` | `{dialog:c._id,seen_count:c.messages_count}` |
| `chat/send` | `b` |
| `chat/setAdmin` | `{dialog:k,user:f,isAdmin:d}` |
| `chat/setTyping` | `{dialog:ga}` |
| `chat/toggleBookmark` | `{dialog:a,mid:c,bookmarked:d}` |
| `chat/unpinDialog` | `{dialog:a}` |
| `chat/updatePhoto` | `{dialog:k,photo:a._id}` |
| `chat/updateSentMessage` | `{dialog:ga,mid:c,newMessage:e}` ; `{dialog:e.dialogId,mid:e.messageId,log:f}` |
| `chat/updateTitle` | `{dialog:k,title:a}` |

## content (1)

| endpoint | body at call site |
|---|---|
| `content/getCroppedPhoto` | `{base:b._id,points:a}` |

## customer (7)

| endpoint | body at call site |
|---|---|
| `customer/add` | `d` |
| `customer/history` | `{customer_id:d._id}` |
| `customer/import` | `{contentId:j,members:a.members,labelAssign:a.labelAssign,fieldIndexes:a.fieldIndexes}` |
| `customer/importPrepare` | `{contentId:c}` |
| `customer/suggestParticipants` | `{}` |
| `customer/update` | `d` |
| `customer/updateLabel` | `{customer_id:a,is_add:b,label_id:c}` |

## dashboard (10)

| endpoint | body at call site |
|---|---|
| `dashboard/acceptInviteRequest` | `{workspace:b.workspace}` |
| `dashboard/cancelInviteRequest` | `{workspace:a.workspace}` |
| `dashboard/checkWhatsNew` | `{}` |
| `dashboard/demoGuide` | `{}` |
| `dashboard/getAllBadges` | `{only_badges:!0}` |
| `dashboard/getAllSummary` | `{}` |
| `dashboard/getAllWorkspacesUsers` | `{}` |
| `dashboard/getPending` | `{}` |
| `dashboard/notifySeen` | `{}` |
| `dashboard/setWhatsNewSeen` | `{}` |

## deal (7)

| endpoint | body at call site |
|---|---|
| `deal/add` | `c` |
| `deal/getAll` | `a` |
| `deal/getCustomerDeals` | `{customer:a}` |
| `deal/getReportStatistics` | `{filter:a}` |
| `deal/history` | `{deal_id:c._id}` |
| `deal/info` | `{deal_id:b}` |
| `deal/update` | `c` |

## device (1)

| endpoint | body at call site |
|---|---|
| `device/register` | `{subscription:e,iOS:!0,regId:c,deviceName:"iPhone",deviceId:d,versionCode:1,versionName:1},{no_session:!0}` |

## feedback (2)

| endpoint | body at call site |
|---|---|
| `feedback/checkRequireParticipant` | `{}` |
| `feedback/sendFeedback` | `{feedback:g}` ; `{feedback:{no_answer:!0}}` |

## fix (13)

| endpoint | body at call site |
|---|---|
| `fix/changeUser/changeChatGroups` | `{fromUser:e.from,toUser:e.to}` |
| `fix/changeUser/changeCustomers` | `{fromUser:e.from,toUser:e.to}` |
| `fix/changeUser/changeTasks` | `{fromUser:e.from,toUser:e.to}` |
| `fix/changeUser/history` | `{}` |
| `fix/chatGroups/getAll` | `{filter:a.filter}` |
| `fix/chatGroups/getMembers` | `{dialog:e._id}` |
| `fix/chatGroups/grantAccess` | `{dialogIds:[e._id],userId:c,access:!1}` ; `{dialogIds:e,users:f.map(a=>a._id),access:c}` |
| `fix/customer/getAll` | `{filter:a.filter}` |
| `fix/customer/getMembers` | `{customer:e._id}` |
| `fix/customer/grantAccess` | `{customerIds:[e._id],userId:c,access:!1}` ; `{customerIds:e,users:f.map(a=>a._id),access:c}` |
| `fix/projects/getAll` | `{filter:a.filter}` |
| `fix/projects/getMembers` | `{project:f._id}` |
| `fix/projects/grantAccess` | `{projectIds:[b],users:g,access:!1}` ; `{projectIds:[f._id],userId:c,access:!1}` |

## formRequestTemplate (8)

| endpoint | body at call site |
|---|---|
| `formRequestTemplate/add` | `{projectId:a,form:b}` |
| `formRequestTemplate/getAll` | `{projectId:a}` ; `{projectId:f}` |
| `formRequestTemplate/getAllForms` | `{}` |
| `formRequestTemplate/getHistory` | `{projectId:c,templateId:e._id}` |
| `formRequestTemplate/remove` | `{projectId:c,formId:q._id}` |
| `formRequestTemplate/save` | `{projectId:a,form:b}` |
| `formRequestTemplate/submit` | `{templateId:b,custom_params_values:h}` |
| `formRequestTemplate/view` | `{templateId:b}` |

## inbox (18)

| endpoint | body at call site |
|---|---|
| `inbox/archive` | `{thread:b}` |
| `inbox/archive/sender` | `{thread:b}` |
| `inbox/changeMessageDialogs` | `{thread:b.thread,dialogs:e}` |
| `inbox/changeMessageLabels` | `{thread:b.thread,labels:e}` |
| `inbox/deleteMessage` | `{mid:d,isDeleteThread:e}` |
| `inbox/expandInboxRow` | `{thread:a,mode:b}` |
| `inbox/getHistory` | `{thread:b}` |
| `inbox/getInbox` | `d` |
| `inbox/getLastSecretariatStatus` | `{}` |
| `inbox/getMessageDialogs` | `{thread:b.currentInboxMessage.thread}` |
| `inbox/getMessageLabels` | `{thread:b}` |
| `inbox/getSeenDetails` | `{thread:b,msgId:c}` |
| `inbox/seen` | `{thread:a}` |
| `inbox/send` | `b` |
| `inbox/setTyping` | `{thread:e.thread}` |
| `inbox/toggleBookmark` | `{thread:a.thread,bookmarked:b}` |
| `inbox/unArchive` | `{thread:b}` |
| `inbox/unArchive/sender` | `{thread:b}` |

## labels (6)

| endpoint | body at call site |
|---|---|
| `labels/add` | `{title:a.title,color:a.color,type:a.type}` |
| `labels/delete` | `{label_id:c._id,label_type:c.type}` |
| `labels/getAll` | `{type:c}` |
| `labels/history` | `{label_id:b.editLabel._id}` |
| `labels/save` | `{label_id:a._id,type:a.type,title:a.title,color:a.color}` |
| `labels/sendUsage` | `{label_id:b,type:a}` |

## meeting (6)

| endpoint | body at call site |
|---|---|
| `meeting/broadcastMeetingMessage` | `{meeting:a,message:c}` |
| `meeting/create` | `{dialog:a,members:b,tab:f.getBrowserTabId()}` |
| `meeting/endCall` | `{meeting:r,socket:h.getSocketId(),tab:h.getBrowserTabId()}` ; `{meeting:d.meeting_id,socket:c.getSocketId(),tab:c.getBrowserTabId()}` |
| `meeting/get` | `{meeting:r,socket:h.getSocketId(),tab:h.getBrowserTabId()}` |
| `meeting/ping` | `{meeting:a,socket:b,tab:f.getBrowserTabId()}` |
| `meeting/reject` | `{meeting:a}` |

## minute (5)

| endpoint | body at call site |
|---|---|
| `minute/getTemplate` | `{template:a._id}` ; `{template:c._id}` |
| `minute/getTemplates` | `{}` |
| `minute/history` | `{minute_id:g._id}` |
| `minute/setMinuteAsTemplate` | `d` |
| `minute/update` | `{dialog:g.dialog,minute:f}` |

## minuteAdvanced (13)

| endpoint | body at call site |
|---|---|
| `minuteAdvanced/deleteComment` | `{minuteId:e._id,commentId:b._id}` |
| `minuteAdvanced/editComment` | `{minuteId:e._id,commentId:c._id,newComment:a.newMessage}` |
| `minuteAdvanced/get` | `{minuteId:b}` |
| `minuteAdvanced/getComments` | `{minuteId:e._id}` |
| `minuteAdvanced/getSmsHistory` | `{minuteId:e._id}` |
| `minuteAdvanced/getTemplates` | `{}` |
| `minuteAdvanced/newComment` | `{minuteId:e._id,comment:e.newComment,attachments:e.newCommentFiles}` |
| `minuteAdvanced/sendDraft` | `{minuteId:e._id,dialog:e.dialog,project:e.project}` |
| `minuteAdvanced/sendForSign` | `{minuteId:e._id,dialog:e.dialog,project:e.project}` |
| `minuteAdvanced/sendSms` | `{minuteId:e._id,dialog:e.dialog,project:e.project,template:e.newSmsTemplate}` |
| `minuteAdvanced/setMinuteAsTemplate` | `{minuteId:e._id,isActive:b}` |
| `minuteAdvanced/sign` | `{mid:c,dialog:b,minuteId:d}` |
| `minuteAdvanced/update` | `{minute:f,dialog:e.dialog,project:e.project}` |

## monitor (12)

| endpoint | body at call site |
|---|---|
| `monitor/chart/chatMessages` | `{}` ; `{uid:g}` |
| `monitor/chart/customers` | `{}` ; `{uid:g}` |
| `monitor/chart/getPast30DoneTasksPercents` | `{}` |
| `monitor/chart/inboxMessages` | `{}` ; `{uid:g}` |
| `monitor/chart/notes` | `{}` ; `{uid:g}` |
| `monitor/chart/tasksAssigned` | `{uid:g}` ; `{uid:g,not_owner:!0}` |
| `monitor/chart/tasksCreated` | `{}` ; `{uid:g}` |
| `monitor/chart/tasksDone` | `{}` ; `{uid:g}` |
| `monitor/customers` | `{filter:d}` |
| `monitor/minutes` | `{filter:i}` |
| `monitor/user` | `{uid:g}` |
| `monitor/workspace` | `{}` |

## notes (9)

| endpoint | body at call site |
|---|---|
| `notes/archiveNote` | `{note_id:b._id,archived:!1}` ; `{note_id:a._id,archived:!1}` |
| `notes/create` | `b` |
| `notes/deleteNote` | `{note_id:b._id,deleted:!0}` ; `{note_id:a._id,deleted:!1}` |
| `notes/getAll` | `a` |
| `notes/setChecklistValue` | `{note_id:a._id,check_index:b,checked:a.checklist[b].checked}` |
| `notes/setColor` | `{note_id:b._id,color:a}` |
| `notes/setLabels` | `{note_id:b._id,labels:b.labels}` |
| `notes/update` | `b` |
| `notes/updatePinState` | `{pinned:a.pinned,noteId:a._id}` |

## payment (14)

| endpoint | body at call site |
|---|---|
| `payment/add` | `{payment:f}` |
| `payment/checkDiscountCode` | `{discountCode:c.discount_code.trim(),planId:c._id}` |
| `payment/createUpgradeInvoice` | `{plan_id:f._id,discount_code:f.discount_code?f.discount_code.trim():null,request_enterprise:g,is_online:h}` |
| `payment/getAllPayments` | `a` |
| `payment/getCustomerPayments` | `{customer:a}` |
| `payment/getInvoice` | `{invoice:c}` ; `{invoice:k._id}` |
| `payment/getReportDetails` | `a` |
| `payment/getReportStatistics` | `{filter:a}` |
| `payment/history` | `{payment_id:f._id}` |
| `payment/info` | `{payment_id:b}` |
| `payment/requestTrial` | `{planId:c._id,request_enterprise:b.request_type.request_enterprise}` |
| `payment/setWantToPay` | `{invoice:k._id}` |
| `payment/update` | `f` |
| `payment/uploadLastWaitingInvoicePayment` | `{invoice:b.planInfo.last_waiting_invoice_id,photo:a.photo}` |

## polling (6)

| endpoint | body at call site |
|---|---|
| `polling/getTemplates` | `{}` |
| `polling/printPollingResults` | `{dialog:b,polling:d._id}` |
| `polling/retractVote` | `{dialog:i.dialog,polling:i.media.polling._id}` |
| `polling/setPollingAsTemplate` | `d` |
| `polling/setPollingVote` | `{dialog:a.dialog,polling:a._id,my_votes:b}` |
| `polling/stopPolling` | `{dialog:i.dialog,polling:i.media.polling._id}` |

## profile (24)

| endpoint | body at call site |
|---|---|
| `profile/activate` | `{firstname:e.firstname,lastname:e.lastname,pass:f}` |
| `profile/authorizeTotpReplacement` | `{}` ; `{pinCode:b}` |
| `profile/cancelEmailVerification` | `{}` |
| `profile/changePhoneNumber` | `{step:2,token:q.token_from,phone:c,pin:q.pin_to}` ; `{step:1,password:g.createHash(q.password.toEnglishDigits())+"\|"+h.convertToSHA256(q.password.toEnglishDigits()),pinCode:q.pinCode}` |
| `profile/getEmailInfo` | `{}` |
| `profile/getProfileSecurity` | `{}` |
| `profile/initiateTotp` | `b?{replace_token:b}:{}` |
| `profile/recoverTotp` | `c` |
| `profile/removeEmail` | `{}` |
| `profile/removePhoto` | `{}` |
| `profile/removeTotp` | `{}` ; `{pinCode:a}` |
| `profile/setDontDisturbUntil` | `{hours:a}` ; `{hours:0}` |
| `profile/setOnlineStatus` | `{status:a.status}` |
| `profile/setUserOptions` | `{optionTitle:a,value:b}` ; `{optionTitle:"totp_intro_seen",value:!0}` |
| `profile/setWallpaper` | `{wallpaper:b}` |
| `profile/terminateOneSession` | `{regId:d.getRegId(),terminateSid:c.sid}` |
| `profile/terminateOtherSessions` | `{regId:d.getRegId()}` |
| `profile/turnTwoStepLoginOff` | `{two_step_login_method:b}` ; `{pinCode:a,two_step_login_method:f}` |
| `profile/update` | `b.profile` |
| `profile/updateEmail` | `{email:a}` |
| `profile/updatePassword` | `{current:g.createHash(e.current)+"\|"+h.convertToSHA256(e.current),pass:h.convertToSHA256(e.password),pinCode:e.pinCode}` |
| `profile/updatePhoto` | `{base:c._id,points:a}` |
| `profile/verifyEmail` | `{code:b.emailUi.code}` |
| `profile/verifyTotp` | `{code:a.totp.code}` |

## projectAutomation (15)

| endpoint | body at call site |
|---|---|
| `projectAutomation/buttonClicked` | `h` |
| `projectAutomation/customParam/add` | `{projectId:i,paramItem:a}` ; `{projectId:a,paramItem:e}` |
| `projectAutomation/customParam/delete` | `{projectId:e,paramId:a.param._id}` |
| `projectAutomation/customParam/getAll` | `{projectId:a,token:b,automateButtonId:c,isAdminMode:f}` |
| `projectAutomation/customParam/getHistory` | `{projectId:c,paramId:e._id}` |
| `projectAutomation/customParam/getValuesHistory` | `{token:c.access_token}` |
| `projectAutomation/customParam/restore` | `{projectId:a,paramId:b}` |
| `projectAutomation/customParam/update` | `{projectId:a,paramId:e._id,paramItem:i}` |
| `projectAutomation/customParam/updateOrder` | `{projectId:a,items:b}` |
| `projectAutomation/delete` | `{projectId:t,automateItemId:a._id}` |
| `projectAutomation/getAll` | `{projectId:e}` |
| `projectAutomation/getHistory` | `{automateId:t._id,projectId:i}` |
| `projectAutomation/getTaskAutomateButtons` | `{token:e.access_token}` |
| `projectAutomation/loadConstants` | `{}` |
| `projectAutomation/updateOrder` | `{projectId:m,type:c,items:d}` |

## projectAutomationWorkflow (5)

| endpoint | body at call site |
|---|---|
| `projectAutomationWorkflow/add` | `{projectId:t,workflow:e}` |
| `projectAutomationWorkflow/delete` | `{projectId:t,workflowId:e}` |
| `projectAutomationWorkflow/getAll` | `{projectId:f}` ; `{projectId:t}` |
| `projectAutomationWorkflow/getOne` | `{projectId:t,workflowId:e}` |
| `projectAutomationWorkflow/update` | `{projectId:t,workflow:e}` |

## projects (30)

| endpoint | body at call site |
|---|---|
| `projects/activateAdvancedFeatures` | `{project:z.project_entity,dialog:k,advanced:z.project.is_advanced}` |
| `projects/add` | `{title:a.title,color:a.color,members:b}` |
| `projects/addKanbanBoard` | `{projectId:c,kanbanBoard:f}` |
| `projects/allSummary` | `{}` ; `{with_details:!0}` |
| `projects/archive` | `{project_id:b._id}` |
| `projects/chatSummary` | `{dialog:c,project:b,withBoards:i}` ; `{dialog:m._id,project:n,withBoards:e}` |
| `projects/clone` | `{projectId:d,projectName:f.projectTitle.title,ignoreTaskIds:f.tasks_result.filter(a=>!a.selected).map(a=>a._id)}` |
| `projects/full` | `{project_id:a}` |
| `projects/ganttRemoveTask` | `{project:n.project,taskId:n._id}` |
| `projects/get` | `{projectId:a,token:c}` |
| `projects/getAdvancedFeaturesHistory` | `{dialog:d.getDialogByProjectId(g)?._id,project:g}` |
| `projects/getList` | `{}` |
| `projects/getListAdmin` | `{}` |
| `projects/getListAdminForMember` | `{user:a}` |
| `projects/getProjectFiles` | `a` |
| `projects/getProjectTaskFileIds` | `{project:o,task:c._id}` |
| `projects/getProjectsUserAdmin` | `{}` |
| `projects/history` | `{project_id:b._id}` |
| `projects/import` | `{contentId:j,importType:p,projectTitle:a.projectTitle,memberAssign:JSON.stringify(a.memberAssign),labelAssign:JSON.stringify(a.labelAssign),fieldIndexes:a.fieldIndexes,kanbanDoneListTitle:a.kanbanDoneListTitle}` |
| `projects/importPrepare` | `{contentId:c,importType:p}` |
| `projects/removeKanbanBoard` | `{projectId:o,boardId:b._id}` |
| `projects/restoreArchivedTasks` | `{project:c._id}` |
| `projects/save` | `{project_id:a._id,title:a.title,color:a.color,members:b}` |
| `projects/setAdvancedFeatures` | `{dialog:k,advanced:b}` ; `{dialog:e.getDialogByProjectId(d)._id,advanced:c}` |
| `projects/setAutomationExecutionStatus` | `{dialog:g._id,project:a,status:b}` |
| `projects/setChatProjectColor` | `{project:c,dialog:b,color:a}` |
| `projects/setChatProjectLabels` | `{project:b._id,dialog:b.dialog,labels:b.labels}` |
| `projects/setKanbanBoardOrder` | `{projectId:o,boardId:f,oldPosition:k,newPosition:h}` |
| `projects/undoArchive` | `{project_id:b._id}` |
| `projects/updateKanbanBoard` | `{projectId:c,kanbanBoardId:f._id,kanbanBoard:f}` |

## session (12)

| endpoint | body at call site |
|---|---|
| `session/createSSO` | `{token:d},{no_session:!0}` |
| `session/deleteAccount` | `{validationCode:e},{no_session:!0}` |
| `session/deleteAccountRequest` | `{username:a.username},{no_session:!0}` |
| `session/forgot` | `{username:b.forgot_username.username},{no_session:!0}` |
| `session/forgotReset` | `{reset_code:e.reset_code,pass:f},{no_session:!0}` |
| `session/forgotResetByTotp` | `{totp_code:e.totp_code,recovery_token:a.totpRecoveryToken,pass:f},{no_session:!0}` |
| `session/iOSAppIsAlive` | `{deviceId:b,isAlive:a}` |
| `session/register` | `l,{no_session:!0}` ; `e,{no_session:!0}` |
| `session/requestCodeWhenTotpUnavailable` | `{username:a.username,purpose:"password_reset"},{no_session:!0}` ; `{username:g,purpose:"login",two_step_challenge:i},{no_session:!0}` |
| `session/userInfo` | `{uid:n},{no_session:!0}` |
| `session/username` | `null,{no_session:!0}` |
| `session/verifyCodeWhenTotpUnavailable` | `{reset_code:b},{no_session:!0}` ; `{reset_code:a},{no_session:!0}` |

## support (32)

| endpoint | body at call site |
|---|---|
| `support/clientOnlineHistory` | `{}` |
| `support/closeResponse` | `{supportId:a}` |
| `support/deleteFromClient` | `{messageId:a}` |
| `support/deleteResponse` | `{supportId:a,messageId:b}` |
| `support/deleteResponseFeedback` | `{messageId:a}` |
| `support/editFromClient` | `{messageId:a,message:b}` |
| `support/editResponse` | `{supportId:a,messageId:b,message:c}` |
| `support/extendDialogLock` | `{supportId:a}` |
| `support/getAdminHistory` | `{supportId:a}` |
| `support/getClientUnreadCount` | `{}` |
| `support/getDialog` | `{dialog:a}` |
| `support/getDialogs` | `{filter:b,filterIsLastMessageIsRequest:c,skip:a,limit:d}` |
| `support/getFeedbackMonitor` | `a\|\|{}` |
| `support/getFeedbackMonitorOpenCount` | `{}` |
| `support/getFeedbackMonitorStats` | `a\|\|{}` |
| `support/getFeedbackReviewCase` | `{caseId:a}` |
| `support/getSupportInfo` | `{supportId:b}` |
| `support/lockDialog` | `{supportId:a}` |
| `support/markClientSeen` | `{seenCount:a}` |
| `support/markSupportSeen` | `{supportId:a,seenCount:b}` |
| `support/reopenFeedbackReview` | `{caseId:a}` |
| `support/resolveFeedbackReview` | `{caseId:a,result:b,dissatisfactionReason:c,note:d}` |
| `support/searchContent` | `{searchStr:e,messageType:a.content_search_filter.message_type,supportUser:a.content_search_filter.support_user,fromDate:b&&b.from?b.from.valueOf():null,toDate:b&&b.to?b.to.valueOf():null,skip:a.content_search_result.leng` |
| `support/sendFromClient` | `{message:a,media:b,replyTo:c}` |
| `support/sendResponse` | `{supportId:a,message:b,media:c,replyTo:d}` |
| `support/sendSuggestion` | `a.suggestion` |
| `support/setResponseFeedbackVote` | `{messageId:a,value:b,reason:c,comment:d}` |
| `support/setTyping` | `{}` |
| `support/setTypingAdmin` | `{supportId:a.currentDialog.dialogId}` |
| `support/startFeedbackReview` | `{caseId:a}` |
| `support/unlockDialog` | `{supportId:a}` |
| `support/updateResponseFeedbackDetails` | `{messageId:a,reason:b,comment:c}` |

## taskTemplates (6)

| endpoint | body at call site |
|---|---|
| `taskTemplates/add` | `a` |
| `taskTemplates/getAll` | `{projectId:a}` |
| `taskTemplates/getAllTemplates` | `{projectId:a}` |
| `taskTemplates/remove` | `{projectId:b,templateId:c}` |
| `taskTemplates/save` | `a` |
| `taskTemplates/setActive` | `{projectId:a,templateId:b._id,isActive:!!c}` |

## tasks (26)

| endpoint | body at call site |
|---|---|
| `tasks/add` | `o` ; `l` |
| `tasks/checkToken` | `{tid:n._id,token:n.access_token}` |
| `tasks/createShareLink` | `{token:n.access_token}` |
| `tasks/deleteComment` | `{token:n.access_token,commentId:t._id}` |
| `tasks/editComment` | `{token:n.access_token,commentId:t._id,newComment:e.newMessage}` |
| `tasks/ganttGetTaskInfo` | `{project:n.project,token:n.access_token}` |
| `tasks/get` | `s` |
| `tasks/getAll` | `e` |
| `tasks/getComments` | `{token:n.access_token}` |
| `tasks/getSeenDetails` | `{token:t}` |
| `tasks/history` | `{token:s.access_token,tid:s._id}` |
| `tasks/print` | `e` ; `a` |
| `tasks/removeFromBoard` | `{token:t.access_token,project_id:t.project}` |
| `tasks/removeFromTracking` | `{token:e.access_token}` |
| `tasks/removeTask` | `{token:n.access_token}` |
| `tasks/removeTaskUndo` | `{token:n.access_token}` |
| `tasks/save` | `o` |
| `tasks/setChecklistCheckedValue` | `{token:n.access_token,checklistId:t._id,checked:o}` |
| `tasks/setCompleted` | `{token:t.access_token,completed:!0,project:t.project}` ; `{token:t.access_token,project:t.project,completed:!1,progress:t.progress,undone_user_id:o}` |
| `tasks/setKanbanWeight` | `{token:k.access_token,projectId:o,kanbanBoardId:h,kanbanWeight:j}` |
| `tasks/setKanbanWeightSort` | `{projectId:o,kanbanBoardId:b._id,sortField:c,sortOrder:d}` |
| `tasks/snooze` | `{token:e.access_token,project:e.project,alarm_at:t,update_repeat_base:!!o.update_repeat_base}` |
| `tasks/toggleBookmark` | `{token:n.access_token,bookmarked:e}` |
| `tasks/upcoming` | `e` |
| `tasks/updateDeadline` | `{token:e.access_token,project:e.project,deadline:t}` |
| `tasks/updateProgress` | `{token:n.access_token,progress:n.progress}` |

## workspace (23)

| endpoint | body at call site |
|---|---|
| `workspace/add` | `{name:b.workspace_name,members:b.teammates}` |
| `workspace/changeOwner` | `{owner:b.user,pinCode:k,password:l}` |
| `workspace/changeRole` | `{user_id:c._id,role:c.role}` |
| `workspace/delete` | `{}` |
| `workspace/getPermissions` | `{}` |
| `workspace/getPlans` | `{}` |
| `workspace/getSettingsHistory` | `{before:h,filters:Object.assign({},l)}` |
| `workspace/getUsers` | `{}` |
| `workspace/ignoreBusinessTypeModal` | `{}` |
| `workspace/inviteMember` | `{name:a,email_phone:b,is_guest:c}` |
| `workspace/name` | `{}` |
| `workspace/planInfo` | `{details:b}` |
| `workspace/reJoinMember` | `{member_id:c._id}` |
| `workspace/removeMember` | `{member_id:c._id}` |
| `workspace/sendContactUsage` | `{user_id:b.to}` ; `{user_id:a._id}` |
| `workspace/setWorkspaceSettings` | `{title:a,value:c}` |
| `workspace/switch` | `{workspace_id:b}` |
| `workspace/updateBusinessType` | `{business_type:c}` |
| `workspace/updateDedicatedLogoPhoto` | `{photo:a.photo._id}` |
| `workspace/updateTitle` | `{title:y.name}` |
| `workspace/updateUserPermission` | `{user:b,permission:c,access:d}` |
| `workspace/updateWorkspaceRoleName` | `{user_id:b._id,workspaceRoleName:b.workspace_role_name_tmp}` |
| `workspace/userId` | `{regId:c.getRegId()}` |
