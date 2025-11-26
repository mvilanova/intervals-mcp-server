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

from enum import StrEnum
from json import JSONDecodeError
import logging
import os
import re
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from http import HTTPStatus
from typing import Any
import json

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

from intervals_mcp_server.utils.types import WorkoutDoc

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

# Create a single AsyncClient instance for all requests (lazily initialized)
httpx_client: httpx.AsyncClient | None = None


async def _get_httpx_client() -> httpx.AsyncClient:
    """
    Lazily create or reuse the shared httpx AsyncClient.

    The client may be closed by downstream transports between tool invocations,
    so we recreate it when necessary.
    """
    global httpx_client  # noqa: PLW0603 - we intentionally manage the shared client here
    if httpx_client is None or httpx_client.is_closed:
        httpx_client = httpx.AsyncClient()
    return httpx_client


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
        if httpx_client and not httpx_client.is_closed:
            await httpx_client.aclose()


# Initialize FastMCP server with custom lifespan
mcp = FastMCP("intervals-icu", lifespan=lifespan)

# Constants
INTERVALS_API_BASE_URL = os.getenv("INTERVALS_API_BASE_URL", "https://intervals.icu/api/v1")
API_KEY = os.getenv("API_KEY", "")  # Provide default empty string
ATHLETE_ID = os.getenv("ATHLETE_ID", "")  # Default athlete ID from .env
USER_AGENT = "intervalsicu-mcp-server/1.0"

# Accept athlete IDs that are either all digits or start with 'i' followed by digits
if not re.fullmatch(r"i?\d+", ATHLETE_ID):
    raise ValueError(
        "ATHLETE_ID must be all digits (e.g. 123456) or start with 'i' followed by digits (e.g. i123456)"
    )


def validate_date(date_str: str) -> str:
    """Validate that a date string is in YYYY-MM-DD format.

    Args:
        date_str: The date string to validate.

    Returns:
        The validated date string if valid.

    Raises:
        ValueError: If the date string is not in YYYY-MM-DD format.
    """
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return date_str
    except ValueError as exc:
        raise ValueError("Invalid date format. Please use YYYY-MM-DD.") from exc


def _get_error_message(error_code: int, error_text: str) -> str:
    """Return a user-friendly error message for a given HTTP status code."""
    error_messages = {
        HTTPStatus.UNAUTHORIZED: f"{HTTPStatus.UNAUTHORIZED.value} {HTTPStatus.UNAUTHORIZED.phrase}: Please check your API key.",
        HTTPStatus.FORBIDDEN: f"{HTTPStatus.FORBIDDEN.value} {HTTPStatus.FORBIDDEN.phrase}: You may not have permission to access this resource.",
        HTTPStatus.NOT_FOUND: f"{HTTPStatus.NOT_FOUND.value} {HTTPStatus.NOT_FOUND.phrase}: The requested endpoint or ID doesn't exist.",
        HTTPStatus.UNPROCESSABLE_ENTITY: f"{HTTPStatus.UNPROCESSABLE_ENTITY.value} {HTTPStatus.UNPROCESSABLE_ENTITY.phrase}: The server couldn't process the request (invalid parameters or unsupported operation).",
        HTTPStatus.TOO_MANY_REQUESTS: f"{HTTPStatus.TOO_MANY_REQUESTS.value} {HTTPStatus.TOO_MANY_REQUESTS.phrase}: Too many requests in a short time period.",
        HTTPStatus.INTERNAL_SERVER_ERROR: f"{HTTPStatus.INTERNAL_SERVER_ERROR.value} {HTTPStatus.INTERNAL_SERVER_ERROR.phrase}: The Intervals.icu server encountered an internal error.",
        HTTPStatus.SERVICE_UNAVAILABLE: f"{HTTPStatus.SERVICE_UNAVAILABLE.value} {HTTPStatus.SERVICE_UNAVAILABLE.phrase}: The Intervals.icu server might be down or undergoing maintenance.",
    }
    try:
        status = HTTPStatus(error_code)
        return error_messages.get(status, error_text)
    except ValueError:
        return error_text


async def make_intervals_request(
    url: str,
    api_key: str | None = None,
    params: dict[str, Any] | None = None,
    method: str = "GET",
    data: dict[str, Any] | None = None,
) -> dict[str, Any] | list[dict[str, Any]]:
    """
    Make a request to the Intervals.icu API with proper error handling.

    Args:
        url (str): The API endpoint path (e.g., '/athlete/{id}/activities').
        api_key (str | None): Optional API key to use for authentication. Defaults to the global API_KEY.
        params (dict[str, Any] | None): Optional query parameters for the request.
        method (str): HTTP method to use (GET, POST, etc.). Defaults to GET.
        data (dict[str, Any] | None): Optional data to send in the request body.

    Returns:
        dict[str, Any] | list[dict[str, Any]]: The parsed JSON response from the API, or an error dict.
    """
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}

    if method in ["POST", "PUT"]:
        headers["Content-Type"] = "application/json"

    # Use provided api_key or fall back to global API_KEY
    key_to_use = api_key if api_key is not None else API_KEY
    if not key_to_use:
        logger.error("No API key provided for request to: %s", url)
        return {
            "error": True,
            "message": "API key is required. Set API_KEY env var or pass api_key",
        }

    auth = httpx.BasicAuth("API_KEY", key_to_use)
    full_url = f"{INTERVALS_API_BASE_URL}{url}"

    async def _send_request(client: httpx.AsyncClient) -> httpx.Response:
        if method in {"POST", "PUT"} and data is not None:
            return await client.request(
                method=method,
                url=full_url,
                headers=headers,
                params=params,
                auth=auth,
                timeout=30.0,
                content=json.dumps(data),
            )
        return await client.request(
            method=method,
            url=full_url,
            headers=headers,
            params=params,
            auth=auth,
            timeout=30.0,
        )

    try:
        client = await _get_httpx_client()

        try:
            response = await _send_request(client)
        except RuntimeError as runtime_error:
            # httpx closes the client when the underlying connection is severed;
            # recreate the shared client lazily and retry once.
            if "client has been closed" not in str(runtime_error).lower():
                raise
            logger.warning("HTTPX client was closed; creating a new instance for retries.")
            global httpx_client  # noqa: PLW0603 - we intentionally manage the shared client here
            httpx_client = None
            client = await _get_httpx_client()
            response = await _send_request(client)

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

        return {
            "error": True,
            "status_code": error_code,
            "message": _get_error_message(error_code, error_text),
        }
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
async def get_activity_streams(
    activity_id: str,
    api_key: str | None = None,
    stream_types: str | None = None,
) -> str:
    """Get stream data for a specific activity from Intervals.icu

    This endpoint returns time-series data for an activity, including metrics like power, heart rate,
    cadence, altitude, distance, temperature, and velocity data.

    Args:
        activity_id: The Intervals.icu activity ID
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
        stream_types: Comma-separated list of stream types to retrieve (optional, defaults to all available types)
                     Available types: time, watts, heartrate, cadence, altitude, distance,
                     core_temperature, skin_temperature, velocity_smooth
    """
    # Build query parameters
    params = {}
    if stream_types:
        params["types"] = stream_types
    else:
        # Default to common stream types if none specified
        params["types"] = "time,watts,heartrate,cadence,altitude,distance,velocity_smooth"

    # Call the Intervals.icu API
    result = await make_intervals_request(
        url=f"/activity/{activity_id}/streams",
        api_key=api_key,
        params=params,
    )

    if isinstance(result, dict) and "error" in result:
        error_message = result.get("message", "Unknown error")
        return f"Error fetching activity streams: {error_message}"

    # Format the response
    if not result:
        return f"No stream data found for activity {activity_id}."

    # Ensure result is a list
    streams = result if isinstance(result, list) else []

    if not streams:
        return f"No stream data found for activity {activity_id}."

    # Format the streams data
    streams_summary = f"Activity Streams for {activity_id}:\n\n"

    for stream in streams:
        if not isinstance(stream, dict):
            continue

        stream_type = stream.get("type", "unknown")
        stream_name = stream.get("name", stream_type)
        data = stream.get("data", [])
        value_type = stream.get("valueType", "")

        streams_summary += f"Stream: {stream_name} ({stream_type})\n"
        streams_summary += f"  Value Type: {value_type}\n"
        streams_summary += f"  Data Points: {len(data)}\n"

        # Show first few and last few data points for preview
        if data:
            if len(data) <= 10:
                streams_summary += f"  Values: {data}\n"
            else:
                preview_start = data[:5]
                preview_end = data[-5:]
                streams_summary += f"  First 5 values: {preview_start}\n"
                streams_summary += f"  Last 5 values: {preview_end}\n"

        streams_summary += "\n"

    return streams_summary


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
            # Add the date to the data dictionary if it's not already present
            if isinstance(data, dict) and "date" not in data:
                data["date"] = date_str
            wellness_summary += format_wellness_entry(data) + "\n\n"
    elif isinstance(result, list):
        for entry in result:
            if isinstance(entry, dict):
                wellness_summary += format_wellness_entry(entry) + "\n\n"

    return wellness_summary


def _resolve_workout_type(name: str | None, workout_type: str | None) -> str:
    """Determine the workout type based on the name and provided value."""
    if workout_type:
        return workout_type
    name_lower = name.lower() if name else ""
    mapping = [
        ("Ride", ["bike", "cycle", "cycling", "ride"]),
        ("Run", ["run", "running", "jog", "jogging"]),
        ("Swim", ["swim", "swimming", "pool"]),
        ("Walk", ["walk", "walking", "hike", "hiking"]),
        ("Row", ["row", "rowing"]),
    ]
    for workout, keywords in mapping:
        if any(keyword in name_lower for keyword in keywords):
            return workout
    return "Ride"  # Default


def _prepare_event_data(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    name: str,
    workout_type: str,
    start_date: str,
    workout_doc: WorkoutDoc | None,
    moving_time: int | None,
    distance: int | None,
) -> dict[str, Any]:
    """Prepare event data dictionary for API request.

    Many arguments are required to match the Intervals.icu API event structure.
    """
    resolved_workout_type = _resolve_workout_type(name, workout_type)
    return {
        "start_date_local": start_date + "T00:00:00",
        "category": "WORKOUT",
        "name": name,
        "description": str(workout_doc) if workout_doc else None,
        "type": resolved_workout_type,
        "moving_time": moving_time,
        "distance": distance,
    }


def _handle_event_response(
    result: dict[str, Any] | list[dict[str, Any]] | None,
    action: str,
    athlete_id: str,
    start_date: str,
) -> str:
    """Handle API response and format appropriate message."""
    if isinstance(result, dict) and "error" in result:
        error_message = result.get("message", "Unknown error")
        return f"Error {action} event: {error_message}"
    if not result:
        return f"No events {action} for athlete {athlete_id}."
    if isinstance(result, dict):
        return f"Successfully {action} event: {json.dumps(result, indent=2)}"
    return f"Event {action} successfully at {start_date}"


@mcp.tool()
async def delete_event(
    event_id: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Delete event for an athlete from Intervals.icu
    Args:
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
        event_id: The Intervals.icu event ID
    """
    athlete_id_to_use = athlete_id if athlete_id is not None else ATHLETE_ID
    if not athlete_id_to_use:
        return "Error: No athlete ID provided and no default ATHLETE_ID found in environment variables."
    if not event_id:
        return "Error: No event ID provided."
    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/events/{event_id}", api_key=api_key, method="DELETE"
    )
    if isinstance(result, dict) and "error" in result:
        return f"Error deleting event: {result.get('message')}"
    return json.dumps(result, indent=2)


@mcp.tool()
async def delete_events_by_date_range(
    start_date: str,
    end_date: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Delete events for an athlete from Intervals.icu in the specified date range.

    Args:
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
    """
    athlete_id_to_use = athlete_id if athlete_id is not None else ATHLETE_ID
    if not athlete_id_to_use:
        return "Error: No athlete ID provided and no default ATHLETE_ID found in environment variables."
    params = {"oldest": validate_date(start_date), "newest": validate_date(end_date)}
    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/events", api_key=api_key, params=params
    )
    if isinstance(result, dict) and "error" in result:
        return f"Error deleting events: {result.get('message')}"
    events = result if isinstance(result, list) else []
    failed_events = []
    for event in events:
        result = await make_intervals_request(
            url=f"/athlete/{athlete_id_to_use}/events/{event.get('id')}",
            api_key=api_key,
            method="DELETE",
        )
        if isinstance(result, dict) and "error" in result:
            failed_events.append(event.get("id"))
    return f"Deleted {len(events) - len(failed_events)} events. Failed to delete {len(failed_events)} events: {failed_events}"


@mcp.tool()
async def add_or_update_event(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    workout_type: str,
    name: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
    event_id: str | None = None,
    start_date: str | None = None,
    workout_doc: WorkoutDoc | None = None,
    moving_time: int | None = None,
    distance: int | None = None,
) -> str:
    """Post event for an athlete to Intervals.icu this follows the event api from intervals.icu
    If event_id is provided, the event will be updated instead of created.

    Many arguments are required as this MCP tool function maps directly to the Intervals.icu API parameters.

    Args:
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
        event_id: The Intervals.icu event ID (optional, will use event_id from .env if not provided)
        start_date: Start date in YYYY-MM-DD format (optional, defaults to today)
        name: Name of the activity
        workout_doc: steps as a list of Step objects (optional, but necessary to define workout steps)
        workout_type: Workout type (e.g. Ride, Run, Swim, Walk, Row)
        moving_time: Total expected moving time of the workout in seconds (optional)
        distance: Total expected distance of the workout in meters (optional)

    Example:
        "workout_doc": {
            "description": "High-intensity workout for increasing VO2 max",
            "steps": [
                {"power": {"value": "80", "units": "%ftp"}, "duration": "900", "warmup": true},
                {"reps": 2, "text": "High-intensity intervals", "steps": [
                    {"power": {"value": "110", "units": "%ftp"}, "distance": "500", "text": "High-intensity"},
                    {"power": {"value": "80", "units": "%ftp"}, "duration": "90", "text": "Recovery"}
                ]},
                {"power": {"value": "80", "units": "%ftp"}, "duration": "600", "cooldown": true}
                {"text": ""}, # Add comments or blank lines for readability
            ]
        }

    Step properties:
        distance: Distance of step in meters
            {"distance": "5000"}
        duration: Duration of step in seconds
            {"duration": "1800"}
        power/hr/pace/cadence: Define step intensity
            Percentage of FTP: {"power": {"value": "80", "units": "%ftp"}}
            Absolute power: {"power": {"value": "200", "units": "w"}}
            Heart rate: {"hr": {"value": "75", "units": "%hr"}}
            Heart rate (LTHR): {"hr": {"value": "85", "units": "%lthr"}}
            Cadence: {"cadence": {"value": "90", "units": "rpm"}}
            Pace by ftp: {"pace": {"value": "80", "units": "%pace"}}
            Pace by zone: {"pace": {"value": "Z2", "units": "pace_zone"}}
            Zone by power: {"power": {"value": "Z2", "units": "power_zone"}}
            Zone by heart rate: {"hr": {"value": "Z2", "units": "hr_zone"}}
        Ranges: Specify ranges for power, heart rate, or cadence:
            {"power": {"start": "80", "end": "90", "units": "%ftp"}}
        Ramps: Instead of a range, indicate a gradual change in intensity (useful for ERG workouts):
            {"ramp": True, "power": {"start": "80", "end": "90", "units": "%ftp"}}
        Repeats: include the reps property and add nested steps
            {"reps": 3,
            "steps": [
                {"power": {"value": "110", "units": "%ftp"}, "distance": "500", "text": "High-intensity"},
                {"power": {"value": "80", "units": "%ftp"}, "duration": "90", "text": "Recovery"}
            ]}
        Free Ride: Include free to indicate a segment without ERG control, optionally with a suggested power range:
            {"free": true, "power": {"value": "80", "units": "%ftp"}}
        Comments and Labels: Add descriptive text to label steps:
            {"text": "Warmup"}

    How to use steps:
        - Set distance or duration as appropriate for step
        - Use "reps" with nested steps to define repeat intervals (as in example above)
        - Define one of "power", "hr" or "pace" to define step intensity
    """
    athlete_id_to_use = athlete_id if athlete_id is not None else ATHLETE_ID
    if not athlete_id_to_use:
        return "Error: No athlete ID provided and no default ATHLETE_ID found in environment variables."

    if not start_date:
        start_date = datetime.now().strftime("%Y-%m-%d")

    try:
        data = _prepare_event_data(
            name, workout_type, start_date, workout_doc, moving_time, distance
        )
        url = f"/athlete/{athlete_id_to_use}/events"
        if event_id:
            url += f"/{event_id}"
        result = await make_intervals_request(
            url=url,
            api_key=api_key,
            data=data,
            method="PUT" if event_id else "POST",
        )
        action = "updated" if event_id else "created"
        return _handle_event_response(result, action, athlete_id_to_use, start_date)
    except ValueError as e:
        return f"Error: {e}"


# Run the server
class TransportAliases(StrEnum):
    STDIO = "stdio"
    SSE = "sse"
    HTTP = "http"
    STREAMABLE_HTTP = "streamable-http"

if __name__ == "__main__":
    transport_env = os.getenv("MCP_TRANSPORT", TransportAliases.STDIO).lower()
    try:
        transport_alias = TransportAliases(transport_env)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in TransportAliases)
        raise ValueError(f"Unsupported MCP_TRANSPORT value. Use one of: {allowed}.") from exc

    selected_transport = (
        TransportAliases.STREAMABLE_HTTP if transport_alias == TransportAliases.HTTP else transport_alias
    )
    host = mcp.settings.host
    port = mcp.settings.port

    if selected_transport == TransportAliases.STDIO:
        logger.info("Starting MCP server with stdio transport.")
        mcp.run()
    elif selected_transport == TransportAliases.SSE:
        mount_path = os.getenv("MCP_SSE_MOUNT_PATH")
        logger.info(
            "Starting MCP server with SSE transport at http://%s:%s%s (messages: %s).",
            host,
            port,
            mcp.settings.sse_path,
            mcp.settings.message_path,
        )
        mcp.run(transport="sse", mount_path=mount_path)
    else:  # STREAMABLE_HTTP
        logger.info(
            "Starting MCP server with Streamable HTTP transport at http://%s:%s%s.",
            host,
            port,
            mcp.settings.streamable_http_path,
        )
        mcp.run(transport="streamable-http")
