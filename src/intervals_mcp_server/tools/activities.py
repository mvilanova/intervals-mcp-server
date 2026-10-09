"""
Activity-related MCP tools for Intervals.icu.

This module contains tools for retrieving and managing athlete activities.
"""

import json
from datetime import datetime, timedelta
from typing import Any

from intervals_mcp_server.api.client import make_intervals_request
from intervals_mcp_server.config import get_config
from intervals_mcp_server.tools.custom_items import get_custom_item_index
from intervals_mcp_server.tools.gear import (
    resolve_gear_for_activity,
    resolve_gear_for_activities,
)
from intervals_mcp_server.utils.custom_fields import (
    ACTIVITY_FIELD,
    ACTIVITY_STREAM,
    INTERVAL_FIELD,
    CustomFieldDefs,
)
from intervals_mcp_server.utils.formatting import (
    format_activity_details,
    format_activity_message,
    format_activity_summary,
    format_intervals,
)
from intervals_mcp_server.utils.streams import (
    DEFAULT_STREAM_TYPES,
    describe_stream,
    find_stream,
    format_stats,
    format_streams_summary,
    order_streams,
    range_stats,
    render_streams_json,
    render_streams_table,
    resolve_sample_range,
    stream_label,
    stream_length,
)
from intervals_mcp_server.utils.validation import resolve_athlete_id, resolve_date_params

# Import mcp instance from shared module for tool registration
from intervals_mcp_server.mcp_instance import mcp  # noqa: F401

config = get_config()

STREAM_OUTPUT_FORMATS = ("summary", "full", "json")
# Selectors of get_activity_streams / get_activity_intervals that fetch every stream.
_ALL_STREAM_SELECTORS = ("all", "custom")


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


async def _custom_defs(
    item_type: str, api_key: str | None, athlete_id: Any = None
) -> CustomFieldDefs:
    """Custom item definitions of one type for the athlete (cached per process).

    The athlete is taken from the payload (``icu_athlete_id``) when given, otherwise
    from the configured ATHLETE_ID. Without an athlete there are no definitions.
    """
    athlete_id_to_use = str(athlete_id) if athlete_id else config.athlete_id
    if not athlete_id_to_use:
        return {}
    index = await get_custom_item_index(athlete_id=athlete_id_to_use, api_key=api_key)
    return index.get(item_type, {})


def _split_stream_types(stream_types: str) -> list[str]:
    """Split a comma-separated list, trimming blanks and duplicates (order kept)."""
    selected: list[str] = []
    for part in stream_types.split(","):
        name = part.strip()
        if name and name not in selected:
            selected.append(name)
    return selected


def _stream_request_params(
    stream_types: str | None, *, ensure_time: bool
) -> dict[str, str] | None:
    """Translate the stream_types argument into query parameters for the streams endpoint.

    None selects the default streams, "all"/"custom" fetch every stream of the
    activity (no filter), anything else is passed through as given. The time
    stream is added when ensure_time is set, because it carries the timestamps.
    """
    if stream_types is None:
        selected = _split_stream_types(DEFAULT_STREAM_TYPES)
    elif stream_types.strip().lower() in _ALL_STREAM_SELECTORS:
        return None
    else:
        selected = _split_stream_types(stream_types)
    if ensure_time and "time" not in selected:
        selected.insert(0, "time")
    return {"types": ",".join(selected)}


async def _fetch_streams(
    activity_id: str, api_key: str | None, params: dict[str, str] | None
) -> tuple[list[dict[str, Any]], str | None]:
    """Fetch streams for an activity. Returns (streams, error_message)."""
    result = await make_intervals_request(
        url=f"/activity/{activity_id}/streams",
        api_key=api_key,
        params=params,
    )

    if isinstance(result, dict) and "error" in result:
        error_message = result.get("message", "Unknown error")
        return [], f"Error fetching activity streams: {error_message}"

    streams = [item for item in result if isinstance(item, dict)] if isinstance(result, list) else []
    if not streams:
        return [], f"No stream data found for activity {activity_id}."
    return streams, None


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
    # Resolve athlete ID and date parameters
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    start_date, end_date = resolve_date_params(start_date, end_date)

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

    # Resolve gear names (in-place injection of `_resolved_gear_name`)
    await resolve_gear_for_activities(
        activities, athlete_id=athlete_id_to_use, api_key=api_key
    )

    return _format_activities_response(activities, athlete_id_to_use, include_unnamed)


@mcp.tool()
async def get_activity_details(
    activity_id: str,
    api_key: str | None = None,
    include_custom_fields: bool = True,
    include_all_fields: bool = False,
) -> str:
    """Get detailed information for a specific activity from Intervals.icu

    Besides the standard summary the result lists every custom activity field the
    athlete has defined on Intervals.icu that has a value on this activity, with
    display name, technical code, value and units (for select fields also the option
    label). This covers metrics that devices write into custom fields, for example
    aerobic/anaerobic training effect, training load, EPOC, recovery time, VO2max,
    performance condition, stamina at start/end, sweat loss and any other field the
    athlete has configured. The fields are read dynamically from the athlete's custom
    item definitions; nothing is hard-coded. 'no value' means null/NaN on Intervals.icu.

    Args:
        activity_id: The Intervals.icu activity ID
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
        include_custom_fields: Include the custom activity fields section (optional, default True)
        include_all_fields: Also list every other non-empty field of the raw activity payload
            that is not part of the standard summary, e.g. time in zones, running dynamics,
            power meter details, available stream types (optional, default False)
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

    # Resolve gear name (uses configured athlete_id via ATHLETE_ID env var)
    await resolve_gear_for_activity(activity_data, api_key=api_key)

    custom_field_defs: CustomFieldDefs | None = None
    if include_custom_fields:
        custom_field_defs = await _custom_defs(
            ACTIVITY_FIELD, api_key, activity_data.get("icu_athlete_id")
        )

    return format_activity_details(
        activity_data,
        custom_field_defs=custom_field_defs,
        include_all_fields=include_all_fields,
    )


@mcp.tool()
async def get_activity_intervals(
    activity_id: str,
    api_key: str | None = None,
    stream_types: str | None = None,
    include_custom_fields: bool = True,
) -> str:
    """Get interval data for a specific activity from Intervals.icu

    This endpoint returns detailed metrics for each interval in an activity, including power, heart rate,
    cadence, speed, and environmental data. It also includes grouped intervals if applicable.

    Custom interval fields defined by the athlete are listed per interval with display
    name, technical code, value and units. With stream_types the raw samples of the given
    streams between each interval's start_index and end_index are evaluated (start, end,
    min, max, mean, delta and the number of non-null samples), which yields per-interval
    values for any stream Intervals.icu does not summarise itself: custom streams such as
    stamina (delta = stamina drop during the interval), performance condition or grade
    adjusted speed, a second power meter (secondary_power), gear selection and so on.
    Groups are evaluated over all their member intervals. Statistics are computed from
    the recorded samples only; missing samples are never interpolated.

    Args:
        activity_id: The Intervals.icu activity ID
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
        stream_types: Comma-separated stream types to evaluate per interval, e.g.
            "Stamina,PotentialStamina,secondary_power"; "custom" = every custom stream of the
            activity plus secondary_power; "all" = every stream. Use list_activity_streams to
            see what is available. (optional, default: no stream metrics)
        include_custom_fields: List custom interval fields per interval (optional, default True)
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

    interval_field_defs: CustomFieldDefs = {}
    if include_custom_fields:
        interval_field_defs = await _custom_defs(INTERVAL_FIELD, api_key)

    streams: list[dict[str, Any]] | None = None
    stream_defs: CustomFieldDefs = {}
    note = ""
    if stream_types:
        streams, error = await _fetch_streams(
            activity_id, api_key, _stream_request_params(stream_types, ensure_time=True)
        )
        if error:
            note = f"\nNote: stream metrics unavailable. {error}\n"
            streams = None
        else:
            if stream_types.strip().lower() == "custom":
                streams = [
                    s for s in streams if s.get("custom") or s.get("type") == "secondary_power"
                ]
            stream_defs = await _custom_defs(ACTIVITY_STREAM, api_key)

    # Format the intervals data
    return (
        format_intervals(
            result,
            interval_field_defs=interval_field_defs,
            streams=streams,
            stream_defs=stream_defs,
        )
        + note
    )


def _render_stream_rows(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
    activity_id: str,
    streams: list[dict[str, Any]],
    stream_defs: CustomFieldDefs,
    output_format: str,
    window: tuple[int | None, int | None, int | None, int | None],
    downsample: int,
    max_points: int,
) -> str:
    """Render the selected sample range of the streams as CSV table or JSON."""
    start_index, end_index, start_time, end_time = window
    length = stream_length(streams)
    time_stream = find_stream(streams, "time")
    start, end = resolve_sample_range(
        length,
        time_stream.get("data") if time_stream else None,
        start_index,
        end_index,
        start_time,
        end_time,
    )

    total = len(range(start, end, downsample))
    cut_end = end
    note = ""
    if total > max_points:
        cut_end = start + max_points * downsample
        note = (
            f"\nNote: output cut to {max_points} of {total} samples (indices {start}-{cut_end - 1}). "
            f"Continue with start_index={cut_end}, or raise downsample or max_points.\n"
        )

    resolution = "full sample resolution" if downsample == 1 else f"every {downsample}. sample"
    header = (
        f"Activity Streams for {activity_id}: samples {start}-{max(start, cut_end - 1)} of {length} "
        f"({resolution}). time = seconds since activity start; empty/null = no value.\n"
    )
    header += "Streams: " + ", ".join(
        stream_label(describe_stream(s, stream_defs)) for s in order_streams(streams)
    ) + "\n"
    if cut_end <= start:
        return header + "No samples in the selected range.\n"

    if output_format == "json":
        body = json.dumps(
            render_streams_json(streams, stream_defs, start, cut_end, downsample),
            ensure_ascii=False,
        )
        body += "\n"
    else:
        body = render_streams_table(streams, start, cut_end, downsample)
    return header + body + note


@mcp.tool()
async def get_activity_streams(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    activity_id: str,
    api_key: str | None = None,
    stream_types: str | None = None,
    output_format: str = "summary",
    start_index: int | None = None,
    end_index: int | None = None,
    start_time: int | None = None,
    end_time: int | None = None,
    downsample: int = 1,
    max_points: int = 10000,
) -> str:
    """Get time-series (stream) data for a specific activity from Intervals.icu

    Any stream the activity has can be requested by its technical type: the standard
    streams (time, watts, heartrate, cadence, altitude, distance, velocity_smooth, temp,
    torque, left_right_balance, hrv, respiration, secondary_power, ...) and every custom
    stream the athlete has defined, addressed by its code (for example Stamina,
    PotentialStamina, GarminGASpeed, FrontGear, RearGear ...). Use list_activity_streams
    to discover what an activity offers. All streams of an activity are sample-aligned:
    index i of every stream belongs to the same recorded sample and time[i] is its offset
    in seconds from the activity start. Recording pauses appear as jumps in time, so use
    the time column, not the index, as the timestamp.

    Args:
        activity_id: The Intervals.icu activity ID
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
        stream_types: Comma-separated stream types to retrieve, or "all" for every stream of
            the activity (optional, defaults to time,watts,heartrate,cadence,altitude,distance,velocity_smooth)
        output_format: "summary" (default) = per-stream metadata, statistics and a short preview;
            "full" = CSV table with one row per sample (index, time, one column per stream,
            empty cell = no value); "json" = the same selection as JSON arrays (null = no value).
            The time stream is always included in full/json output.
        start_index: First sample index of the full/json output (optional, default 0; matches
            start_index of get_activity_intervals)
        end_index: Sample index to stop before in full/json output (optional, default = end;
            matches end_index of get_activity_intervals, which is exclusive)
        start_time: Only samples with time >= start_time seconds (optional, full/json)
        end_time: Only samples with time < end_time seconds (optional, full/json)
        downsample: Keep every n-th recorded sample in full/json output (optional, default 1 =
            full sample resolution; samples are skipped, never averaged)
        max_points: Maximum number of samples in full/json output (optional, default 10000).
            Longer selections are cut and the response says how to continue (page with
            start_index, or raise downsample or max_points).
    """
    output_format = (output_format or "summary").strip().lower()
    if output_format not in STREAM_OUTPUT_FORMATS:
        return f"Error: output_format must be one of {', '.join(STREAM_OUTPUT_FORMATS)}."
    if downsample < 1 or max_points < 1:
        return "Error: downsample and max_points must be positive integers."

    params = _stream_request_params(stream_types, ensure_time=output_format != "summary")
    streams, error = await _fetch_streams(activity_id, api_key, params)
    if error:
        return error

    stream_defs = await _custom_defs(ACTIVITY_STREAM, api_key)

    if output_format == "summary":
        return format_streams_summary(activity_id, streams, stream_defs)

    return _render_stream_rows(
        activity_id,
        streams,
        stream_defs,
        output_format,
        (start_index, end_index, start_time, end_time),
        downsample,
        max_points,
    )


def _format_stream_listing(
    activity_id: str,
    activity: dict[str, Any],
    available: list[Any],
    streams: list[dict[str, Any]],
    stream_defs: CustomFieldDefs,
) -> str:
    """Render the stream listing of list_activity_streams."""
    by_type = {s.get("type"): s for s in streams}
    standard: list[str] = []
    custom: list[str] = []
    for stream_type in available:
        stream = by_type.get(stream_type) or {
            "type": stream_type,
            "custom": stream_type in stream_defs,
        }
        info = describe_stream(stream, stream_defs)
        line = f"- {stream_label(info)}"
        if info["description"]:
            line += f": {info['description']}"
        data = stream.get("data")
        if isinstance(data, list) and stream_type != "latlng":
            line += f" | {format_stats(range_stats(data, [(0, len(data))]))}"
        (custom if info["custom"] else standard).append(line)

    output = (
        f"Streams available for activity {activity_id} ('{activity.get('name', 'Unnamed')}', "
        f"start {activity.get('start_date_local', 'unknown')}, "
        f"elapsed {activity.get('elapsed_time', 'N/A')} s):\n"
    )
    power_fields = activity.get("power_field_names")
    if isinstance(power_fields, list) and power_fields:
        output += f"Power fields: {', '.join(str(p) for p in power_fields)}\n"
    output += f"\nStandard streams ({len(standard)}):\n" + "\n".join(standard or ["- (none)"]) + "\n"
    output += f"\nCustom streams ({len(custom)}):\n" + "\n".join(custom or ["- (none)"]) + "\n"
    output += (
        "\nRequest samples with get_activity_streams(activity_id, stream_types='time,watts,<type>', "
        "output_format='full') and evaluate streams per interval with "
        "get_activity_intervals(activity_id, stream_types='<type>').\n"
    )
    return output


@mcp.tool()
async def list_activity_streams(
    activity_id: str,
    api_key: str | None = None,
    include_stats: bool = False,
) -> str:
    """List every data stream available for an activity on Intervals.icu

    Returns the standard streams and the custom streams (defined by the athlete, for
    example streams a device records such as stamina, potential stamina, performance
    condition, grade adjusted speed, gear selection, battery ...) present on the activity,
    with display name, units and description. Use the listed stream types with
    get_activity_streams (full sample data) or get_activity_intervals(stream_types=...)
    (per-interval statistics).

    Args:
        activity_id: The Intervals.icu activity ID
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
        include_stats: Also download the streams and report sample count, non-null count and
            start/end/min/max/mean per stream (optional, default False)
    """
    result = await make_intervals_request(url=f"/activity/{activity_id}", api_key=api_key)

    if isinstance(result, dict) and "error" in result:
        error_message = result.get("message", "Unknown error")
        return f"Error fetching activity details: {error_message}"

    activity = result[0] if isinstance(result, list) and result else result
    if not isinstance(activity, dict) or not activity:
        return f"No details found for activity {activity_id}."

    stream_defs = await _custom_defs(ACTIVITY_STREAM, api_key, activity.get("icu_athlete_id"))

    available = activity.get("stream_types")
    streams: list[dict[str, Any]] = []
    if include_stats or not isinstance(available, list) or not available:
        streams, error = await _fetch_streams(activity_id, api_key, None)
        if error and not available:
            return error
        if streams:
            available = [s.get("type") for s in streams]

    if not isinstance(available, list) or not available:
        return f"No streams found for activity {activity_id}."

    return _format_stream_listing(activity_id, activity, available, streams, stream_defs)


@mcp.tool()
async def get_activity_messages(activity_id: str, api_key: str | None = None) -> str:
    """Get messages (notes/comments) for a specific activity from Intervals.icu

    Args:
        activity_id: The Intervals.icu activity ID
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
    """
    result = await make_intervals_request(
        url=f"/activity/{activity_id}/messages",
        api_key=api_key,
    )

    if isinstance(result, dict) and "error" in result:
        error_message = result.get("message", "Unknown error")
        return f"Error fetching activity messages: {error_message}"

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
    result = await make_intervals_request(
        url=f"/activity/{activity_id}/messages",
        api_key=api_key,
        method="POST",
        data={"content": content},
    )

    if isinstance(result, dict) and "error" in result:
        error_message = result.get("message", "Unknown error")
        return f"Error adding message to activity: {error_message}"

    if not result or not isinstance(result, dict):
        return "Error: Unexpected response when adding message."

    msg_id = result.get("id")
    if msg_id is not None:
        return f"Successfully added message (ID: {msg_id}) to activity {activity_id}."
    return f"Message appears to have been added to activity {activity_id}, but no ID was returned. Please verify manually."
