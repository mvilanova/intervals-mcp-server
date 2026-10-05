"""
Shared MCP instance module.

This module provides a shared FastMCP instance that can be imported by both
the server module and tool modules without creating cyclic imports.
"""

from mcp.server.fastmcp import FastMCP  # pylint: disable=import-error
from mcp.server.transport_security import TransportSecuritySettings  # pylint: disable=import-error

from intervals_mcp_server.api.client import setup_api_client

mcp: FastMCP = FastMCP(
    "intervals-icu",
    lifespan=setup_api_client,
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    stateless_http=True,
    json_response=True,
)  # pylint: disable=invalid-name
