"""
Shared MCP instance module.

This module provides a shared MCPServer instance that can be imported by both
the server module and tool modules without creating cyclic imports.
"""

import os
from typing import Literal, cast

from mcp.server.mcpserver import MCPServer  # pylint: disable=import-error

from intervals_mcp_server.api.client import setup_api_client

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

# mcp<2 read FASTMCP_LOG_LEVEL automatically; keep honoring it for existing setups.
_log_level = os.getenv("FASTMCP_LOG_LEVEL", "INFO").upper()
if _log_level not in _LOG_LEVELS:
    raise ValueError(f"Unsupported FASTMCP_LOG_LEVEL value. Use one of: {', '.join(_LOG_LEVELS)}.")

mcp: MCPServer = MCPServer(  # pylint: disable=invalid-name
    "intervals-icu", lifespan=setup_api_client, log_level=cast(LogLevel, _log_level)
)
