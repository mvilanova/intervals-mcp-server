"""Events domain service for Intervals.icu."""

from typing import Any

from intervals_mcp_server.api.client import make_intervals_request
from intervals_mcp_server.utils.types import WorkoutDoc
from intervals_mcp_server.utils.validation import validate_date


def resolve_workout_type(name: str | None, workout_type: str | None) -> str:
    """Infer workout type from name when not explicitly provided."""
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
    return "Ride"


def prepare_event_data(  # noqa: PLR0913
    name: str,
    workout_type: str,
    start_date: str,
    workout_doc: WorkoutDoc | None,
    moving_time: int | None,
    distance: int | None,
) -> dict[str, Any]:
    """Build the event payload dict for the Intervals.icu API."""
    resolved_type = resolve_workout_type(name, workout_type)
    return {
        "start_date_local": start_date + "T00:00:00",
        "category": "WORKOUT",
        "name": name,
        "description": str(workout_doc) if workout_doc else None,
        "type": resolved_type,
        "moving_time": moving_time,
        "distance": distance,
    }


async def list_events(
    athlete_id: str,
    api_key: str | None,
    start_date: str,
    end_date: str,
) -> dict[str, Any] | list[dict[str, Any]]:
    """Fetch events for an athlete in the given date range."""
    return await make_intervals_request(
        url=f"/athlete/{athlete_id}/events",
        api_key=api_key,
        params={"oldest": start_date, "newest": end_date},
    )


async def get_event(
    event_id: str, athlete_id: str, api_key: str | None
) -> dict[str, Any] | list[dict[str, Any]]:
    """Fetch a single event by ID."""
    return await make_intervals_request(
        url=f"/athlete/{athlete_id}/event/{event_id}", api_key=api_key
    )


async def create_or_update_event(
    athlete_id: str,
    api_key: str | None,
    event_data: dict[str, Any],
    event_id: str | None = None,
) -> dict[str, Any] | list[dict[str, Any]]:
    """Create or update an event. Updates when event_id is provided."""
    url = f"/athlete/{athlete_id}/events"
    if event_id:
        url += f"/{event_id}"
    return await make_intervals_request(
        url=url,
        api_key=api_key,
        data=event_data,
        method="PUT" if event_id else "POST",
    )


async def delete_single_event(
    event_id: str, athlete_id: str, api_key: str | None
) -> dict[str, Any] | list[dict[str, Any]]:
    """Delete a single event by ID."""
    return await make_intervals_request(
        url=f"/athlete/{athlete_id}/events/{event_id}",
        api_key=api_key,
        method="DELETE",
    )


async def delete_events_in_range(
    athlete_id: str,
    api_key: str | None,
    start_date: str,
    end_date: str,
) -> tuple[int, list[int | str | None]] | dict[str, Any]:
    """Fetch and delete all events in the date range.

    Returns (deleted_count, failed_event_ids) on success, or an error dict.
    """
    result = await make_intervals_request(
        url=f"/athlete/{athlete_id}/events",
        api_key=api_key,
        params={"oldest": validate_date(start_date), "newest": validate_date(end_date)},
    )
    if isinstance(result, dict) and "error" in result:
        return result

    events: list[dict[str, Any]] = result if isinstance(result, list) else []
    failed: list[int | str | None] = []
    for event in events:
        del_result = await make_intervals_request(
            url=f"/athlete/{athlete_id}/events/{event.get('id')}",
            api_key=api_key,
            method="DELETE",
        )
        if isinstance(del_result, dict) and "error" in del_result:
            failed.append(event.get("id"))

    return len(events) - len(failed), failed
