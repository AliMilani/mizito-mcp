"""Tool registration helpers shared by every tools/* module.

Each domain module exposes `register(tool, ctx)`. `tool` is the decorator
built by `make_tool`: it sets MCP annotations, scrubs secrets from every
result, and silently skips write tools when MIZITO_READ_ONLY=1.
"""
from __future__ import annotations

import functools
from dataclasses import dataclass
from typing import Any, Callable

from fastmcp import FastMCP
from mcp.types import ToolAnnotations

from ..client import MizitoClient
from ..config import Settings
from ..directory import Directory
from ..util import scrub


@dataclass
class Ctx:
    client: MizitoClient
    dir: Directory
    settings: Settings


def make_tool(server: FastMCP, settings: Settings,
              registry: dict[str, str] | None = None) -> Callable:
    """Returns `tool(write=..., destructive=..., idempotent=...)` decorator.

    `registry` (optional) collects name -> "read"/"write" for tests/docs.
    """
    def tool(*, write: bool = False, destructive: bool = False,
             idempotent: bool = False, title: str | None = None) -> Callable:
        def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
            if write and settings.read_only:
                return fn

            @functools.wraps(fn)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                return scrub(fn(*args, **kwargs))

            server.tool(
                wrapper,
                title=title,
                tags={"write" if write else "read"},
                annotations=ToolAnnotations(
                    readOnlyHint=not write,
                    destructiveHint=destructive if write else False,
                    idempotentHint=idempotent or not write,
                    openWorldHint=True,
                ),
            )
            if registry is not None:
                registry[fn.__name__] = "write" if write else "read"
            return fn
        return deco
    return tool


def register_all(tool: Callable, ctx: Ctx) -> None:
    from . import chat, projects, tasks, workspace
    for mod in (workspace, projects, tasks, chat):
        mod.register(tool, ctx)
    # write modules are imported lazily so read-only builds stay minimal
    from . import chat_writes, task_writes
    for mod in (task_writes, chat_writes):
        mod.register(tool, ctx)
