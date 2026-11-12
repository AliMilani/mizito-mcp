"""Builds the FastMCP server. `build()` is what tests and server.py call."""
from __future__ import annotations

import logging
import sys

from fastmcp import FastMCP

from . import __version__
from .client import MizitoClient
from .config import Settings
from .directory import Directory
from .tools import Ctx, make_tool, register_all

INSTRUCTIONS = """\
Mizito (office.mizito.ir) is the team's project-management + chat tool:
projects with kanban boards, tasks, task comments, and team chat.

How to use these tools well:
- Start cheap: daily_brief or get_projects_summary answer most status
  questions in one call. list_tasks is the main task query (filters by
  project, board, assignee, label, status, overdue, text).
- Arguments named user/assignee/project/board/label/chat accept an id OR a
  name/title. Persian names match even with Arabic ي/ك or ZWNJ differences.
  "me" means the current user. Ambiguous names raise an error listing the
  candidates: pick one and pass its id.
- Task ids come from list_tasks/search_tasks. Checklist item ids and comment
  ids come from get_task.
- Dates: results carry UTC ISO plus *_fa = Tehran time on the Jalali
  calendar. Inputs accept "YYYY-MM-DD HH:MM" (Gregorian, Tehran time),
  "1405/08/30 14:00" (Jalali) or ISO with Z.
- "When is it due" = the reminder (reminder/reminder_fa; set_task_reminder):
  that is what Mizito uses for today / overdue. `deadline` ("مهلت انجام")
  exists only in projects with the deadline feature.
- Write tools change real shared data that teammates see and get notified
  about. Confirm with the user before writing unless they asked for that
  exact change. Every write reads the object back and reports the verified
  result; if a write tool raises, treat the change as NOT done and check
  with a read before retrying.
- Chat messages are often task cards (type=task_card) with empty text:
  report the task title instead of calling the message empty.
"""


def build(settings: Settings | None = None, client: MizitoClient | None = None,
          registry: dict[str, str] | None = None) -> FastMCP:
    settings = settings or Settings.from_env()
    logging.basicConfig(stream=sys.stderr, level=settings.log_level,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    if not settings.token:
        logging.getLogger("mizito").error("MIZITO_TOKEN is not set (see .env)")
    client = client or MizitoClient(settings.token, settings.base_url,
                                    settings.workspace_id, settings.timeout)
    server = FastMCP("mizito", instructions=INSTRUCTIONS, version=__version__)
    ctx = Ctx(client=client, dir=Directory(client, ttl=settings.cache_ttl),
              settings=settings)
    register_all(make_tool(server, settings, registry), ctx)
    return server


def main() -> None:
    build().run(show_banner=False)
