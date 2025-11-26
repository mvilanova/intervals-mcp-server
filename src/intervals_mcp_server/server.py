"""
Intervals.icu MCP Server

This module implements a Model Context Protocol (MCP) server for connecting
Claude with the Intervals.icu API. It provides tools for retrieving and managing
athlete data, including activities, events, workouts, and wellness metrics.

Main Features:
    - Activity retrieval and detailed analysis
    - Event management (races, workouts, calendar items)
    - Wellness data tracking and visualization
    - Error handling with user-friendly messages
    - Configurable parameters with environment variable support

Usage:
    This server is designed to be run as a standalone script and exposes several MCP tools
    for use with Claude Desktop or other MCP-compatible clients. The server loads configuration
    from environment variables (optionally via a .env file) and communicates with the Intervals.icu API.

    To run the server:
        $ python src/intervals_mcp_server/server.py

    MCP tools provided:
        - get_activities
        - get_activity_details
        - get_events
        - get_event_by_id
        - get_wellness_data
        - get_activity_intervals
        - get_activity_streams
        - add_events

    See the README for more details on configuration and usage.
"""

import logging

from mcp.server.fastmcp import FastMCP  # pylint: disable=import-error

# Import API client and configuration
from intervals_mcp_server.api.client import (
    httpx_client,  # Re-export for backward compatibility with tests
    make_intervals_request,
    setup_api_client,
)
from intervals_mcp_server.config import get_config

# Import types and validation
from intervals_mcp_server.server_setup import setup_transport, start_server
from intervals_mcp_server.utils.validation import validate_athlete_id

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("intervals_icu_mcp_server")

# Get configuration instance
config = get_config()

# Initialize FastMCP server with custom lifespan
mcp = FastMCP("intervals-icu", lifespan=setup_api_client)

# Set the shared mcp instance for tool modules to use (breaks cyclic imports)
from intervals_mcp_server import mcp_instance  # pylint: disable=wrong-import-position  # noqa: E402

mcp_instance.mcp = mcp

# Import tool modules to register them (tools register themselves via @mcp.tool() decorators)
# Import tool functions for re-export (imported after mcp instance creation)
from intervals_mcp_server.tools.activities import (  # pylint: disable=wrong-import-position  # noqa: E402
    get_activities,
    get_activity_details,
    get_activity_intervals,
    get_activity_streams,
)
from intervals_mcp_server.tools.events import (  # pylint: disable=wrong-import-position  # noqa: E402
    add_or_update_event,
    delete_event,
    delete_events_by_date_range,
    get_event_by_id,
    get_events,
)
from intervals_mcp_server.tools.wellness import get_wellness_data  # pylint: disable=wrong-import-position  # noqa: E402

# Re-export make_intervals_request and httpx_client for backward compatibility
# pylint: disable=duplicate-code  # This __all__ list is intentionally similar to tools/__init__.py
__all__ = [
    "make_intervals_request",
    "httpx_client",  # Re-exported for test compatibility
    "get_activities",
    "get_activity_details",
    "get_activity_intervals",
    "get_activity_streams",
    "get_events",
    "get_event_by_id",
    "delete_event",
    "delete_events_by_date_range",
    "add_or_update_event",
    "get_wellness_data",
]


# Run the server
if __name__ == "__main__":
    # Validate ATHLETE_ID when server starts (not at import time to allow tests)
    validate_athlete_id(config.athlete_id)

    # Setup transport and start server
    selected_transport = setup_transport()
    start_server(mcp, selected_transport)
