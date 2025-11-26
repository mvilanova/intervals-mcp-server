"""
Server setup and initialization for Intervals.icu MCP Server.

This module handles transport configuration and server startup logic.
"""

import os
import logging

from mcp.server.fastmcp import FastMCP  # pylint: disable=import-error

from intervals_mcp_server.utils.types import TransportAliases

logger = logging.getLogger("intervals_icu_mcp_server")


def setup_transport() -> TransportAliases:
    """
    Setup and validate the MCP transport configuration.

    Reads MCP_TRANSPORT environment variable and validates it against
    supported transport types.

    Returns:
        TransportAliases: The selected transport type.

    Raises:
        ValueError: If the transport type is not supported.
    """
    transport_env = os.getenv("MCP_TRANSPORT", TransportAliases.STDIO.value).lower()
    try:
        transport_alias = TransportAliases(transport_env)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in TransportAliases)
        raise ValueError(f"Unsupported MCP_TRANSPORT value. Use one of: {allowed}.") from exc

    # Map HTTP to STREAMABLE_HTTP
    selected_transport = (
        TransportAliases.STREAMABLE_HTTP
        if transport_alias == TransportAliases.HTTP
        else transport_alias
    )

    return selected_transport


def start_server(mcp_instance: FastMCP, transport: TransportAliases) -> None:
    """
    Start the MCP server with the specified transport.

    Args:
        mcp_instance (FastMCP): The FastMCP server instance to start.
        transport (TransportAliases): The transport type to use.
    """
    host = mcp_instance.settings.host
    port = mcp_instance.settings.port

    if transport == TransportAliases.STDIO:
        logger.info("Starting MCP server with stdio transport.")
        mcp_instance.run()
    elif transport == TransportAliases.SSE:
        mount_path = os.getenv("MCP_SSE_MOUNT_PATH")
        logger.info(
            "Starting MCP server with SSE transport at http://%s:%s%s (messages: %s).",
            host,
            port,
            mcp_instance.settings.sse_path,
            mcp_instance.settings.message_path,
        )
        mcp_instance.run(transport="sse", mount_path=mount_path)
    else:  # STREAMABLE_HTTP
        logger.info(
            "Starting MCP server with Streamable HTTP transport at http://%s:%s%s.",
            host,
            port,
            mcp_instance.settings.streamable_http_path,
        )
        mcp_instance.run(transport="streamable-http")
