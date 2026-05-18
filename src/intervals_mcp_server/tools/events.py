"""
Event-related MCP tools for Intervals.icu.

This module contains tools for retrieving, creating, updating, and deleting athlete events.
"""

import json
from datetime import datetime
from typing import Any

from intervals_mcp_server.utils.dates import get_default_end_date, get_default_future_end_date
from intervals_mcp_server.utils.formatting import format_event_details, format_event_summary
from intervals_mcp_server.utils.types import WorkoutDoc
from intervals_mcp_server.tools.common import format_tool_error, is_error_result, resolve_tool_context
import intervals_mcp_server.services.events as events_service

# Import mcp instance from shared module for tool registration
from intervals_mcp_server.mcp_instance import mcp  # noqa: F401


def _handle_event_response(
    result: dict[str, Any] | list[dict[str, Any]] | None,
    action: str,
    athlete_id: str,
    start_date: str,
) -> str:
    if is_error_result(result):
        return format_tool_error(f"{action} event", result)
    if not result:
        return f"No events {action} for athlete {athlete_id}."
    if isinstance(result, dict):
        return f"Successfully {action} event id: {result.get('id')}"
    return f"Event {action} successfully at {start_date}"


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
    athlete_id_to_use, api_key, error_msg = resolve_tool_context(athlete_id, api_key)
    if error_msg:
        return error_msg

    if not start_date:
        start_date = get_default_end_date()
    if not end_date:
        end_date = get_default_future_end_date()

    result = await events_service.list_events(athlete_id_to_use, api_key, start_date, end_date)

    if is_error_result(result):
        return format_tool_error("fetching events", result)

    if not result:
        return f"No events found for athlete {athlete_id_to_use} in the specified date range."

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
    athlete_id_to_use, api_key, error_msg = resolve_tool_context(athlete_id, api_key)
    if error_msg:
        return error_msg

    result = await events_service.get_event(event_id, athlete_id_to_use, api_key)

    if is_error_result(result):
        return format_tool_error("fetching event details", result)

    if not result:
        return f"No details found for event {event_id}."

    if not isinstance(result, dict):
        return f"Invalid event format for event {event_id}."

    return format_event_details(result)


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
    athlete_id_to_use, api_key, error_msg = resolve_tool_context(athlete_id, api_key)
    if error_msg:
        return error_msg
    if not event_id:
        return "Error: No event ID provided."
    result = await events_service.delete_single_event(event_id, athlete_id_to_use, api_key)
    if is_error_result(result):
        return format_tool_error("deleting event", result)
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
    athlete_id_to_use, api_key, error_msg = resolve_tool_context(athlete_id, api_key)
    if error_msg:
        return error_msg

    result = await events_service.delete_events_in_range(
        athlete_id_to_use, api_key, start_date, end_date
    )
    if is_error_result(result):
        return format_tool_error("deleting events", result)

    deleted_count, failed_events = result  # type: ignore[misc]
    return f"Deleted {deleted_count} events. Failed to delete {len(failed_events)} events: {failed_events}"


@mcp.tool()
async def add_or_update_event(  # noqa: PLR0913 — MCP tool maps directly to Intervals.icu API parameters
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
                {"power": {"value": 80, "units": "%ftp"}, "duration": 900, "warmup": true},
                {"reps": 2, "text": "High-intensity intervals", "steps": [
                    {"power": {"value": 110, "units": "%ftp"}, "distance": 500, "text": "High-intensity"},
                    {"power": {"value": 80, "units": "%ftp"}, "duration": 90, "text": "Recovery"}
                ]},
                {"power": {"value": 80, "units": "%ftp"}, "duration": 600, "cooldown": true},
                {"text": ""}
            ]
        }

    Step properties:
        distance: Distance of step in meters
            {"distance": 5000}
        duration: Duration of step in seconds
            {"duration": 1800}
        power/hr/pace/cadence: Define step intensity
            Percentage of FTP: {"power": {"value": 80, "units": "%ftp"}}
            Absolute power: {"power": {"value": 200, "units": "w"}}
            Heart rate: {"hr": {"value": 75, "units": "%hr"}}
            Heart rate (LTHR): {"hr": {"value": 85, "units": "%lthr"}}
            Cadence: {"cadence": {"value": 90, "units": "cadence"}}
            Pace by ftp: {"pace": {"value": 80, "units": "%pace"}}
            Pace by zone: {"pace": {"value": 2, "units": "pace_zone"}}
            Zone by power: {"power": {"value": 2, "units": "power_zone"}}
            Zone by heart rate: {"hr": {"value": 2, "units": "hr_zone"}}
        Ranges: Specify ranges for power, heart rate, or cadence:
            {"power": {"start": 80, "end": 90, "units": "%ftp"}}
        Ramps: Instead of a range, indicate a gradual change in intensity (useful for ERG workouts):
            {"ramp": true, "power": {"start": 80, "end": 90, "units": "%ftp"}}
        Repeats: include the reps property and add nested steps
            {"reps": 3,
            "steps": [
                {"power": {"value": 110, "units": "%ftp"}, "distance": 500, "text": "High-intensity"},
                {"power": {"value": 80, "units": "%ftp"}, "duration": 90, "text": "Recovery"}
            ]}
        Free Ride: Include freeride to indicate a segment without ERG control, optionally with a suggested power range:
            {"freeride": true, "power": {"value": 80, "units": "%ftp"}}
        Comments and Labels: Add descriptive text to label steps:
            {"text": "Warmup"}

    How to use steps:
        - Set distance or duration as appropriate for step
        - Use "reps" with nested steps to define repeat intervals (as in example above)
        - Define one of "power", "hr" or "pace" to define step intensity
    """
    athlete_id_to_use, api_key, error_msg = resolve_tool_context(athlete_id, api_key)
    if error_msg:
        return error_msg

    if not start_date:
        start_date = datetime.now().strftime("%Y-%m-%d")

    try:
        event_data = events_service.prepare_event_data(
            name, workout_type, start_date, workout_doc, moving_time, distance
        )
        result = await events_service.create_or_update_event(
            athlete_id_to_use, api_key, event_data, event_id
        )
        action = "updated" if event_id else "created"
        return _handle_event_response(result, action, athlete_id_to_use, start_date)
    except ValueError as e:
        return f"Error: {e}"
