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
from intervals_mcp_server.utils.validation import (
    resolve_activity_type,
    resolve_athlete_id,
    validate_date,
)

# Import mcp instance from shared module for tool registration
from intervals_mcp_server.mcp_instance import mcp  # noqa: F401

config = get_config()


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
    resolved_workout_type = resolve_activity_type(name, workout_type)
    return {
        "start_date_local": start_date + "T00:00:00",
        "category": "WORKOUT",
        "name": name,
        "description": str(workout_doc) if workout_doc else None,
        "type": resolved_workout_type,
        "moving_time": moving_time,
        "distance": distance,
    }


def _prepare_note_data(
    name: str, description: str, start_date: str, color: str | None
) -> dict[str, Any]:
    """Prepare note (category NOTE) data dictionary for API request."""
    return {
        "category": "NOTE",
        "name": name,
        "description": description,
        "start_date_local": start_date + "T00:00:00",
        "color": color,
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
        return f"Successfully {action} event id: {result.get('id')}"
    return f"Event {action} successfully at {start_date}"


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
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    if not start_date:
        start_date = datetime.now().strftime("%Y-%m-%d")

    try:
        validated_date = validate_date(start_date)
        event_data = _prepare_event_data(
            name, workout_type, validated_date, workout_doc, moving_time, distance
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
    color: str | None = "green",
    athlete_id: str | None = None,
    api_key: str | None = None,
    event_id: str | None = None,
) -> str:
    """Add or update a plain text note (category NOTE) on the Intervals.icu calendar.

    Args:
        name: Title of the note
        description: Plain text content of the note
        start_date: Date in YYYY-MM-DD format (optional, defaults to today)
        color: Color of the note (e.g. green, orange, red, blue)
        athlete_id: The Intervals.icu athlete ID (optional)
        api_key: The Intervals.icu API key (optional)
        event_id: The Intervals.icu event ID (optional, for updates)
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    if not start_date:
        start_date = datetime.now().strftime("%Y-%m-%d")

    try:
        validated_date = validate_date(start_date)
        event_data = _prepare_note_data(name, description, validated_date, color)
        return await _create_or_update_event_request(
            athlete_id_to_use, api_key, event_data, validated_date, event_id
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


_BULK_COMMON_KEYS = {"category", "name", "start_date"}
_BULK_WORKOUT_KEYS = _BULK_COMMON_KEYS | {
    "workout_type",
    "workout_doc",
    "description",
    "moving_time",
    "distance",
}
_BULK_NOTE_KEYS = _BULK_COMMON_KEYS | {"description", "color"}


def _build_bulk_event_entry(entry: Any) -> dict[str, Any]:  # pylint: disable=too-many-branches
    """Validate one bulk entry and build the API event body using the shared builders.

    All problems of the entry are collected and reported together.

    Raises:
        ValueError: If the entry is invalid; the message lists every problem found.
    """
    if not isinstance(entry, dict):
        raise ValueError("entry must be an object")

    problems: list[str] = []
    category = str(entry.get("category") or "WORKOUT").upper()
    if category not in ("WORKOUT", "NOTE"):
        raise ValueError("'category' must be WORKOUT or NOTE")
    allowed = _BULK_NOTE_KEYS if category == "NOTE" else _BULK_WORKOUT_KEYS
    not_applicable = sorted(set(entry) - allowed)
    if not_applicable:
        problems.append(f"keys not supported for category {category}: {', '.join(not_applicable)}")

    name = entry.get("name")
    if not isinstance(name, str) or not name:
        problems.append("'name' is required")
    validated_date = ""
    if not entry.get("start_date"):
        problems.append("'start_date' is required")
    else:
        try:
            validated_date = validate_date(str(entry["start_date"]))
        except ValueError as e:
            problems.append(str(e))

    description = entry.get("description")
    if category == "NOTE":
        if not isinstance(description, str) or not description:
            problems.append("'description' is required for category NOTE")
        if problems:
            raise ValueError("; ".join(problems))
        return _prepare_note_data(
            str(name), str(description), validated_date, entry.get("color", "green")
        )

    workout_type = entry.get("workout_type")
    if not isinstance(workout_type, str) or not workout_type:
        problems.append("'workout_type' is required for category WORKOUT")
    if description is not None and not isinstance(description, str):
        problems.append("'description' must be a string")
    raw_doc = entry.get("workout_doc")
    workout_doc: WorkoutDoc | None = None
    if raw_doc is not None and description:
        problems.append("provide either 'workout_doc' or 'description', not both")
    if isinstance(raw_doc, dict):
        try:
            workout_doc = WorkoutDoc.from_dict(raw_doc)
        except (ValueError, TypeError, KeyError) as e:
            problems.append(f"invalid 'workout_doc': {e!r}")
    elif isinstance(raw_doc, WorkoutDoc):
        workout_doc = raw_doc
    elif raw_doc is not None:
        problems.append("'workout_doc' must be an object")
    for key in ("moving_time", "distance"):
        value = entry.get(key)
        if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
            problems.append(f"'{key}' must be an integer")
    if problems:
        raise ValueError("; ".join(problems))

    try:
        body = _prepare_event_data(
            str(name),
            str(workout_type),
            validated_date,
            workout_doc,
            entry.get("moving_time"),
            entry.get("distance"),
        )
    except (ValueError, TypeError, KeyError) as e:
        raise ValueError(f"invalid 'workout_doc': {e!r}") from e
    if description:
        # Native Intervals.icu workout text, sent as-is.
        body["description"] = description
    return body


@mcp.tool()
async def add_events_bulk(
    events: list[dict[str, Any]],
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """WRITES to Intervals.icu: create many calendar events (planned workouts and/or notes) in one call.

    All entries are validated first. If ANY entry is invalid, nothing is sent and all errors are
    returned (fix them and retry). Otherwise all entries are sent in a single POST to
    /athlete/{id}/events/bulk. This tool only creates new events (it never updates existing ones;
    use add_or_update_event for that).

    Args:
        events: List of entry objects (see below).
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)

    Entry keys (keys that do not apply to the entry's category are rejected, not ignored):
        name (str, required): Name/title of the event
        start_date (str, required): Date in YYYY-MM-DD format
        category (str, optional): "WORKOUT" (default) or "NOTE"
        WORKOUT entries:
            workout_type (str, REQUIRED here, unlike add_or_update_event where it is inferred
                from the name): e.g. Ride, Run, Swim, Walk, Row
            workout_doc (object, optional): structured workout with "steps", same structure as in
                add_or_update_event, e.g.
                {"description": "...", "steps": [{"power": {"value": 80, "units": "%ftp"}, "duration": 900}]}
            description (str, optional): workout as native Intervals.icu workout text, sent as-is.
                Mutually exclusive with workout_doc.
            moving_time (int, optional): expected moving time in seconds
            distance (int, optional): expected distance in meters
        NOTE entries:
            description (str, required): plain text content of the note
            color (str, optional): note color, defaults to "green"

    Example:
        [
            {"name": "Easy run", "start_date": "2025-01-06", "workout_type": "Run", "moving_time": 2700},
            {"name": "Rest day", "start_date": "2025-01-07", "category": "NOTE", "description": "Full rest"}
        ]

    Returns:
        JSON with "created" (per event: input index, event id, and the name/start date as returned
        by the API), "errors" (index and all problems found per invalid entry, joined with "; ")
        and counts. If the request
        fails, an error string is returned and events may have been created.
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if not events:
        return "Error: No events provided."

    bodies: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for index, entry in enumerate(events):
        try:
            bodies.append(_build_bulk_event_entry(entry))
        except (ValueError, TypeError, KeyError) as e:
            errors.append({"index": index, "error": str(e)})

    if errors:
        return json.dumps(
            {
                "message": "No events were sent because some entries are invalid.",
                "created_count": 0,
                "error_count": len(errors),
                "created": [],
                "errors": errors,
            },
            indent=2,
        )

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/events/bulk",
        api_key=api_key,
        method="POST",
        params={"upsert": False, "upsertOnUid": False, "updatePlanApplied": False},
        data=bodies,
    )
    if isinstance(result, dict) and "error" in result:
        return (
            f"Error creating events in bulk: {result.get('message', 'Unknown error')}. "
            "The events may have been partially or fully created; check get_events for the "
            "date range before retrying."
        )
    returned = result if isinstance(result, list) else []
    created: list[dict[str, Any]] = []
    for index, body in enumerate(bodies):
        item = returned[index] if index < len(returned) else {}
        if not isinstance(item, dict):
            item = {}
        created.append(
            {
                "index": index,
                "id": item.get("id"),
                "name": item.get("name", body.get("name")),
                "start_date_local": item.get("start_date_local"),
            }
        )
    if len(returned) != len(bodies):
        errors.append(
            {
                "index": None,
                "error": f"API returned {len(returned)} events for {len(bodies)} sent; ids may be missing",
            }
        )
    return json.dumps(
        {
            "created_count": len(created),
            "error_count": len(errors),
            "created": created,
            "errors": errors,
        },
        indent=2,
    )
