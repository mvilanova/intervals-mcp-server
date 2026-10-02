"""
Wellness-related MCP tools for Intervals.icu.

This module contains tools for retrieving and updating athlete wellness data.
"""

from intervals_mcp_server.api.client import make_intervals_request
from intervals_mcp_server.config import get_config
from intervals_mcp_server.utils.formatting import format_wellness_entry
from intervals_mcp_server.utils.validation import (
    resolve_athlete_id,
    resolve_date_params,
    validate_date,
)

# Import mcp instance from shared module for tool registration
from intervals_mcp_server.mcp_instance import mcp  # noqa: F401

config = get_config()


@mcp.tool()
async def get_wellness_data(
    athlete_id: str | None = None,
    api_key: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    include_all_fields: bool = False,
) -> str:
    """Get wellness data for an athlete from Intervals.icu.

    By default returns standard wellness fields (training metrics, vitals, sleep,
    subjective scores, etc.). Set include_all_fields=True to also include any
    additional or custom fields configured by the user in Intervals.icu.

    Args:
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
        start_date: Start date in YYYY-MM-DD format (optional, defaults to 30 days ago)
        end_date: End date in YYYY-MM-DD format (optional, defaults to today)
        include_all_fields: If True, include additional and custom fields beyond the standard set (optional, defaults to False)
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    start_date, end_date = resolve_date_params(start_date, end_date)

    params = {"oldest": start_date, "newest": end_date}

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/wellness", api_key=api_key, params=params
    )

    if isinstance(result, dict) and "error" in result:
        return f"Error fetching wellness data: {result.get('message')}"

    if not result:
        return (
            f"No wellness data found for athlete {athlete_id_to_use} in the specified date range."
        )

    wellness_summary = "Wellness Data:\n\n"

    if isinstance(result, dict):
        for date_str, data in result.items():
            if isinstance(data, dict) and "date" not in data:
                data["date"] = date_str
            wellness_summary += format_wellness_entry(data, include_all_fields=include_all_fields) + "\n\n"
    elif isinstance(result, list):
        for entry in result:
            if isinstance(entry, dict):
                wellness_summary += format_wellness_entry(entry, include_all_fields=include_all_fields) + "\n\n"

    return wellness_summary


# Subjective scales accepted by Intervals.icu (all 1-4, see update_wellness docstring).
_SUBJECTIVE_SCALE_MIN = 1
_SUBJECTIVE_SCALE_MAX = 4


@mcp.tool()
async def update_wellness(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    date: str,
    soreness: int | None = None,
    fatigue: int | None = None,
    stress: int | None = None,
    mood: int | None = None,
    motivation: int | None = None,
    injury: int | None = None,
    comments: str | None = None,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """WRITE: Update (modify) the subjective wellness fields of one day in Intervals.icu.

    This tool MODIFIES data in Intervals.icu. Only the fields you pass are sent and
    changed; all other values of that day (weight, HRV, sleep, resting HR, etc., which
    are usually synced from devices) are left untouched. At least one field is required.
    If no wellness record exists for the date, it is created.

    Scales (integers 1-4, as in the Intervals.icu wellness dialog):
        soreness:   1=Low, 2=Avg, 3=High, 4=Extreme
        fatigue:    1=Low, 2=Avg, 3=High, 4=Extreme
        stress:     1=Low, 2=Avg, 3=High, 4=Extreme
        mood:       1=Great, 2=Good, 3=OK, 4=Grumpy
        motivation: 1=Extreme, 2=High, 3=Avg, 4=Low
        injury:     1=None, 2=Niggle, 3=Poor, 4=Injured

    A scale value cannot be cleared again through the API once it is set (null is
    ignored and 0 is rejected); use the Intervals.icu web app for that. Double-check
    the values before writing.

    NOTE: comments REPLACES the day's existing comment, it does not append. To append,
    read the existing record first (get_wellness_data) and send the combined text.
    An empty string clears the comment.

    Args:
        date: The day to update in YYYY-MM-DD format
        soreness: Muscle soreness, 1-4 (optional)
        fatigue: Fatigue, 1-4 (optional)
        stress: Stress, 1-4 (optional)
        mood: Mood, 1-4 (optional)
        motivation: Motivation, 1-4 (optional)
        injury: Injury level, 1-4 (optional)
        comments: Free-text comment for the day; replaces any existing comment (optional)
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    try:
        validate_date(date)
    except ValueError as exc:
        return f"Error: {exc}"

    scales = {
        "soreness": soreness,
        "fatigue": fatigue,
        "stress": stress,
        "mood": mood,
        "motivation": motivation,
        "injury": injury,
    }
    body: dict[str, int | str] = {}
    for name, value in scales.items():
        if value is None:
            continue
        # bool is a subclass of int; reject it explicitly
        if isinstance(value, bool) or not _SUBJECTIVE_SCALE_MIN <= value <= _SUBJECTIVE_SCALE_MAX:
            return (
                f"Error: {name} must be an integer between {_SUBJECTIVE_SCALE_MIN} "
                f"and {_SUBJECTIVE_SCALE_MAX}."
            )
        body[name] = value
    if comments is not None:
        body["comments"] = comments

    if not body:
        return (
            "Error: No wellness fields provided. Pass at least one of soreness, fatigue, "
            "stress, mood, motivation, injury or comments."
        )

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/wellness/{date}",
        api_key=api_key,
        method="PUT",
        data=body,
    )

    if isinstance(result, dict) and "error" in result:
        return f"Error updating wellness data: {result.get('message')}"

    if not isinstance(result, dict) or not result:
        return f"Error updating wellness data: unexpected empty response for {date}."

    if "date" not in result:
        result["date"] = result.get("id", date)

    return "Wellness updated:\n\n" + format_wellness_entry(result)
