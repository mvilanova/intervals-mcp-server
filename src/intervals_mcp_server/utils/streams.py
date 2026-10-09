"""
Stream helpers for Intervals.icu MCP Server.

Activity streams are sample-aligned arrays: every stream of an activity has the
same length, and index ``i`` of each stream belongs to the same recorded sample,
whose offset in seconds from the activity start is ``time[i]``. Recording pauses
show up as jumps in the ``time`` stream, so ``time`` (not the index) is the
timestamp. Interval boundaries from the intervals endpoint are ``start_index`` /
``end_index`` (end exclusive) into these arrays, and ``start_time`` / ``end_time``
are the matching ``time`` values.

This module computes statistics over index ranges and renders streams as a sample
table (CSV) or JSON. Nothing is interpolated or resampled: ``downsample`` keeps
every n-th recorded sample, nulls stay empty and NaN becomes null.
"""

import bisect
import csv
import io
import json
import math
from typing import Any

from intervals_mcp_server.utils.custom_fields import CustomFieldDefs, format_value, is_missing

# Units of the standard Intervals.icu streams (only the unambiguous ones). Any
# other stream, including every custom stream, gets its units from the athlete's
# custom item definition or is reported without units.
STANDARD_STREAM_UNITS: dict[str, str] = {
    "time": "s",
    "watts": "W",
    "raw_watts": "W",
    "fixed_watts": "W",
    "secondary_power": "W",
    "heartrate": "bpm",
    "cadence": "rpm",
    "distance": "m",
    "altitude": "m",
    "fixed_altitude": "m",
    "velocity_smooth": "m/s",
    "grade_smooth": "%",
    "temp": "°C",
    "torque": "Nm",
    "respiration": "breaths/min",
    "hrv": "ms",
    "latlng": "deg",
    "left_right_balance": "%",
    "core_temperature": "°C",
    "skin_temperature": "°C",
}

# Streams requested by get_activity_streams when the caller does not specify any.
DEFAULT_STREAM_TYPES = "time,watts,heartrate,cadence,altitude,distance,velocity_smooth"

# Streams whose per-range statistics are meaningless.
NON_METRIC_STREAM_TYPES = ("time", "latlng")


_DESCRIPTION_MAX_CHARS = 160


def _one_line(text: Any, limit: int = _DESCRIPTION_MAX_CHARS) -> str | None:
    """Collapse whitespace of a description to one line and cap its length."""
    if not isinstance(text, str):
        return None
    collapsed = " ".join(text.split())
    if not collapsed:
        return None
    if len(collapsed) > limit:
        return collapsed[: limit - 1].rstrip() + "…"
    return collapsed


def describe_stream(stream: dict[str, Any], stream_defs: CustomFieldDefs) -> dict[str, Any]:
    """Resolve display name, units, description and custom flag of a stream."""
    stream_type = str(stream.get("type") or "unknown")
    definition = stream_defs.get(stream_type)
    custom = bool(stream.get("custom")) or definition is not None
    if definition is not None:
        label = definition.get("name") or stream_type
        units = definition.get("units")
        description = _one_line(definition.get("description"))
    else:
        label = stream.get("name") or stream_type
        units = STANDARD_STREAM_UNITS.get(stream_type)
        description = None
    return {
        "type": stream_type,
        "label": str(label),
        "units": units,
        "custom": custom,
        "description": description,
    }


def stream_label(info: dict[str, Any]) -> str:
    """Compact label: 'watts (W)', 'Power2 [secondary_power] (W)', 'Garmin Stamina [Stamina] (point)'."""
    if info["label"] == info["type"]:
        text = info["type"]
    else:
        text = f"{info['label']} [{info['type']}]"
    if info.get("units"):
        text += f" ({info['units']})"
    return text


def numeric_values(values: list[Any]) -> list[int | float]:
    """Keep the numeric samples of a stream segment (drops null, NaN, arrays, booleans)."""
    out: list[int | float] = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        if isinstance(value, float) and math.isnan(value):
            continue
        out.append(value)
    return out


def range_stats(data: list[Any], ranges: list[tuple[int, int]]) -> dict[str, Any]:
    """Statistics over the samples of one or more index ranges (end exclusive)."""
    total = 0
    arrays = 0
    nums: list[int | float] = []
    for start, end in ranges:
        segment = data[start:end]
        total += len(segment)
        arrays += sum(1 for value in segment if isinstance(value, list))
        nums.extend(numeric_values(segment))
    stats: dict[str, Any] = {"samples": total, "non_null": len(nums)}
    if arrays:
        stats["arrays"] = arrays
    if nums:
        stats.update(
            first=nums[0],
            last=nums[-1],
            min=min(nums),
            max=max(nums),
            mean=sum(nums) / len(nums),
            delta=nums[-1] - nums[0],
        )
    return stats


def format_stats(stats: dict[str, Any]) -> str:
    """Render range statistics on one line."""
    if not stats.get("non_null"):
        if stats.get("arrays"):
            return (
                f"array values, no scalar statistics "
                f"({stats['arrays']}/{stats.get('samples', 0)} samples; see full output)"
            )
        return f"no numeric samples ({stats.get('samples', 0)} samples in range)"
    return ", ".join(
        [
            f"start {format_value(stats['first'])}",
            f"end {format_value(stats['last'])}",
            f"min {format_value(stats['min'])}",
            f"max {format_value(stats['max'])}",
            f"mean {format_value(round(stats['mean'], 2))}",
            f"delta {format_value(stats['delta'])}",
            f"samples {stats['non_null']}/{stats['samples']}",
        ]
    )


def format_range_metrics(
    streams: list[dict[str, Any]],
    stream_defs: CustomFieldDefs,
    ranges: list[tuple[int, int]],
) -> list[str]:
    """One statistics line per metric stream over the given sample ranges."""
    lines: list[str] = []
    for stream in streams:
        if not isinstance(stream, dict) or stream.get("type") in NON_METRIC_STREAM_TYPES:
            continue
        info = describe_stream(stream, stream_defs)
        stats = range_stats(stream.get("data") or [], ranges)
        lines.append(f"  {stream_label(info)}: {format_stats(stats)}")
    return lines


def find_stream(streams: list[dict[str, Any]], stream_type: str) -> dict[str, Any] | None:
    """Return the stream with the given type, if present."""
    for stream in streams:
        if isinstance(stream, dict) and stream.get("type") == stream_type:
            return stream
    return None


def stream_length(streams: list[dict[str, Any]]) -> int:
    """Number of samples (length of the longest stream)."""
    lengths = [len(s.get("data") or []) for s in streams if isinstance(s, dict)]
    return max(lengths) if lengths else 0


def resolve_sample_range(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    length: int,
    time_data: list[Any] | None,
    start_index: int | None = None,
    end_index: int | None = None,
    start_time: int | None = None,
    end_time: int | None = None,
) -> tuple[int, int]:
    """Clamp an index range and narrow it by start/end time (seconds since start).

    Time bounds follow the interval convention: the range covers samples with
    ``start_time <= time < end_time``. Time bounds are ignored when the time
    stream is missing or contains gaps of unknown values.
    """
    start = 0 if start_index is None else max(0, min(start_index, length))
    end = length if end_index is None else max(0, min(end_index, length))
    times = time_data if time_data and all(isinstance(t, (int, float)) for t in time_data) else None
    if times is not None:
        if start_time is not None:
            start = max(start, bisect.bisect_left(times, start_time))
        if end_time is not None:
            end = min(end, bisect.bisect_left(times, end_time))
    return start, max(start, end)


def order_streams(streams: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Put the time stream first, keep the API order otherwise."""
    valid = [s for s in streams if isinstance(s, dict)]
    time_streams = [s for s in valid if s.get("type") == "time"]
    others = [s for s in valid if s.get("type") != "time"]
    return time_streams + others


def _json_safe(value: Any) -> Any:
    if is_missing(value):
        return None
    if isinstance(value, float):
        return value
    return value


def _cell(value: Any) -> Any:
    if is_missing(value):
        return ""
    if isinstance(value, (list, dict)):
        return json.dumps(value)
    return value


def render_streams_table(
    streams: list[dict[str, Any]], start: int, end: int, step: int = 1
) -> str:
    """CSV with one row per kept sample: index, then one column per stream.

    ``latlng`` expands to ``lat,lng``; array values (e.g. hrv) are JSON encoded;
    null and NaN are empty cells.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    header = ["index"]
    columns: list[tuple[list[Any], list[Any] | None]] = []
    for stream in order_streams(streams):
        data = stream.get("data") or []
        data2 = stream.get("data2")
        if stream.get("type") == "latlng" and isinstance(data2, list):
            header.extend(["lat", "lng"])
            columns.append((data, data2))
        else:
            header.append(str(stream.get("type") or "unknown"))
            columns.append((data, None))
    writer.writerow(header)
    for index in range(start, end, step):
        row: list[Any] = [index]
        for data, data2 in columns:
            row.append(_cell(data[index] if index < len(data) else None))
            if data2 is not None:
                row.append(_cell(data2[index] if index < len(data2) else None))
        writer.writerow(row)
    return buffer.getvalue()


def render_streams_json(
    streams: list[dict[str, Any]],
    stream_defs: CustomFieldDefs,
    start: int,
    end: int,
    step: int = 1,
) -> dict[str, Any]:
    """JSON-serialisable view of the selected samples with per-stream metadata."""
    out: dict[str, Any] = {
        "index_start": start,
        "index_end": end,
        "downsample": step,
        "streams": {},
    }
    for stream in order_streams(streams):
        info = describe_stream(stream, stream_defs)
        data = stream.get("data") or []
        entry: dict[str, Any] = {
            "name": info["label"],
            "units": info["units"],
            "custom": info["custom"],
            "data": [_json_safe(v) for v in data[start:end:step]],
        }
        data2 = stream.get("data2")
        if isinstance(data2, list):
            entry["data2"] = [_json_safe(v) for v in data2[start:end:step]]
        out["streams"][info["type"]] = entry
    return out


def format_streams_summary(
    activity_id: str, streams: list[dict[str, Any]], stream_defs: CustomFieldDefs
) -> str:
    """Per-stream overview: metadata, statistics and a short preview of the samples."""
    summary = f"Activity Streams for {activity_id}:\n\n"
    for stream in streams:
        if not isinstance(stream, dict):
            continue
        info = describe_stream(stream, stream_defs)
        data = stream.get("data") or []
        summary += f"Stream: {info['label']} ({info['type']})\n"
        summary += f"  Value Type: {stream.get('valueType', '')}\n"
        summary += f"  Data Points: {len(data)}\n"
        summary += f"  Units: {info['units'] or 'not specified'}\n"
        summary += f"  Custom: {'yes' if info['custom'] else 'no'}\n"
        if info["description"]:
            summary += f"  Description: {info['description']}\n"
        summary += f"  Stats: {format_stats(range_stats(data, [(0, len(data))]))}\n"
        if data:
            if len(data) <= 10:
                summary += f"  Values: {data}\n"
            else:
                summary += f"  First 5 values: {data[:5]}\n"
                summary += f"  Last 5 values: {data[-5:]}\n"
        summary += "\n"
    return summary
