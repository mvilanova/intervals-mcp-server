"""Activities domain service for Intervals.icu."""

from datetime import datetime, timedelta
from typing import Any

from intervals_mcp_server.api.client import make_intervals_request


def parse_activities(result: Any) -> list[dict[str, Any]]:
    """Extract a flat list of activity dicts from various API response shapes."""
    activities: list[dict[str, Any]] = []
    if isinstance(result, list):
        activities = [item for item in result if isinstance(item, dict)]
    elif isinstance(result, dict):
        for _key, value in result.items():
            if isinstance(value, list):
                activities = [item for item in value if isinstance(item, dict)]
                break
        if not activities and any(key in result for key in ["name", "startTime", "distance"]):
            activities = [result]
    return activities


def filter_named(activities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove unnamed activities from the list."""
    return [a for a in activities if a.get("name") and a.get("name") != "Unnamed"]


async def _fetch_more_activities(
    athlete_id: str,
    api_key: str | None,
    start_date: str,
    api_limit: int,
) -> list[dict[str, Any]]:
    """Fetch activities from the 60-day window before start_date to fill filtering gaps."""
    oldest_date = datetime.fromisoformat(start_date)
    older_start = (oldest_date - timedelta(days=60)).strftime("%Y-%m-%d")
    older_end = (oldest_date - timedelta(days=1)).strftime("%Y-%m-%d")
    if older_start >= older_end:
        return []
    result = await make_intervals_request(
        url=f"/athlete/{athlete_id}/activities",
        api_key=api_key,
        params={"oldest": older_start, "newest": older_end, "limit": api_limit},
    )
    if isinstance(result, list):
        return filter_named(result)
    return []


async def list_activities(
    athlete_id: str,
    api_key: str | None,
    start_date: str,
    end_date: str,
    limit: int,
    include_unnamed: bool,
) -> list[dict[str, Any]] | dict[str, Any]:
    """Fetch, parse, and filter activities for an athlete.

    Returns a list of activity dicts (possibly empty) or an error dict.
    """
    api_limit = limit * 3 if not include_unnamed else limit
    result = await make_intervals_request(
        url=f"/athlete/{athlete_id}/activities",
        api_key=api_key,
        params={"oldest": start_date, "newest": end_date, "limit": api_limit},
    )
    if isinstance(result, dict) and "error" in result:
        return result

    activities = parse_activities(result)
    if not include_unnamed:
        activities = filter_named(activities)
        if len(activities) < limit:
            more = await _fetch_more_activities(athlete_id, api_key, start_date, api_limit)
            activities.extend(more)
    return activities[:limit]


async def get_activity(
    activity_id: str, api_key: str | None
) -> dict[str, Any] | list[dict[str, Any]]:
    """Fetch a single activity by ID."""
    return await make_intervals_request(url=f"/activity/{activity_id}", api_key=api_key)


async def get_intervals(
    activity_id: str, api_key: str | None
) -> dict[str, Any] | list[dict[str, Any]]:
    """Fetch interval data for an activity."""
    return await make_intervals_request(
        url=f"/activity/{activity_id}/intervals", api_key=api_key
    )


async def get_streams(
    activity_id: str,
    api_key: str | None,
    stream_types: str | None = None,
) -> dict[str, Any] | list[dict[str, Any]]:
    """Fetch time-series streams for an activity."""
    types = stream_types or "time,watts,heartrate,cadence,altitude,distance,velocity_smooth"
    return await make_intervals_request(
        url=f"/activity/{activity_id}/streams",
        api_key=api_key,
        params={"types": types},
    )


async def get_messages(
    activity_id: str, api_key: str | None
) -> dict[str, Any] | list[dict[str, Any]]:
    """Fetch messages (notes/comments) for an activity."""
    return await make_intervals_request(
        url=f"/activity/{activity_id}/messages", api_key=api_key
    )


async def post_message(
    activity_id: str, api_key: str | None, content: str
) -> dict[str, Any] | list[dict[str, Any]]:
    """Post a message to an activity."""
    return await make_intervals_request(
        url=f"/activity/{activity_id}/messages",
        api_key=api_key,
        method="POST",
        data={"content": content},
    )
