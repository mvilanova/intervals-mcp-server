"""
Shared MCP instance module.

This module provides a shared FastMCP instance that can be imported by both
the server module and tool modules without creating cyclic imports.
"""

from mcp.server.fastmcp import FastMCP  # pylint: disable=import-error

from intervals_mcp_server.api.client import setup_api_client
from intervals_mcp_server.auth import auth_settings_from_env

mcp: FastMCP = FastMCP(  # pylint: disable=invalid-name
    "intervals-icu", lifespan=setup_api_client, **auth_settings_from_env()
)
