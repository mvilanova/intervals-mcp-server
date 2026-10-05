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
from intervals_mcp_server.utils.validation import resolve_activity_type, resolve_athlete_id, validate_date

# Import mcp instance from shared module for tool registration
from intervals_mcp_server.mcp_instance import mcp  # noqa: F401

config = get_config()


def _prepare_event_data(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    name: str,
    workout_type: str | None,
    start_date: str | None,
    workout_doc: WorkoutDoc | None,
    moving_time: int | None,
    distance: int | None,
    category: str | None = None,
    is_update: bool = False,
) -> dict[str, Any]:
    """Prepare event data dictionary for API request.

    Many arguments are required to match the Intervals.icu API event structure.
    On create, the category defaults to WORKOUT and a missing type is inferred from
    the name. On update, category and type are only set when the caller passes them,
    so an update never turns a NOTE into a WORKOUT. None values are dropped before
    the request (see :func:`_create_or_update_event_request`).
    """
    if is_update:
        event_type = workout_type or None
    else:
        event_type = resolve_activity_type(name, workout_type)
        category = category or "WORKOUT"
    return {
        "start_date_local": start_date + "T00:00:00" if start_date else None,
        "category": category,
        "name": name,
        "description": str(workout_doc) if workout_doc else None,
        "type": event_type,
        "moving_time": moving_time,
        "distance": distance,
    }


def _handle_event_response(
    result: dict[str, Any] | list[dict[str, Any]] | None,
    action: str,
    athlete_id: str,
    start_date: str | None,
) -> str:
    """Handle API response and format appropriate message."""
    if isinstance(result, dict) and "error" in result:
        error_message = result.get("message", "Unknown error")
        return f"Error {action} event: {error_message}"
    if not result:
        return f"No events {action} for athlete {athlete_id}."
    if isinstance(result, dict):
        return f"Successfully {action} event id: {result.get('id')}"
    return f"Event {action} successfully" + (f" at {start_date}" if start_date else "")


async def _delete_events_list(
    athlete_id: str, api_key: str | None, events: list[dict[str, Any]]
) -> list[int | str | None]:
    """Delete a list of events and return IDs of failed deletions.

    Args:
        athlete_id: The athlete ID.
        api_key: Optional API key.
        events: List of event dictionaries to delete.

    Returns:
        List of event IDs that failed to delete.
    """
    failed_events: list[int | str | None] = []
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
        url=f"/athlete/{athlete_id_to_use}/events/{event_id}", api_key=api_key
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
    name: str,
    workout_type: str | None = None,
    athlete_id: str | None = None,
    api_key: str | None = None,
    event_id: str | None = None,
    start_date: str | None = None,
    workout_doc: WorkoutDoc | None = None,
    moving_time: int | None = None,
    distance: int | None = None,
    category: str | None = None,
) -> str:
    """Post event for an athlete to Intervals.icu this follows the event api from intervals.icu
    If event_id is provided, the event will be updated instead of created. An update
    only changes the fields you pass; omitted fields (description, date, type,
    category, ...) keep their current values.

    Many arguments are required as this MCP tool function maps directly to the Intervals.icu API parameters.

    Args:
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
        event_id: The Intervals.icu event ID (optional; if given, that event is updated)
        start_date: Start date in YYYY-MM-DD format (optional, defaults to today when
            creating; unchanged on update)
        name: Name of the activity
        workout_doc: steps as a list of Step objects (optional, but necessary to define workout steps)
        workout_type: Workout type (e.g. Ride, Run, Swim, Walk, Row, WeightTraining).
            Optional: inferred from the name when creating, unchanged on update.
        moving_time: Total expected moving time of the workout in seconds (optional)
        distance: Total expected distance of the workout in meters (optional)
        category: Event category (optional): WORKOUT (default when creating), RACE_A,
            RACE_B, RACE_C, NOTE, ... Unchanged on update unless given.

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
            Absolute pace (seconds or decimal minutes per km; MINS_MILE, SECS_100M, SECS_500M analog):
                {"pace": {"value": 335, "units": "MINS_KM"}}
            Zone by power: {"power": {"value": 2, "units": "power_zone"}}
            Zone by heart rate: {"hr": {"value": 2, "units": "hr_zone"}}
        Ranges: Specify ranges for power, heart rate, pace, or cadence:
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
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    if not start_date and not event_id:
        start_date = datetime.now().strftime("%Y-%m-%d")

    try:
        validated_date = validate_date(start_date) if start_date else None
        event_data = _prepare_event_data(
            name,
            workout_type,
            validated_date,
            workout_doc,
            moving_time,
            distance,
            category,
            is_update=bool(event_id),
        )
        return await _create_or_update_event_request(
            athlete_id_to_use, api_key, event_data, validated_date, event_id
        )
    except ValueError as e:
        return f"Error: {e}"


@mcp.tool()
async def add_or_update_note(
    name: str,
    description: str,
    start_date: str | None = None,
    color: str | None = None,
    athlete_id: str | None = None,
    api_key: str | None = None,
    event_id: str | None = None,
) -> str:
    """Add or update a plain text note (category NOTE) on the Intervals.icu calendar.

    An update only changes the fields you pass; date and color keep their values.

    Args:
        name: Title of the note
        description: Plain text content of the note
        start_date: Date in YYYY-MM-DD format (optional, defaults to today when
            creating; unchanged on update)
        color: Color of the note (e.g. green, orange, red, blue; optional, green when
            creating; unchanged on update)
        athlete_id: The Intervals.icu athlete ID (optional)
        api_key: The Intervals.icu API key (optional)
        event_id: The Intervals.icu event ID (optional, for updates)
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    is_update = bool(event_id)
    if not start_date and not is_update:
        start_date = datetime.now().strftime("%Y-%m-%d")

    try:
        validated_date = validate_date(start_date) if start_date else None
        event_data = {
            "category": None if is_update else "NOTE",
            "name": name,
            "description": description,
            "start_date_local": validated_date + "T00:00:00" if validated_date else None,
            "color": color if is_update else color or "green",
        }

        return await _create_or_update_event_request(
            athlete_id_to_use, api_key, event_data, validated_date, event_id
        )
    except ValueError as e:
        return f"Error: {e}"


async def _create_or_update_event_request(
    athlete_id: str,
    api_key: str | None,
    event_data: dict[str, Any],
    start_date: str | None,
    event_id: str | None,
) -> str:
    """Create or update an event via API request.

    None values are not sent: a PUT with ``"description": null`` would clear the
    existing description.

    Args:
        athlete_id: The athlete ID.
        api_key: Optional API key.
        event_data: Prepared event data dictionary.
        start_date: Start date string for response formatting (None on updates
            that keep the date).
        event_id: Optional event ID for updates.

    Returns:
        Formatted response string.
    """
    event_data = {key: value for key, value in event_data.items() if value is not None}
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
