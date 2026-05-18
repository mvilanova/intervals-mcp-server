"""
Activity-related MCP tools for Intervals.icu.

This module contains tools for retrieving and managing athlete activities.
"""

from typing import Any

from intervals_mcp_server.utils.formatting import (
    format_activity_message,
    format_activity_summary,
    format_intervals,
)
from intervals_mcp_server.utils.validation import resolve_date_params
from intervals_mcp_server.tools.common import format_tool_error, is_error_result, resolve_tool_context
import intervals_mcp_server.services.activities as activities_service

# Import mcp instance from shared module for tool registration
from intervals_mcp_server.mcp_instance import mcp  # noqa: F401


def _format_activities_response(
    activities: list[dict[str, Any]],
    athlete_id: str,
    include_unnamed: bool,
) -> str:
    if not activities:
        if include_unnamed:
            return f"No valid activities found for athlete {athlete_id} in the specified date range."
        return f"No named activities found for athlete {athlete_id} in the specified date range. Try with include_unnamed=True to see all activities."
    activities_summary = "Activities:\n\n"
    for activity in activities:
        if isinstance(activity, dict):
            activities_summary += format_activity_summary(activity) + "\n"
        else:
            activities_summary += f"Invalid activity format: {activity}\n\n"
    return activities_summary


@mcp.tool()
async def get_activities(  # pylint: disable=too-many-arguments,too-many-positional-arguments
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
    athlete_id_to_use, api_key, error_msg = resolve_tool_context(athlete_id, api_key)
    if error_msg:
        return error_msg

    start_date, end_date = resolve_date_params(start_date, end_date)

    result = await activities_service.list_activities(
        athlete_id_to_use, api_key, start_date, end_date, limit, include_unnamed
    )
    if is_error_result(result):
        return format_tool_error("fetching activities", result)

    activities: list[dict[str, Any]] = result if isinstance(result, list) else []
    return _format_activities_response(activities, athlete_id_to_use, include_unnamed)


@mcp.tool()
async def get_activity_details(activity_id: str, api_key: str | None = None) -> str:
    """Get detailed information for a specific activity from Intervals.icu

    Args:
        activity_id: The Intervals.icu activity ID
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
    """
    result = await activities_service.get_activity(activity_id, api_key)

    if is_error_result(result):
        return format_tool_error("fetching activity details", result)

    if not result:
        return f"No details found for activity {activity_id}."

    activity_data = result[0] if isinstance(result, list) and result else result
    if not isinstance(activity_data, dict):
        return f"Invalid activity format for activity {activity_id}."

    detailed_view = format_activity_summary(activity_data)

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
    result = await activities_service.get_intervals(activity_id, api_key)

    if is_error_result(result):
        return format_tool_error("fetching intervals", result)

    if not result:
        return f"No interval data found for activity {activity_id}."

    if not isinstance(result, dict) or not any(
        key in result for key in ["icu_intervals", "icu_groups"]
    ):
        return f"No interval data or unrecognized format for activity {activity_id}."

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
    result = await activities_service.get_streams(activity_id, api_key, stream_types)

    if is_error_result(result):
        return format_tool_error("fetching activity streams", result)

    if not result:
        return f"No stream data found for activity {activity_id}."

    streams = result if isinstance(result, list) else []
    if not streams:
        return f"No stream data found for activity {activity_id}."

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
        if data:
            if len(data) <= 10:
                streams_summary += f"  Values: {data}\n"
            else:
                streams_summary += f"  First 5 values: {data[:5]}\n"
                streams_summary += f"  Last 5 values: {data[-5:]}\n"
        streams_summary += "\n"

    return streams_summary


@mcp.tool()
async def get_activity_messages(activity_id: str, api_key: str | None = None) -> str:
    """Get messages (notes/comments) for a specific activity from Intervals.icu

    Args:
        activity_id: The Intervals.icu activity ID
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
    """
    result = await activities_service.get_messages(activity_id, api_key)

    if is_error_result(result):
        return format_tool_error("fetching activity messages", result)

    if not result:
        return f"No messages found for activity {activity_id}."

    messages = result if isinstance(result, list) else []
    if not messages:
        return f"No messages found for activity {activity_id}."

    output = f"Messages for activity {activity_id}:\n\n"
    for msg in messages:
        if isinstance(msg, dict):
            output += format_activity_message(msg) + "\n\n"
    return output


@mcp.tool()
async def add_activity_message(
    activity_id: str,
    content: str,
    api_key: str | None = None,
) -> str:
    """Add a message (note/comment) to an activity on Intervals.icu

    Args:
        activity_id: The Intervals.icu activity ID
        content: The message text to add
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
    """
    result = await activities_service.post_message(activity_id, api_key, content)

    if is_error_result(result):
        return format_tool_error("adding message to activity", result)

    if not result or not isinstance(result, dict):
        return "Error: Unexpected response when adding message."

    msg_id = result.get("id")
    if msg_id is not None:
        return f"Successfully added message (ID: {msg_id}) to activity {activity_id}."
    return f"Message appears to have been added to activity {activity_id}, but no ID was returned. Please verify manually."
