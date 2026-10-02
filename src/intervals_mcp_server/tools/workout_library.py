"""
Workout library MCP tools for Intervals.icu.

This module contains tools for listing the athlete's workout library (folders and plans
with their workouts), creating new library workouts (templates) and scheduling a library
workout on the calendar.
"""

from typing import Any

from intervals_mcp_server.api.client import make_intervals_request
from intervals_mcp_server.config import get_config
from intervals_mcp_server.utils.types import WorkoutDoc
from intervals_mcp_server.utils.validation import (
    resolve_activity_type,
    resolve_athlete_id,
    validate_date,
)

# Import mcp instance from shared module for tool registration
from intervals_mcp_server.mcp_instance import mcp  # noqa: F401

config = get_config()

# Workout fields copied from a library workout when scheduling it on the calendar.
_WORKOUT_FIELDS_FOR_EVENT = (
    "name",
    "description",
    "type",
    "moving_time",
    "distance",
    "indoor",
    "color",
    "tags",
    "target",
    "sub_type",
    "carbs_per_hour",
)

# Above this many workouts, an unfiltered listing only shows per-folder counts.
_MAX_WORKOUTS_FULL_LISTING = 50


def _folder_matches(folder: dict[str, Any], key: str) -> bool:
    """Check whether a folder matches the given name (case-insensitive) or id."""
    return str(folder.get("id")) == key or str(folder.get("name", "")).lower() == key.lower()


def _format_workout(workout: dict[str, Any], folder_name: str) -> str:
    """Format a library workout as a short text block."""
    lines = [
        f"- id: {workout.get('id')} | name: {workout.get('name', 'Unnamed')} "
        f"| type: {workout.get('type', 'Unknown')} | folder: {folder_name}"
    ]
    details = []
    moving_time = workout.get("moving_time")
    if isinstance(moving_time, (int, float)) and moving_time:
        minutes = int(moving_time) // 60
        details.append(f"duration: {minutes // 60}h{minutes % 60:02d}m")
    if workout.get("icu_training_load") is not None:
        details.append(f"load: {workout['icu_training_load']}")
    if details:
        lines.append("  " + " | ".join(details))
    description = str(workout.get("description") or "").strip()
    if description:
        first_line = description.splitlines()[0]
        if len(first_line) > 100 or "\n" in description:
            first_line = first_line[:100] + "..."
        lines.append(f"  description: {first_line}")
    return "\n".join(lines)


def _format_folder(folder: dict[str, Any]) -> str:
    """Format a folder/plan with its workouts."""
    name = str(folder.get("name", "Unnamed"))
    children = [c for c in folder.get("children") or [] if isinstance(c, dict)]
    header = (
        f"{folder.get('type', 'FOLDER')}: {name} (id: {folder.get('id')}) "
        f"- {len(children)} workouts"
    )
    return "\n".join([header, *(_format_workout(child, name) for child in children)])


def _available_folders(folders: list[dict[str, Any]]) -> str:
    """List folder names and ids for error messages."""
    return ", ".join(f"{f.get('name')} (id {f.get('id')})" for f in folders)


async def _fetch_folders(
    athlete_id: str, api_key: str | None
) -> tuple[list[dict[str, Any]], str | None]:
    """Fetch all folders/plans. Returns (folders, error_message)."""
    result = await make_intervals_request(url=f"/athlete/{athlete_id}/folders", api_key=api_key)
    if isinstance(result, dict) and "error" in result:
        return [], str(result.get("message", "Unknown error"))
    folders = [f for f in result if isinstance(f, dict)] if isinstance(result, list) else []
    return folders, None


@mcp.tool()
async def get_workout_library(
    folder: str | None = None,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """List the athlete's workout library (folders/plans and their workouts) from Intervals.icu.

    Args:
        folder: Optional folder or plan filter, either the folder name (case-insensitive) or its id
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    folders, error = await _fetch_folders(athlete_id_to_use, api_key)
    if error:
        return f"Error fetching workout library: {error}"

    if folder:
        folders = [f for f in folders if _folder_matches(f, folder)]
        if not folders:
            return f"No folder matching '{folder}' found for athlete {athlete_id_to_use}."

    if not folders:
        return f"No workout library found for athlete {athlete_id_to_use}."

    if not folder:
        total = sum(len(f.get("children") or []) for f in folders)
        if total > _MAX_WORKOUTS_FULL_LISTING:
            lines = [
                f"{f.get('type', 'FOLDER')}: {f.get('name', 'Unnamed')} (id: {f.get('id')}) "
                f"- {len(f.get('children') or [])} workouts"
                for f in folders
            ]
            return (
                f"Workout library ({total} workouts, too many to list at once). "
                "Pass `folder` (name or id) to see the workouts of one folder:\n\n"
                + "\n".join(lines)
            )

    return "Workout library:\n\n" + "\n\n".join(_format_folder(f) for f in folders)


async def _resolve_folder_id(
    athlete_id: str, api_key: str | None, folder: str | None
) -> tuple[int | None, str | None]:
    """Resolve a folder name/id to a folder id. Returns (folder_id, error_message)."""
    folders, error = await _fetch_folders(athlete_id, api_key)
    if error:
        return None, f"Error fetching folders: {error}"
    if not folders:
        return None, (
            "Error: the workout library has no folders. Create a folder or plan in "
            "Intervals.icu first, workouts must belong to a folder."
        )
    if folder:
        matches = [f for f in folders if _folder_matches(f, folder)]
        if not matches:
            return None, (
                f"Error: no folder matching '{folder}'. "
                f"Available folders: {_available_folders(folders)}"
            )
        if len(matches) > 1:
            return None, (
                f"Error: folder '{folder}' is ambiguous, use the id. "
                f"Matches: {_available_folders(matches)}"
            )
        if matches[0].get("type", "FOLDER") != "FOLDER":
            return None, (
                f"Error: '{matches[0].get('name')}' is a {matches[0].get('type')}; "
                "plans are not supported by this tool, choose a regular folder."
            )
        return int(matches[0]["id"]), None
    plain = [f for f in folders if f.get("type", "FOLDER") == "FOLDER"]
    if not plain:
        return None, "Error: the workout library has no regular folders (plans are not supported)."
    if len(plain) == 1:
        return int(plain[0]["id"]), None
    return None, (
        "Error: multiple folders exist, specify one with 'folder'. "
        f"Available folders: {_available_folders(plain)}"
    )


@mcp.tool()
async def create_library_workout(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    name: str,
    sport_type: str,
    folder: str | None = None,
    description: str | None = None,
    workout_doc: WorkoutDoc | None = None,
    moving_time: int | None = None,
    distance: int | None = None,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """WRITES to Intervals.icu: create a new workout template in the athlete's workout library.

    Args:
        name: Name of the workout (e.g. "Sweet Spot 3x10")
        sport_type: Sport type (e.g. Ride, Run, Swim, Walk, Row, WeightTraining)
        folder: Folder or plan to put the workout in, by name (case-insensitive) or id. Optional if
            the library has exactly one folder; the call fails if there is no folder.
        description: Workout text in Intervals.icu workout syntax (e.g. "- 10m 55%\\n3x\\n- 10m 90%\\n- 5m 55%")
            or free text. Ignored if workout_doc is given.
        workout_doc: Structured steps (same format as in add_or_update_event). Rendered into the
            description text.
        moving_time: Expected total moving time in seconds (optional)
        distance: Expected total distance in meters (optional)
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    folder_id, error = await _resolve_folder_id(athlete_id_to_use, api_key, folder)
    if error:
        return error

    workout_data: dict[str, Any] = {
        "name": name,
        "type": resolve_activity_type(name, sport_type),
        "folder_id": folder_id,
    }
    if workout_doc:
        workout_data["description"] = str(workout_doc)
    elif description is not None:
        workout_data["description"] = description
    if moving_time is not None:
        workout_data["moving_time"] = moving_time
    if distance is not None:
        workout_data["distance"] = distance

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/workouts",
        api_key=api_key,
        data=workout_data,
        method="POST",
    )
    if isinstance(result, dict) and "error" in result:
        return f"Error creating library workout: {result.get('message', 'Unknown error')}"
    if isinstance(result, dict) and result.get("id") is not None:
        return f"Successfully created library workout id: {result.get('id')} in folder {folder_id}"
    return f"No library workout created for athlete {athlete_id_to_use}."


@mcp.tool()
async def add_event_from_library(
    workout_id: str,
    date: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """WRITES to Intervals.icu: schedule a workout from the workout library on the calendar.

    Creates a new calendar event (category WORKOUT) on the given date by copying the library
    workout's name, description (steps), type, duration, distance and tags.

    Args:
        workout_id: The id of the library workout (see get_workout_library). Library ids are
            numbered per athlete, so small values such as 1 are normal.
        date: Date in YYYY-MM-DD format
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if not (workout_id.isascii() and workout_id.isdigit()):
        return "Error: workout_id must be a numeric library workout ID."
    try:
        validated_date = validate_date(date)
    except ValueError as e:
        return f"Error: {e}"

    workout = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/workouts/{workout_id}", api_key=api_key
    )
    if isinstance(workout, dict) and "error" in workout:
        return f"Error fetching library workout: {workout.get('message', 'Unknown error')}"
    if not isinstance(workout, dict) or not workout:
        return f"No library workout found with id {workout_id}."

    event_data: dict[str, Any] = {
        key: workout[key] for key in _WORKOUT_FIELDS_FOR_EVENT if workout.get(key) is not None
    }
    event_data["category"] = "WORKOUT"
    event_data["start_date_local"] = validated_date + "T00:00:00"

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/events",
        api_key=api_key,
        data=event_data,
        method="POST",
    )
    if isinstance(result, dict) and "error" in result:
        return (
            f"Error creating event from library workout: {result.get('message', 'Unknown error')}"
        )
    if isinstance(result, dict) and result.get("id") is not None:
        return (
            f"Successfully created event id: {result.get('id')} on {validated_date} "
            f"from library workout {workout_id}"
        )
    return f"No event created for athlete {athlete_id_to_use}."


@mcp.tool()
async def delete_library_workout(
    workout_id: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """DELETES from Intervals.icu: permanently remove a workout from the workout library.

    This cannot be undone. Calendar events that were created from the workout are not
    affected. Only the given workout is deleted (other workouts added together with it to
    a plan are kept).

    Args:
        workout_id: The id of the library workout (see get_workout_library). Library ids are
            numbered per athlete, so small values such as 1 are normal.
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if not (workout_id.isascii() and workout_id.isdigit()):
        return "Error: workout_id must be a numeric library workout ID."

    url = f"/athlete/{athlete_id_to_use}/workouts/{workout_id}"
    workout = await make_intervals_request(url=url, api_key=api_key)
    if isinstance(workout, dict) and "error" in workout:
        return f"Error fetching library workout: {workout.get('message', 'Unknown error')}"
    if not isinstance(workout, dict) or not workout:
        return f"No library workout found with id {workout_id}."

    result = await make_intervals_request(url=url, api_key=api_key, method="DELETE")
    if isinstance(result, dict) and "error" in result:
        return f"Error deleting library workout: {result.get('message', 'Unknown error')}"
    return f"Deleted library workout {workout_id} '{workout.get('name') or 'unnamed'}'."
