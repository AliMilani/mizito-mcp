"""Mizito MCP server package.

Layout (README.md has the long version):

- config.py     environment -> Settings
- client.py     HTTP transport, retries, error mapping (the only module that talks to Mizito)
- util.py       Persian text normalisation, Jalali/Tehran dates, secret scrubbing
- directory.py  cached lookups (users, projects, boards, labels, dialogs) and name -> id resolution
- shape.py      raw Mizito objects -> compact agent-facing dicts
- tasks_api.py  task listing/pagination/filter building shared by several tools
- tools/        one module per domain; each exposes register(server, ctx)
- app.py        builds the FastMCP server
"""

__version__ = "2.0.0"
