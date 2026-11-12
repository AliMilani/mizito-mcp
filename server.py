#!/usr/bin/env python3
"""Mizito MCP server entry point (stdio).

Kept at this path because run-mcp.sh, the Dockerfile and existing MCP client
registrations all exec `server.py`. The code lives in the mizito_mcp package;
see README.md for the layout.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mizito_mcp.app import main  # noqa: E402

if __name__ == "__main__":
    main()
