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
        - list_events
        - get_event_by_id
        - get_wellness_data
        - get_activity_intervals
        - get_races
        - get_power_curves
        - get_activity_power_curves
        - get_pace_curves
        - get_activity_pace_curve
        - get_athlete
        - get_power_hr_curve
        - get_activity_power_vs_hr
        - get_activity_hr_curve
        - get_current_date_info
        - get_workout_format_examples
        - create_workout

    See the README for more details on configuration and usage.
"""

from json import JSONDecodeError
import logging
import os
import re
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from http import HTTPStatus
from typing import Any

import httpx  # pylint: disable=import-error
from mcp.server.fastmcp import FastMCP  # pylint: disable=import-error

# Import formatting utilities
from intervals_mcp_server.utils.formatting import (
    format_activity_summary,
    format_event_details,
    format_event_summary,
    format_intervals,
    format_wellness_entry,
)

# Try to load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv

    _ = load_dotenv()
except ImportError:
    # python-dotenv not installed, proceed without it
    pass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("intervals_icu_mcp_server")

# Create a single AsyncClient instance for all requests
httpx_client = httpx.AsyncClient()


@asynccontextmanager
async def lifespan(_app: FastMCP):
    """
    Context manager to ensure the shared httpx client is closed when the server stops.

    Args:
        _app (FastMCP): The MCP server application instance.
    """
    try:
        yield
    finally:
        await httpx_client.aclose()


# Initialize FastMCP server with custom lifespan
mcp = FastMCP("intervals-icu", lifespan=lifespan)

# Constants
INTERVALS_API_BASE_URL = os.getenv("INTERVALS_API_BASE_URL", "https://intervals.icu/api/v1")
API_KEY = os.getenv("API_KEY", "")  # Provide default empty string
ATHLETE_ID = os.getenv("ATHLETE_ID", "")  # Default athlete ID from .env
USER_AGENT = "intervalsicu-mcp-server/1.0"

# Validate environment variables on import
if API_KEY == "":
    raise ValueError("API_KEY environment variable is not set or empty")

# Accept athlete IDs that are either all digits or start with 'i' followed by digits
if not re.fullmatch(r"i?\d+", ATHLETE_ID):
    raise ValueError(
        "ATHLETE_ID must be all digits (e.g. 123456) or start with 'i' followed by digits (e.g. i123456)"
    )


async def make_intervals_request(
    url: str, api_key: str | None = None, params: dict[str, Any] | None = None
) -> dict[str, Any] | list[dict[str, Any]]:
    """
    Make a GET request to the Intervals.icu API with proper error handling.

    Args:
        url (str): The API endpoint path (e.g., '/athlete/{id}/activities').
        api_key (str | None): Optional API key to use for authentication. Defaults to the global API_KEY.
        params (dict[str, Any] | None): Optional query parameters for the request.

    Returns:
        dict[str, Any] | list[dict[str, Any]]: The parsed JSON response from the API, or an error dict.
    """
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}

    # Use provided api_key or fall back to global API_KEY
    key_to_use = api_key if api_key is not None else API_KEY
    auth = httpx.BasicAuth("API_KEY", key_to_use)
    full_url = f"{INTERVALS_API_BASE_URL}{url}"

    try:
        response = await httpx_client.get(
            full_url, headers=headers, params=params, auth=auth, timeout=30.0
        )
        try:
            data = response.json() if response.content else {}
        except JSONDecodeError:
            logger.error("Invalid JSON in response from: %s", full_url)
            return {"error": True, "message": "Invalid JSON in response"}
        _ = response.raise_for_status()
        return data
    except httpx.HTTPStatusError as e:
        error_code = e.response.status_code
        error_text = e.response.text

        logger.error("HTTP error: %s - %s", error_code, error_text)

        # Provide specific messages for common error codes
        error_messages = {
            HTTPStatus.UNAUTHORIZED: f"{HTTPStatus.UNAUTHORIZED.value} {HTTPStatus.UNAUTHORIZED.phrase}: Please check your API key.",
            HTTPStatus.FORBIDDEN: f"{HTTPStatus.FORBIDDEN.value} {HTTPStatus.FORBIDDEN.phrase}: You may not have permission to access this resource.",
            HTTPStatus.NOT_FOUND: f"{HTTPStatus.NOT_FOUND.value} {HTTPStatus.NOT_FOUND.phrase}: The requested endpoint or ID doesn't exist.",
            HTTPStatus.UNPROCESSABLE_ENTITY: f"{HTTPStatus.UNPROCESSABLE_ENTITY.value} {HTTPStatus.UNPROCESSABLE_ENTITY.phrase}: The server couldn't process the request (invalid parameters or unsupported operation). Details: {error_text}",
            HTTPStatus.TOO_MANY_REQUESTS: f"{HTTPStatus.TOO_MANY_REQUESTS.value} {HTTPStatus.TOO_MANY_REQUESTS.phrase}: Too many requests in a short time period.",
            HTTPStatus.INTERNAL_SERVER_ERROR: f"{HTTPStatus.INTERNAL_SERVER_ERROR.value} {HTTPStatus.INTERNAL_SERVER_ERROR.phrase}: The Intervals.icu server encountered an internal error.",
            HTTPStatus.SERVICE_UNAVAILABLE: f"{HTTPStatus.SERVICE_UNAVAILABLE.value} {HTTPStatus.SERVICE_UNAVAILABLE.phrase}: The Intervals.icu server might be down or undergoing maintenance.",
        }

        # Get a specific message or default to the server's response
        try:
            status = HTTPStatus(error_code)
            custom_message = error_messages.get(status, error_text)
        except ValueError:
            # If the status code doesn't map to HTTPStatus, use the error_text
            custom_message = error_text

        return {"error": True, "status_code": error_code, "message": custom_message}
    except httpx.RequestError as e:
        logger.error("Request error: %s", str(e))
        return {"error": True, "message": f"Request error: {str(e)}"}
    except Exception as e:
        logger.error("Unexpected error: %s", str(e))
        return {"error": True, "message": f"Unexpected error: {str(e)}"}


async def make_intervals_post_request(
    url: str, data: dict[str, Any], api_key: str | None = None
) -> dict[str, Any] | list[dict[str, Any]]:
    """
    Make a POST request to the Intervals.icu API with proper error handling.

    Args:
        url (str): The API endpoint path (e.g., '/athlete/{id}/events').
        data (dict[str, Any]): The JSON data to send in the request body.
        api_key (str | None): Optional API key to use for authentication. Defaults to the global API_KEY.

    Returns:
        dict[str, Any] | list[dict[str, Any]]: The parsed JSON response from the API, or an error dict.
    """
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    # Use provided api_key or fall back to global API_KEY
    key_to_use = api_key if api_key is not None else API_KEY
    auth = httpx.BasicAuth("API_KEY", key_to_use)
    full_url = f"{INTERVALS_API_BASE_URL}{url}"

    try:
        response = await httpx_client.post(full_url, headers=headers, json=data, auth=auth, timeout=30.0)
        try:
            response_data = response.json() if response.content else {}
        except JSONDecodeError:
            logger.error("Invalid JSON in response from: %s", full_url)
            return {"error": True, "message": "Invalid JSON in response"}
        _ = response.raise_for_status()
        return response_data
    except httpx.HTTPStatusError as e:
        error_code = e.response.status_code
        error_text = e.response.text

        logger.error("HTTP error: %s - %s", error_code, error_text)

        # Provide specific messages for common error codes
        error_messages = {
            HTTPStatus.UNAUTHORIZED: f"{HTTPStatus.UNAUTHORIZED.value} {HTTPStatus.UNAUTHORIZED.phrase}: Please check your API key.",
            HTTPStatus.FORBIDDEN: f"{HTTPStatus.FORBIDDEN.value} {HTTPStatus.FORBIDDEN.phrase}: You may not have permission to access this resource.",
            HTTPStatus.NOT_FOUND: f"{HTTPStatus.NOT_FOUND.value} {HTTPStatus.NOT_FOUND.phrase}: The requested endpoint or ID doesn't exist.",
            HTTPStatus.UNPROCESSABLE_ENTITY: f"{HTTPStatus.UNPROCESSABLE_ENTITY.value} {HTTPStatus.UNPROCESSABLE_ENTITY.phrase}: The server couldn't process the request (invalid parameters or unsupported operation). Details: {error_text}",
            HTTPStatus.TOO_MANY_REQUESTS: f"{HTTPStatus.TOO_MANY_REQUESTS.value} {HTTPStatus.TOO_MANY_REQUESTS.phrase}: Too many requests in a short time period.",
            HTTPStatus.INTERNAL_SERVER_ERROR: f"{HTTPStatus.INTERNAL_SERVER_ERROR.value} {HTTPStatus.INTERNAL_SERVER_ERROR.phrase}: The Intervals.icu server encountered an internal error.",
            HTTPStatus.SERVICE_UNAVAILABLE: f"{HTTPStatus.SERVICE_UNAVAILABLE.value} {HTTPStatus.SERVICE_UNAVAILABLE.phrase}: The Intervals.icu server might be down or undergoing maintenance.",
        }

        # Get a specific message or default to the server's response
        try:
            status = HTTPStatus(error_code)
            custom_message = error_messages.get(status, error_text)
        except ValueError:
            # If the status code doesn't map to HTTPStatus, use the error_text
            custom_message = error_text

        return {"error": True, "status_code": error_code, "message": custom_message}
    except httpx.RequestError as e:
        logger.error("Request error: %s", str(e))
        return {"error": True, "message": f"Request error: {str(e)}"}
    except httpx.HTTPError as e:
        logger.error("HTTP client error: %s", str(e))
        return {"error": True, "message": f"HTTP client error: {str(e)}"}


# ----- MCP Tool Implementations ----- #


def _parse_activities_from_result(result: Any) -> list[dict[str, Any]]:
    """Extract a list of activity dictionaries from the API result."""
    activities: list[dict[str, Any]] = []

    if isinstance(result, list):
        activities = [item for item in result if isinstance(item, dict)]
    elif isinstance(result, dict):
        # Result is a single activity or a container
        for _key, value in result.items():
            if isinstance(value, list):
                activities = [item for item in value if isinstance(item, dict)]
                break
        # If no list was found but the dict has typical activity fields, treat it as a single activity
        if not activities and any(key in result for key in ["name", "startTime", "distance"]):
            activities = [result]

    return activities


def _filter_named_activities(activities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter out unnamed activities from the list."""
    return [
        activity
        for activity in activities
        if activity.get("name") and activity.get("name") != "Unnamed"
    ]


async def _fetch_more_activities(
    athlete_id: str,
    start_date: str,
    api_key: str | None,
    api_limit: int,
) -> list[dict[str, Any]]:
    """Fetch additional activities from an earlier date range."""
    oldest_date = datetime.fromisoformat(start_date)
    older_start_date = (oldest_date - timedelta(days=60)).strftime("%Y-%m-%d")
    older_end_date = (oldest_date - timedelta(days=1)).strftime("%Y-%m-%d")

    if older_start_date >= older_end_date:
        return []

    more_params = {
        "oldest": older_start_date,
        "newest": older_end_date,
        "limit": api_limit,
    }
    more_result = await make_intervals_request(
        url=f"/athlete/{athlete_id}/activities",
        api_key=api_key,
        params=more_params,
    )

    if isinstance(more_result, list):
        return _filter_named_activities(more_result)
    return []


def _format_activities_response(
    activities: list[dict[str, Any]],
    athlete_id: str,
    include_unnamed: bool,
) -> str:
    """Format the activities response based on the results."""
    if not activities:
        if include_unnamed:
            return (
                f"No valid activities found for athlete {athlete_id} in the specified date range."
            )
        return f"No named activities found for athlete {athlete_id} in the specified date range. Try with include_unnamed=True to see all activities."

    # Format the output
    activities_summary = "Activities:\n\n"
    for activity in activities:
        if isinstance(activity, dict):
            activities_summary += format_activity_summary(activity) + "\n"
        else:
            activities_summary += f"Invalid activity format: {activity}\n\n"

    return activities_summary


@mcp.tool()
async def get_activities(  # pylint: disable=too-many-arguments,too-many-return-statements,too-many-branches,too-many-positional-arguments
    athlete_id: str | None = None,
    api_key: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 10,
    include_unnamed: bool = False,
) -> str:
    """Get a list of activities for an athlete from Intervals.icu

    Args:
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
        start_date: Start date in YYYY-MM-DD format (optional, defaults to 30 days ago)
        end_date: End date in YYYY-MM-DD format (optional, defaults to today)
        limit: Maximum number of activities to return (optional, defaults to 10)
        include_unnamed: Whether to include unnamed activities (optional, defaults to False)
    """
    # Use provided athlete_id or fall back to global ATHLETE_ID
    athlete_id_to_use = athlete_id if athlete_id is not None else ATHLETE_ID
    if not athlete_id_to_use:
        return "Error: No athlete ID provided and no default ATHLETE_ID found in environment variables."

    # Parse date parameters
    if not start_date:
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")

    # Fetch more activities if we need to filter out unnamed ones
    api_limit = limit * 3 if not include_unnamed else limit

    # Call the Intervals.icu API
    params = {"oldest": start_date, "newest": end_date, "limit": api_limit}
    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/activities", api_key=api_key, params=params
    )

    # Check for error
    if isinstance(result, dict) and "error" in result:
        error_message = result.get("message", "Unknown error")
        return f"Error fetching activities: {error_message}"

    if not result:
        return f"No activities found for athlete {athlete_id_to_use} in the specified date range."

    # Parse activities from result
    activities = _parse_activities_from_result(result)

    if not activities:
        return f"No valid activities found for athlete {athlete_id_to_use} in the specified date range."

    # Filter and fetch more if needed
    if not include_unnamed:
        activities = _filter_named_activities(activities)

        # If we don't have enough named activities, try to fetch more
        if len(activities) < limit:
            more_activities = await _fetch_more_activities(
                athlete_id_to_use, start_date, api_key, api_limit
            )
            activities.extend(more_activities)

    # Limit to requested count
    activities = activities[:limit]

    return _format_activities_response(activities, athlete_id_to_use, include_unnamed)


@mcp.tool()
async def get_activity_details(activity_id: str, api_key: str | None = None) -> str:
    """Get detailed information for a specific activity from Intervals.icu

    Args:
        activity_id: The Intervals.icu activity ID
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
    """
    # Call the Intervals.icu API
    result = await make_intervals_request(url=f"/activity/{activity_id}", api_key=api_key)

    if isinstance(result, dict) and "error" in result:
        error_message = result.get("message", "Unknown error")
        return f"Error fetching activity details: {error_message}"

    # Format the response
    if not result:
        return f"No details found for activity {activity_id}."

    # If result is a list, use the first item if available
    activity_data = result[0] if isinstance(result, list) and result else result
    if not isinstance(activity_data, dict):
        return f"Invalid activity format for activity {activity_id}."

    # Return a more detailed view of the activity
    detailed_view = format_activity_summary(activity_data)

    # Add additional details if available
    if "zones" in activity_data:
        zones = activity_data["zones"]
        detailed_view += "\nPower Zones:\n"
        for zone in zones.get("power", []):
            detailed_view += f"Zone {zone.get('number')}: {zone.get('secondsInZone')} seconds\n"

        detailed_view += "\nHeart Rate Zones:\n"
        for zone in zones.get("hr", []):
            detailed_view += f"Zone {zone.get('number')}: {zone.get('secondsInZone')} seconds\n"

    return detailed_view


@mcp.tool()
async def get_events(
    athlete_id: str | None = None,
    api_key: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> str:
    """Get events for an athlete from Intervals.icu

    Args:
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
        start_date: Start date in YYYY-MM-DD format (optional, defaults to today)
        end_date: End date in YYYY-MM-DD format (optional, defaults to 30 days from today)
    """
    # Use provided athlete_id or fall back to global ATHLETE_ID
    athlete_id_to_use = athlete_id if athlete_id is not None else ATHLETE_ID
    if not athlete_id_to_use:
        return "Error: No athlete ID provided and no default ATHLETE_ID found in environment variables."

    # Parse date parameters
    if not start_date:
        start_date = datetime.now().strftime("%Y-%m-%d")
    if not end_date:
        end_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

    # Call the Intervals.icu API
    params = {"oldest": start_date, "newest": end_date}

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/events", api_key=api_key, params=params
    )

    if isinstance(result, dict) and "error" in result:
        error_message = result.get("message", "Unknown error")
        return f"Error fetching events: {error_message}"

    # Format the response
    if not result:
        return f"No events found for athlete {athlete_id_to_use} in the specified date range."

    # Ensure result is a list
    events = result if isinstance(result, list) else []

    if not events:
        return f"No events found for athlete {athlete_id_to_use} in the specified date range."

    events_summary = "Events:\n\n"
    for event in events:
        if not isinstance(event, dict):
            continue

        events_summary += format_event_summary(event) + "\n\n"

    return events_summary


@mcp.tool()
async def list_events(
    athlete_id: str | None = None,
    api_key: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    category: str | None = None,
    limit: int = 30,
) -> list[dict] | str:
    """Get events for an athlete from Intervals.icu

    Args:
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
        start_date: Start date in YYYY-MM-DD format (optional, defaults to today)
        end_date: End date in YYYY-MM-DD format (optional, defaults to 7 days from start_date)
        category: Filter by event category (optional, e.g., "WORKOUT,RACE_A,RACE_B,RACE_C")
        limit: Maximum number of events to return (optional, defaults to 30)

    Returns:
        List of event dictionaries or error message
    """
    # Use provided athlete_id or fall back to global ATHLETE_ID
    athlete_id_to_use = athlete_id if athlete_id is not None else ATHLETE_ID
    if not athlete_id_to_use:
        return "Error: No athlete ID provided and no default ATHLETE_ID found in environment variables."

    # Use existing format parameter to ensure JSON output
    format_param = ""

    # Build query parameters
    params = {}
    if start_date:
        params["oldest"] = start_date
    if end_date:
        params["newest"] = end_date
    if category:
        params["category"] = category
    if limit:
        params["limit"] = limit

    # Call the Intervals.icu API using the existing helper function
    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/events{format_param}",
        api_key=api_key,
        params=params,
    )

    # Handle potential errors
    if isinstance(result, dict) and "error" in result:
        error_message = result.get("message", "Unknown error")
        return f"Error fetching events: {error_message}"

    # Process and format the events for better readability
    if isinstance(result, list):
        # Return the raw list for maximum flexibility
        return result

    return "No events found or invalid response format"


@mcp.tool()
async def get_event_by_id(
    event_id: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Get detailed information for a specific event from Intervals.icu

    Args:
        event_id: The Intervals.icu event ID
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
    """
    # Use provided athlete_id or fall back to global ATHLETE_ID
    athlete_id_to_use = athlete_id if athlete_id is not None else ATHLETE_ID
    if not athlete_id_to_use:
        return "Error: No athlete ID provided and no default ATHLETE_ID found in environment variables."

    # Call the Intervals.icu API
    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/event/{event_id}", api_key=api_key
    )

    if isinstance(result, dict) and "error" in result:
        error_message = result.get("message", "Unknown error")
        return f"Error fetching event details: {error_message}"

    # Format the response
    if not result:
        return f"No details found for event {event_id}."

    if not isinstance(result, dict):
        return f"Invalid event format for event {event_id}."

    return format_event_details(result)


@mcp.tool()
async def get_wellness_data(
    athlete_id: str | None = None,
    api_key: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> str:
    """Get wellness data for an athlete from Intervals.icu

    Args:
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
        start_date: Start date in YYYY-MM-DD format (optional, defaults to 30 days ago)
        end_date: End date in YYYY-MM-DD format (optional, defaults to today)
    """
    # Use provided athlete_id or fall back to global ATHLETE_ID
    athlete_id_to_use = athlete_id if athlete_id is not None else ATHLETE_ID
    if not athlete_id_to_use:
        return "Error: No athlete ID provided and no default ATHLETE_ID found in environment variables."

    # Parse date parameters
    if not start_date:
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")

    # Call the Intervals.icu API
    params = {"oldest": start_date, "newest": end_date}

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/wellness", api_key=api_key, params=params
    )

    if isinstance(result, dict) and "error" in result:
        return f"Error fetching wellness data: {result.get('message')}"

    # Format the response
    if not result:
        return (
            f"No wellness data found for athlete {athlete_id_to_use} in the specified date range."
        )

    wellness_summary = "Wellness Data:\n\n"

    # Handle both list and dictionary responses
    if isinstance(result, dict):
        for date_str, data in result.items():
            # Add the date to the data dictionary if it's not already presen
            if isinstance(data, dict) and "date" not in data:
                data["date"] = date_str
            wellness_summary += format_wellness_entry(data) + "\n\n"
    elif isinstance(result, list):
        for entry in result:
            if isinstance(entry, dict):
                wellness_summary += format_wellness_entry(entry) + "\n\n"

    return wellness_summary


@mcp.tool()
async def get_activity_intervals(activity_id: str, api_key: str | None = None) -> str:
    """Get interval data for a specific activity from Intervals.icu

    This endpoint returns detailed metrics for each interval in an activity, including power, heart rate,
    cadence, speed, and environmental data. It also includes grouped intervals if applicable.

    Args:
        activity_id: The Intervals.icu activity ID
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
    """
    # Call the Intervals.icu API
    result = await make_intervals_request(url=f"/activity/{activity_id}/intervals", api_key=api_key)

    if isinstance(result, dict) and "error" in result:
        error_message = result.get("message", "Unknown error")
        return f"Error fetching intervals: {error_message}"

    # Format the response
    if not result:
        return f"No interval data found for activity {activity_id}."

    # If the result is empty or doesn't contain expected fields
    if not isinstance(result, dict) or not any(
        key in result for key in ["icu_intervals", "icu_groups"]
    ):
        return f"No interval data or unrecognized format for activity {activity_id}."

    # Format the intervals data
    return format_intervals(result)


@mcp.tool()
async def get_races(athlete_id: str | None = None, api_key: str | None = None) -> str:
    """Get events of type race for an athlete from Intervals.icu

    Args:
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
    """
    # Use provided athlete_id or fall back to global ATHLETE_ID
    athlete_id_to_use = athlete_id if athlete_id is not None else ATHLETE_ID
    if not athlete_id_to_use:
        return "Error: No athlete ID provided and no default ATHLETE_ID found in environment variables."

    # Set date parameters
    start_date = datetime.now().strftime("%Y-%m-%d")
    end_date = (datetime.now() + timedelta(days=356)).strftime("%Y-%m-%d")

    # Call the Intervals.icu API
    params = {"oldest": start_date, "newest": end_date}

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/events", api_key=api_key, params=params
    )

    if isinstance(result, dict) and "error" in result:
        error_message = result.get("message", "Unknown error")
        return f"Error fetching events: {error_message}"

    # Format the response
    if not result:
        return f"No events found for athlete {athlete_id_to_use} in the specified date range."

    # Ensure result is a list
    events = result if isinstance(result, list) else []

    if not events:
        return f"No events found for athlete {athlete_id_to_use} in the specified date range."

    races_summary = "Races:\n\n"
    for event in events:
        if not isinstance(event, dict) or not event.get("category", "").startswith(
            "RACE_"
        ):
            continue

        shared_event = None
        if shared_event_id := event.get("shared_event_id"):
            shared_event = await make_intervals_request(
                url=f"/shared-event/{shared_event_id}", api_key=api_key
            )
            assert isinstance(shared_event, dict)
        races_summary += format_event_summary(event, shared_event) + "\n\n\n"

    return races_summary


@mcp.tool()
async def get_power_curves(
    athlete_id: str | None = None,
    api_key: str | None = None,
    curves: str = "42d",
    type_: str = "Ride",
) -> list[dict[str, float]] | str:
    """Get power curves for an athlete from Intervals.icu

    Args:
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
        curves: Comma separated list of curves to return. Default is "1y". Possible values are:
            - 1y (past year)
            - 2y (past 2 years) etc.
            - 42d (past 42 days) etc.
            - s0 (current season)
            - s1 (previous season) etc.
            - all (all time)
            - r.2023-10-01.2023-10-31 (date range)
        type_: The sport (Ride, Run, Swim, etc.)

    Returns:
        List of dictionaries containing power curves for the specified athlete and sport
    """
    # Use provided athlete_id or fall back to global ATHLETE_ID
    athlete_id_to_use = athlete_id if athlete_id is not None else ATHLETE_ID
    if not athlete_id_to_use:
        return "Error: No athlete ID provided and no default ATHLETE_ID found in environment variables."

    # Call the Intervals.icu API
    params = {"curves": curves, "type": type_}

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/power-curves",
        api_key=api_key,
        params=params,
    )

    if isinstance(result, dict) and "error" in result:
        error_message = result.get("message", "Unknown error")
        return f"Error fetching power curves: {error_message}"

    return result["list"] if isinstance(result, dict) and "list" in result else []


@mcp.tool()
async def get_activity_power_curves(
    activity_id: str,
    api_key: str | None = None,
    type_: str = "power",
) -> list[dict[str, float]] | str:
    """Get power curves for a specific activity from Intervals.icu

    Args:
        activity_id: The Intervals.icu activity ID
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
        type_: The curve type. Default is "power". Unsure what possible values are.

    Returns:
        List of dictionaries containing power curve data for the specified activity
    """
    # Validate required activity_id
    if not activity_id:
        return "Error: Activity ID is required."

    # Call the Intervals.icu API
    params = {"type": type_}

    result = await make_intervals_request(
        url=f"/activity/{activity_id}/power-curves", api_key=api_key, params=params
    )

    if isinstance(result, dict) and "error" in result:
        error_message = result.get("message", "Unknown error")
        return f"Error fetching activity power curve: {error_message}"

    return result if isinstance(result, list) else []


@mcp.tool()
async def get_pace_curves(
    athlete_id: str | None = None,
    api_key: str | None = None,
    curves: str = "42d",
    type_: str = "Run",
) -> list[dict[str, float]] | str:
    """Get pace curves for an athlete from Intervals.icu

    Args:
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
        curves: Comma separated list of curves to return. Default is "1y". Possible values are:
            - 1y (past year)
            - 2y (past 2 years) etc.
            - 42d (past 42 days) etc.
            - s0 (current season)
            - s1 (previous season) etc.
            - all (all time)
            - r.2023-10-01.2023-10-31 (date range)
        type_: The sport (Run, Swim, Rowing, etc.)

    Returns:
        List of dictionaries containing pace curves for the specified athlete and sport
    """
    # Use provided athlete_id or fall back to global ATHLETE_ID
    athlete_id_to_use = athlete_id if athlete_id is not None else ATHLETE_ID
    if not athlete_id_to_use:
        return "Error: No athlete ID provided and no default ATHLETE_ID found in environment variables."

    # Call the Intervals.icu API
    params = {"curves": curves, "type": type_}

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/pace-curves",
        api_key=api_key,
        params=params,
    )

    if isinstance(result, dict) and "error" in result:
        error_message = result.get("message", "Unknown error")
        return f"Error fetching pace curves: {error_message}"

    return result["list"] if isinstance(result, dict) and "list" in result else []


@mcp.tool()
async def get_activity_pace_curve(
    activity_id: str,
    api_key: str | None = None,
    gap: bool = False,
) -> dict[str, float] | str:
    """Get activity pace curve in JSON format

    Args:
        activity_id: The Intervals.icu activity ID
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
        gap: Boolean indicating whether to use gradient adjusted pace (default: False)

    Returns:
        Dictionary containing pace curve data for the specified activity
    """
    # Validate required activity_id
    if not activity_id:
        return "Error: Activity ID is required."

    # Set up the parameters
    params = {"gap": gap}

    # Call the Intervals.icu API
    result = await make_intervals_request(
        url=f"/activity/{activity_id}/pace-curve.json",
        api_key=api_key,
        params=params,
    )

    if isinstance(result, dict) and "error" in result:
        error_message = result.get("message", "Unknown error")
        return f"Error fetching activity power curve: {error_message}"

    return result if isinstance(result, dict) else {}


@mcp.tool()
async def get_athlete(
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> dict | str:
    """Get detailed information for an athlete from Intervals.icu

    Args:
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)

    Returns:
        Dictionary containing comprehensive athlete data including sport settings and custom items
    """
    # Use provided athlete_id or fall back to global ATHLETE_ID
    athlete_id_to_use = athlete_id if athlete_id is not None else ATHLETE_ID
    if not athlete_id_to_use:
        return "Error: No athlete ID provided and no default ATHLETE_ID found in environment variables."

    # Call the Intervals.icu API
    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}",
        api_key=api_key,
        params={},
    )

    if isinstance(result, dict) and "error" in result:
        error_message = result.get("message", "Unknown error")
        return f"Error fetching athlete data: {error_message}"

    return result if isinstance(result, dict) else {}


@mcp.tool()
async def get_power_hr_curve(
    athlete_id: str | None = None,
    api_key: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict | str:
    """Get the athlete's power vs heart rate curve for a date range

    Args:
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
        start_date: Starting local date (ISO-8601 format, e.g., '2024-01-01')
        end_date: Ending local date (ISO-8601 format, inclusive, e.g., '2024-12-31')

    Returns:
        Dictionary containing power vs heart rate curve data including:
        - athleteId: The athlete ID
        - start/end: Date range
        - minWatts/maxWatts: Power range
        - bucketSize: Watts per bucket
        - bpm: Array of heart rate values
        - cadence: Array of cadence values
        - minutes: Array of time spent at each power/HR combination
        - lthr: Lactate threshold heart rate
        - max_hr: Maximum heart rate
        - ftp: Functional threshold power
    """
    # Use provided athlete_id or fall back to global ATHLETE_ID
    athlete_id_to_use = athlete_id if athlete_id is not None else ATHLETE_ID
    if not athlete_id_to_use:
        return "Error: No athlete ID provided and no default ATHLETE_ID found in environment variables."

    # Parse date parameters
    if not start_date:
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")

    # Call the Intervals.icu API
    params = {"start": start_date, "end": end_date}

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/power-hr-curve",
        api_key=api_key,
        params=params,
    )

    if isinstance(result, dict) and "error" in result:
        return f"Error fetching power_hr curve: {result.get('message')}"

    return result if isinstance(result, dict) else {}


@mcp.tool()
async def get_activity_power_vs_hr(
    activity_id: str, api_key: str | None = None
) -> dict | str:
    """Get activity power vs heart rate data in JSON format

    Args:
        activity_id: The Intervals.icu activity ID
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)

    Returns:
        Dictionary containing power vs heart rate data for the specified activity including:
        - bucketSize: Watts per bucket for grouping
        - warmup/cooldown: Time periods excluded from analysis
        - elapsedTime: Total activity time
        - hrLag: Heart rate lag in seconds
        - powerHr: Overall power/HR ratio
        - powerHrFirst/powerHrSecond: First/second half ratios
        - decoupling: Cardiac drift percentage
        - powerHrZ2: Power/HR ratio in zone 2
        - medianCadenceZ2/avgCadenceZ2: Cadence metrics for zone 2
        - series: Array of buckets with power, HR, cadence data
        - curves: Fitted curves and trend analysis
    """
    # Validate required activity_id
    if not activity_id:
        return "Error: Activity ID is required."

    # Call the Intervals.icu API
    result = await make_intervals_request(
        url=f"/activity/{activity_id}/power-vs-hr", api_key=api_key
    )

    if isinstance(result, dict) and "error" in result:
        return f"Error fetching activity power vs HR data: {result.get('message')}"

    return result if isinstance(result, dict) else {}


@mcp.tool()
async def get_activity_hr_curve(
    activity_id: str, api_key: str | None = None
) -> dict | str:
    """Get activity heart rate curve in JSON format

    Args:
        activity_id: The Intervals.icu activity ID
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)

    Returns:
        Dictionary containing heart rate curve data for the specified activity including:
        - id: Activity ID
        - filters: Applied filters
        - label: Curve label
        - start_date_local/end_date_local: Activity date
        - secs: Array of durations in seconds
        - values: Array of heart rate values (BPM)
        - activity_id: Array of activity IDs for each point
        - start_index/end_index: Stream indexes for each effort
        - submax_values: Submaximal efforts data
        - And other curve metadata
    """
    # Validate required activity_id
    if not activity_id:
        return "Error: Activity ID is required."

    # Call the Intervals.icu API
    result = await make_intervals_request(
        url=f"/activity/{activity_id}/hr-curve.json", api_key=api_key
    )

    if isinstance(result, dict) and "error" in result:
        return f"Error fetching activity HR curve: {result.get('message')}"

    return result if isinstance(result, dict) else {}


@mcp.tool()
async def get_current_date_info() -> dict[str, Any]:
    """Get current date and time information

    Returns comprehensive information about the current date including
    day of week, week number, and relative day calculations.

    Returns:
        Dictionary containing current date information:
        - current_date: ISO format date (YYYY-MM-DD)
        - day_of_week: Full day name (e.g., "Sunday")
        - week_number: ISO week number (1-53)
        - days_until_weekend: Days until Saturday (0-6)
        - is_weekend: Whether today is Saturday or Sunday
        - year: Current year
        - month: Current month (1-12)
        - day: Current day of month (1-31)
    """
    from datetime import datetime

    now = datetime.now()

    # Calculate days until weekend (Saturday = 5, Sunday = 6 in weekday())
    # weekday(): Monday=0, Tuesday=1, ..., Sunday=6
    current_weekday = now.weekday()  # 0=Monday, 6=Sunday
    days_until_saturday = (5 - current_weekday) % 7  # Saturday is weekday 5

    return {
        "current_date": now.strftime("%Y-%m-%d"),
        "day_of_week": now.strftime("%A"),
        "week_number": int(now.strftime("%W")),  # ISO week number
        "days_until_weekend": days_until_saturday,
        "is_weekend": current_weekday in [5, 6],  # Saturday=5, Sunday=6
        "year": now.year,
        "month": now.month,
        "day": now.day,
    }


@mcp.tool()
async def get_workout_format_examples() -> str:
    """Get workout format examples for creating structured workout descriptions

    This tool returns the contents of workout_samples.md which contains examples
    of how to format workout descriptions in the native Intervals.icu format.
    Use this to understand the proper syntax for power zones, pace zones,
    percentages, intervals, and time/distance formats.

    Returns:
        String containing workout format examples and explanations
    """
    try:
        import os

        # Get the path to workout_samples.md relative to this file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(current_dir))
        workout_samples_path = os.path.join(project_root, "workout_samples.md")

        with open(workout_samples_path, "r", encoding="utf-8") as f:
            content = f.read()

        return content
    except FileNotFoundError:
        return (
            "Error: workout_samples.md file not found. Please ensure the file exists in the project root."
        )
    except Exception as e:
        return f"Error reading workout_samples.md: {str(e)}"


@mcp.tool()
async def create_workout(
    name: str,
    description: str,
    date: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
    category: str = "WORKOUT",
    workout_type: str = "Ride",
    indoor: bool | None = None,
    moving_time: int | None = None,
    color: str | None = None,
) -> str:
    """Create a workout event on an athlete's Intervals.icu calendar

    This tool creates a workout event with a structured description using the native
    Intervals.icu workout format.

    Args:
        name: The name/title of the workout
        description: The workout description in Intervals.icu format
        date: The date for the workout in YYYY-MM-DD format (local date)
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
        category: The event category (default: "WORKOUT", options: WORKOUT, RACE_A, RACE_B, RACE_C, NOTE, HOLIDAY, SICK, INJURED, SET_EFTP, FITNESS_DAYS, SEASON_START, TARGET, SET_FITNESS)
        workout_type: The activity type for the workout (default: "Ride", options: Ride, Run, Swim, OpenWaterSwim, etc.)
        indoor: Whether the workout is intended to be done indoors (optional)
        moving_time: Expected moving time in seconds (optional)
        color: Hex color code for the event (optional, e.g., "#FF0000")

    Returns:
        Success message with the created event ID or error message
    """
    # Use provided athlete_id or fall back to global ATHLETE_ID
    athlete_id_to_use = athlete_id if athlete_id is not None else ATHLETE_ID
    if not athlete_id_to_use:
        return "Error: No athlete ID provided and no default ATHLETE_ID found in environment variables."

    # Validate date format
    try:
        from datetime import datetime

        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        return "Error: Date must be in YYYY-MM-DD format."

    # Validate category
    valid_categories = [
        "WORKOUT",
        "RACE_A",
        "RACE_B",
        "RACE_C",
        "NOTE",
        "HOLIDAY",
        "SICK",
        "INJURED",
        "SET_EFTP",
        "FITNESS_DAYS",
        "SEASON_START",
        "TARGET",
        "SET_FITNESS",
    ]
    if category not in valid_categories:
        return f"Error: Invalid category. Must be one of: {', '.join(valid_categories)}"

    # Build the event data with proper date format
    # Convert YYYY-MM-DD to YYYY-MM-DDTHH:MM:SS format
    if len(date) == 10:  # YYYY-MM-DD format
        formatted_date = f"{date}T00:00:00"
    else:
        formatted_date = date

    event_data = {
        "start_date_local": formatted_date,
        "name": name,
        "description": description,
        "category": category,
        "type": workout_type,
    }

    # Add optional fields if provided
    if indoor is not None:
        event_data["indoor"] = indoor
    if moving_time is not None:
        event_data["moving_time"] = moving_time
    if color is not None:
        if not color.startswith("#") or len(color) != 7:
            return "Error: Color must be a hex color code like #FF0000"
        event_data["color"] = color

    # Call the Intervals.icu API
    result = await make_intervals_post_request(
        url=f"/athlete/{athlete_id_to_use}/events", data=event_data, api_key=api_key
    )

    if isinstance(result, dict) and "error" in result:
        error_message = result.get("message", "Unknown error")
        return f"Error creating workout: {error_message}"

    # Check if we got a valid response
    if isinstance(result, dict) and "id" in result:
        event_id = result["id"]
        return f"Successfully created workout '{name}' on {date} (Event ID: {event_id})"
    else:
        return "Workout created but response format was unexpected."


# Run the server
if __name__ == "__main__":
    mcp.run()
