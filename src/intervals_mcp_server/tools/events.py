"""
Event-related MCP tools for Intervals.icu.

This module contains tools for retrieving, creating, updating, and deleting athlete events.
"""

import json
from datetime import datetime
from typing import Any

from intervals_mcp_server.api.client import make_intervals_request
from intervals_mcp_server.config import get_config
from intervals_mcp_server.utils.dates import get_default_end_date, get_default_future_end_date
from intervals_mcp_server.utils.formatting import format_event_details, format_event_summary
from intervals_mcp_server.utils.types import WorkoutDoc
from intervals_mcp_server.utils.validation import resolve_athlete_id, validate_date

# Import mcp instance from shared module for tool registration
from intervals_mcp_server.mcp_instance import mcp  # noqa: F401

config = get_config()


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


async def _delete_events_list(
    athlete_id: str, api_key: str | None, events: list[dict[str, Any]]
) -> list[str]:
    """Delete a list of events and return IDs of failed deletions.

    Args:
        athlete_id: The athlete ID.
        api_key: Optional API key.
        events: List of event dictionaries to delete.

    Returns:
        List of event IDs that failed to delete.
    """
    failed_events = []
    for event in events:
        result = await make_intervals_request(
            url=f"/athlete/{athlete_id}/events/{event.get('id')}",
            api_key=api_key,
            method="DELETE",
        )
        if isinstance(result, dict) and "error" in result:
            failed_events.append(event.get("id"))
    return failed_events


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
    # Resolve athlete ID
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    # Parse date parameters (events use different defaults)
    if not start_date:
        start_date = get_default_end_date()
    if not end_date:
        end_date = get_default_future_end_date()

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
    # Resolve athlete ID
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

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
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if not event_id:
        return "Error: No event ID provided."
    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/events/{event_id}", api_key=api_key, method="DELETE"
    )
    if isinstance(result, dict) and "error" in result:
        return f"Error deleting event: {result.get('message')}"
    return json.dumps(result, indent=2)


async def _fetch_events_for_deletion(
    athlete_id: str, api_key: str | None, start_date: str, end_date: str
) -> tuple[list[dict[str, Any]], str | None]:
    """Fetch events for deletion and return them with any error message.

    Args:
        athlete_id: The athlete ID.
        api_key: Optional API key.
        start_date: Start date in YYYY-MM-DD format.
        end_date: End date in YYYY-MM-DD format.

    Returns:
        Tuple of (events_list, error_message). error_message is None if successful.
    """
    params = {"oldest": validate_date(start_date), "newest": validate_date(end_date)}
    result = await make_intervals_request(
        url=f"/athlete/{athlete_id}/events", api_key=api_key, params=params
    )
    if isinstance(result, dict) and "error" in result:
        return [], f"Error deleting events: {result.get('message')}"
    events = result if isinstance(result, list) else []
    return events, None


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
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    events, error_msg = await _fetch_events_for_deletion(
        athlete_id_to_use, api_key, start_date, end_date
    )
    if error_msg:
        return error_msg

    failed_events = await _delete_events_list(athlete_id_to_use, api_key, events)
    deleted_count = len(events) - len(failed_events)
    return f"Deleted {deleted_count} events. Failed to delete {len(failed_events)} events: {failed_events}"


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
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    if not start_date:
        start_date = datetime.now().strftime("%Y-%m-%d")

    try:
        event_data = _prepare_event_data(
            name, workout_type, start_date, workout_doc, moving_time, distance
        )
        return await _create_or_update_event_request(
            athlete_id_to_use, api_key, event_data, start_date, event_id
        )
    except ValueError as e:
        return f"Error: {e}"


async def _create_or_update_event_request(
    athlete_id: str,
    api_key: str | None,
    event_data: dict[str, Any],
    start_date: str,
    event_id: str | None,
) -> str:
    """Create or update an event via API request.

    Args:
        athlete_id: The athlete ID.
        api_key: Optional API key.
        event_data: Prepared event data dictionary.
        start_date: Start date string for response formatting.
        event_id: Optional event ID for updates.

    Returns:
        Formatted response string.
    """
    url = f"/athlete/{athlete_id}/events"
    if event_id:
        url += f"/{event_id}"
    result = await make_intervals_request(
        url=url,
        api_key=api_key,
        data=event_data,
        method="PUT" if event_id else "POST",
    )
    action = "updated" if event_id else "created"
    return _handle_event_response(result, action, athlete_id, start_date)
