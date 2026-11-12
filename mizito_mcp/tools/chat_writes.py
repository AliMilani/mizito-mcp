"""Chat mutations. Bodies come from the SPA (docs/API.md, "chat writes").

`chat/send` answers a bare `true` (the SPA ignores it and waits for a
socket event), so every send is verified by re-reading history and finding
my own message with the exact text, sent after the request started.
"""
from __future__ import annotations

import time

from .. import shape
from ..client import LookupError_, MizitoError
from ..util import is_object_id, plain_text
from . import Ctx


class WriteNotVerified(MizitoError):
    pass


def register(tool, ctx: Ctx) -> None:
    c, d = ctx.client, ctx.dir

    def _dialog_row(did: str) -> dict:
        d.invalidate("dialogs")
        return next((x for x in d.dialogs().get("dialogs") or [] if x.get("_id") == did), {})

    def _target(to: str | None, dialog_id: str | None) -> str:
        """dialog id from an id, a chat title, or a person (opens the DM)."""
        if dialog_id:
            return d.resolve_dialog(dialog_id)
        if not to:
            raise ValueError("pass `to` (chat title or person) or `dialog_id`")
        try:
            return d.resolve_dialog(to)  # refreshes the chat list once on a miss
        except LookupError_ as e:
            if "No chat matches" not in str(e):
                raise  # ambiguous: never guess who to message
        # Not a chat title. Only an exact person (id / full name / username)
        # may open a DM: a fuzzy match could message the wrong person.
        uid = d.resolve_user_exact(to)
        existing = d.dm_with(uid)
        if existing:
            return existing
        dlg = c.call("chat/createDialog", {"user": uid}, write=True) or {}
        d.invalidate("dialogs")
        if not dlg.get("_id"):
            raise MizitoError(f"Could not open a direct chat with {to!r}.")
        return dlg["_id"]

    def _recent_ids(did: str, scan: int = 30) -> set[str]:
        return {m.get("_id") for m in ctx.chat_history(did, scan)}

    def _find_new_mine(did: str, text: str, before: set[str],
                       scan: int = 30) -> dict | None:
        """My message with this text that was NOT in the chat before the send.
        Matching by new id (not time) means an identical earlier message can
        never be mistaken for this one."""
        me, want = d.me(), plain_text(text)
        for m in ctx.chat_history(did, scan):
            if (m.get("_id") not in before and m.get("from") == me
                    and plain_text(m.get("message")) == want):
                return m
        return None

    @tool(write=True)
    def send_message(text: str, to: str | None = None, dialog_id: str | None = None,
                     reply_to: str | None = None,
                     mention: list[str] | None = None) -> dict:
        """Send a chat message. Teammates see it immediately: confirm wording
        with the user first unless they dictated it.

        to: chat title (project group / group) or a person's name (their DM
            is opened if it does not exist yet). Or pass dialog_id.
        reply_to: message id to reply to (from read_chat).
        mention: people to @mention (names or ids).
        Newlines are kept. Verified by reading the chat back.
        """
        text = (text or "").strip()
        if not text:
            raise ValueError("text is empty: nothing to send")
        if reply_to and not is_object_id(reply_to):
            raise ValueError("reply_to must be a message id (24 hex chars)")
        did = _target(to, dialog_id)
        body = {"dialog": did, "message": text}
        if reply_to:
            body["reply_to"] = reply_to
        if mention:
            body["mention"] = d.resolve_users(mention)
        before = _recent_ids(did)
        c.call("chat/send", body, write=True)
        sent = None
        for delay in (0, 0.7, 1.5):
            time.sleep(delay)
            sent = _find_new_mine(did, text, before)
            if sent:
                break
        if not sent:
            raise WriteNotVerified("Message did not appear in the chat history. It may "
                                   "still arrive: check read_chat BEFORE sending again, "
                                   "or the team gets a duplicate.")
        return {"ok": True, "chat_id": did, "chat": d.dialog_title(_dialog_row(did)),
                "message": shape.message(sent, d)}

    @tool(write=True, idempotent=True)
    def edit_message(chat: str, message_id: str, text: str) -> dict:
        """Change the text of one of my own messages. Mizito only allows this
        before anyone has seen it (the web app hides Edit after that)."""
        text = (text or "").strip()
        if not text:
            raise ValueError("text is empty")
        did = d.resolve_dialog(chat)
        c.call("chat/updateSentMessage", {"dialog": did, "mid": message_id,
                                          "newMessage": text}, write=True)
        got = c.call("chat/getMessages", {"mids": [message_id], "dialog": did}) or []
        m = next((x for x in got if isinstance(x, dict) and x.get("_id") == message_id), None)
        if not m:
            return {"ok": True, "verified": False, "message_id": message_id,
                    "note": "Mizito did not return the message to check; open read_chat."}
        if plain_text(m.get("message")) != plain_text(text):
            raise WriteNotVerified("Message text did not change (probably already seen "
                                   "by someone, or not my message). NOT edited.")
        return {"ok": True, "verified": True, "message": shape.message(m, d)}

    @tool(write=True, destructive=True, idempotent=True)
    def delete_message(chat: str, message_id: str) -> dict:
        """Delete one of my messages for everyone. Confirm with the user first."""
        did = d.resolve_dialog(chat)
        c.call("chat/removeSentMessage", {"dialog": did, "mid": message_id}, write=True)
        got = c.call("chat/getMessages", {"mids": [message_id], "dialog": did}) or []
        m = next((x for x in got if isinstance(x, dict) and x.get("_id") == message_id), None)
        if m and not m.get("deleted"):
            raise WriteNotVerified("Message is still there: NOT deleted.")
        return {"ok": True, "deleted_message_id": message_id, "chat_id": did,
                "verified": "flagged deleted" if m else
                            "no longer returned by Mizito (most likely deleted)"}

    @tool(write=True, idempotent=True)
    def mark_chat_read(chat: str) -> dict:
        """Mark every message in a chat as read (clears its unread badge)."""
        did = d.resolve_dialog(chat)
        row = _dialog_row(did)
        c.call("chat/seen", {"dialog": did, "seen_count": row.get("messages_count") or 0},
               write=True)
        after = _dialog_row(did)
        if after.get("unread_count"):
            raise WriteNotVerified(f"Chat still shows {after['unread_count']} unread.")
        return {"ok": True, "chat_id": did, "chat": d.dialog_title(after), "unread": 0}
