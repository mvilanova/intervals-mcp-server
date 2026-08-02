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
        - get_activity_intervals
        - get_activity_streams
        - get_activity_messages
        - add_activity_message
        - get_events
        - get_event_by_id
        - add_or_update_event
        - delete_event
        - delete_events_by_date_range
        - get_wellness_data
        - get_athlete_power_curves
        - get_custom_items
        - get_custom_item_by_id
        - create_custom_item
        - update_custom_item
        - delete_custom_item

    See the README for more details on configuration and usage.
"""

import logging

# Import API client and configuration
from intervals_mcp_server.api.client import (
    httpx_client,  # Re-export for backward compatibility with tests
    make_intervals_request,
)
from intervals_mcp_server.config import Config, get_config
from intervals_mcp_server.mcp_instance import mcp

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


def _log_configured_account(config: Config) -> None:
    """Log the configured ATHLETE_ID and a short API_KEY fingerprint at startup.

    AGENTS.md names the wrong-account foot-gun (MCP .env drift from
    athlete-profile.md) as the silent-failure mode that misroutes reads to
    a different athlete. Surfacing the configured athlete_id and api_key
    fingerprint at boot is the first diagnostic line of defense — without
    it, drift can only be caught by external cross-checking, which a
    calling agent cannot do reliably.
    """
    athlete_id = config.athlete_id
    api_key = config.api_key
    if athlete_id and api_key:
        logger.info(
            "Configured for athlete %s with API key %s... (len=%d)",
            athlete_id,
            api_key[:4],
            len(api_key),
        )
        return
    missing: list[str] = []
    if not athlete_id:
        missing.append("ATHLETE_ID")
    if not api_key:
        missing.append("API_KEY")
    logger.warning(
        "Intervals.icu MCP server started without %s — pass credentials "
        "explicitly to each tool, or set the missing env vars to restore "
        "the fallback path.",
        " and ".join(missing),
    )


# Get configuration instance
config = get_config()

# Import tool modules to register them (tools register themselves via @mcp.tool() decorators)
# Import tool functions for re-export
from intervals_mcp_server.tools.activities import (  # pylint: disable=wrong-import-position  # noqa: E402
    add_activity_message,
    get_activities,
    get_activity_details,
    get_activity_intervals,
    get_activity_messages,
    get_activity_streams,
)
from intervals_mcp_server.tools.events import (  # pylint: disable=wrong-import-position  # noqa: E402
    add_or_update_event,
    delete_event,
    delete_events_by_date_range,
    get_event_by_id,
    get_events,
)
from intervals_mcp_server.tools.gear import get_gear_list  # pylint: disable=wrong-import-position  # noqa: E402
from intervals_mcp_server.tools.wellness import get_wellness_data  # pylint: disable=wrong-import-position  # noqa: E402
from intervals_mcp_server.tools.power_curves import get_athlete_power_curves  # pylint: disable=wrong-import-position  # noqa: E402
from intervals_mcp_server.tools.custom_items import (  # pylint: disable=wrong-import-position  # noqa: E402
    create_custom_item,
    delete_custom_item,
    get_custom_item_by_id,
    get_custom_items,
    update_custom_item,
)

# Re-export make_intervals_request and httpx_client for backward compatibility
# pylint: disable=duplicate-code  # This __all__ list is intentionally similar to tools/__init__.py
__all__ = [
    "make_intervals_request",
    "httpx_client",  # Re-exported for test compatibility
    "add_activity_message",
    "get_activities",
    "get_activity_details",
    "get_activity_intervals",
    "get_activity_messages",
    "get_activity_streams",
    "get_events",
    "get_event_by_id",
    "delete_event",
    "delete_events_by_date_range",
    "add_or_update_event",
    "get_wellness_data",
    "get_athlete_power_curves",
    "get_custom_items",
    "get_custom_item_by_id",
    "create_custom_item",
    "update_custom_item",
    "delete_custom_item",
]


# Run the server
if __name__ == "__main__":
    # Validate ATHLETE_ID when server starts (not at import time to allow tests)
    validate_athlete_id(config.athlete_id)

    # Surface the configured account so .env drift vs athlete-profile.md
    # is visible at boot, not silently misroute requests later.
    _log_configured_account(config)

    # Setup transport and start server
    selected_transport = setup_transport()
    start_server(mcp, selected_transport)
