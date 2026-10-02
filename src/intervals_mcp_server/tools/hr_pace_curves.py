"""
Heart rate and pace curve MCP tools for Intervals.icu.

This module contains tools for retrieving athlete heart rate curves (best average HR
per duration) and pace curves (best time per distance). Together they are useful to
track progress, e.g. the same pace at a lower heart rate.
"""

from typing import Any

from intervals_mcp_server.api.client import make_intervals_request
from intervals_mcp_server.config import get_config
from intervals_mcp_server.tools.power_curves import _validate_dates
from intervals_mcp_server.utils.formatting import format_hr_curves, format_pace_curves
from intervals_mcp_server.utils.validation import resolve_athlete_id

# Import mcp instance from shared module for tool registration
from intervals_mcp_server.mcp_instance import mcp  # noqa: F401

config = get_config()

# 5s, 15s, 30s, 1min, 5min, 10min, 20min, 30min, 60min
DEFAULT_HR_DURATIONS: tuple[int, ...] = (5, 15, 30, 60, 300, 600, 1200, 1800, 3600)

# 400m, 800m, 1km, 3km, 5km, 10km, half marathon, marathon (metres)
DEFAULT_RUN_DISTANCES: tuple[float, ...] = (400, 800, 1000, 3000, 5000, 10000, 21097.5, 42195)

# Default swim distances in metres (reported as not available if the curve lacks them)
DEFAULT_SWIM_DISTANCES: tuple[float, ...] = (50, 100, 200, 300, 400)

DEFAULT_CURVES: tuple[str, ...] = ("90d",)

SWIM_TYPES: tuple[str, ...] = ("Swim", "OpenWaterSwim")

# Tolerance in metres when matching requested distances to curve distances
_DISTANCE_TOLERANCE = 1.0


def _build_curve_ids(
    curves: list[str] | None,
    start_date: str | None,
    end_date: str | None,
) -> list[str]:
    """Build the `curves` query parameter from curve ids and an optional date range.

    Args:
        curves: Curve identifiers such as "90d", "1y", "s0" or "r.2026-01-01.2026-03-01".
            If None and no date range is given, the default ("90d") is used.
        start_date: Optional start date (YYYY-MM-DD) of a custom range.
        end_date: Optional end date (YYYY-MM-DD) of a custom range.

    Returns:
        List of curve identifiers for the API request.
    """
    ids = [c.strip() for c in (curves or []) if c and c.strip()]
    if start_date and end_date:
        ids.append(f"r.{start_date}.{end_date}")
    if not ids:
        ids = list(DEFAULT_CURVES)
    return ids


def _curve_meta(curve: dict[str, Any]) -> dict[str, Any]:
    """Extract common metadata from a curve object."""
    return {
        "id": curve.get("id", ""),
        "label": curve.get("label", curve.get("id", "")),
        "start": curve.get("start_date_local", ""),
        "end": curve.get("end_date_local", ""),
    }


def _activity_id_at(activity_ids: list[Any], idx: int) -> str:
    """Return the activity id at an index or an empty string."""
    if idx < len(activity_ids) and activity_ids[idx] is not None:
        return str(activity_ids[idx])
    return ""


def _extract_hr_curve(curve: dict[str, Any], durations: list[int]) -> dict[str, Any]:
    """Extract best average HR (bpm) for the requested durations from a single curve."""
    secs = curve.get("secs", [])
    values = curve.get("values", [])
    activity_ids = curve.get("activity_id", [])
    sec_to_idx: dict[int, int] = {s: i for i, s in enumerate(secs)}

    data_points: list[dict[str, Any]] = []
    missing: list[int] = []
    for dur in durations:
        idx = sec_to_idx.get(dur)
        if idx is None or idx >= len(values) or not values[idx]:
            missing.append(dur)
            continue
        data_points.append(
            {
                "secs": dur,
                "bpm": values[idx],
                "activity_id": _activity_id_at(activity_ids, idx),
            }
        )
    return {**_curve_meta(curve), "data_points": data_points, "missing": missing}


def _extract_pace_curve(curve: dict[str, Any], distances: list[float]) -> dict[str, Any]:
    """Extract best times for the requested distances (metres) from a single curve."""
    curve_distances = curve.get("distance", [])
    values = curve.get("values", [])
    activity_ids = curve.get("activity_id", [])

    data_points: list[dict[str, Any]] = []
    missing: list[float] = []
    for dist in distances:
        idx = next(
            (i for i, d in enumerate(curve_distances) if abs(d - dist) <= _DISTANCE_TOLERANCE),
            None,
        )
        if idx is None or idx >= len(values) or not values[idx]:
            missing.append(dist)
            continue
        data_points.append(
            {
                "distance": dist,
                "secs": values[idx],
                "activity_id": _activity_id_at(activity_ids, idx),
            }
        )
    return {**_curve_meta(curve), "data_points": data_points, "missing": missing}


async def _fetch_curves(
    endpoint: str,
    params: dict[str, Any],
    athlete_id: str | None,
    api_key: str | None,
    label: str,
) -> tuple[list[dict[str, Any]] | None, str | None]:
    """Fetch a curve set and return (curve_list, error_message)."""
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return None, error_msg

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/{endpoint}",
        params=params,
        api_key=api_key,
    )
    if isinstance(result, dict) and "error" in result:
        return None, f"Error fetching {label}: {result.get('message', 'Unknown error')}"

    curve_list: list[Any] = []
    if isinstance(result, dict):
        curve_list = result.get("list", [])
    elif isinstance(result, list):
        curve_list = result
    return [c for c in curve_list if isinstance(c, dict)], None


@mcp.tool()
async def get_hr_curves(
    activity_type: str = "Run",
    durations: list[int] | None = None,
    curves: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Get heart rate curves for an athlete from Intervals.icu.

    Returns the best (highest) average heart rate in bpm sustained for selected durations
    across one or more time periods. Read-only.

    Args:
        activity_type: Activity type (e.g. "Run", "Ride", "Swim"). Default is "Run".
        durations: Durations in seconds to include. Default is [5, 15, 30, 60, 300, 600, 1200, 1800, 3600]
        curves: Curve identifiers, e.g. ["90d", "1y"], ["s0"] (this season), ["s1"] (last season)
            or ["r.2026-01-01.2026-03-01"] (custom range). Default is ["90d"].
        start_date: Start date (YYYY-MM-DD) for an additional custom range curve. Must be used with end_date.
        end_date: End date (YYYY-MM-DD) for an additional custom range curve. Must be used with start_date.
        athlete_id: Intervals.icu athlete ID (optional, uses ATHLETE_ID from .env if not provided)
        api_key: Optional API key override. Uses API_KEY from .env if not provided.
    """
    date_error = _validate_dates(start_date, end_date)
    if date_error:
        return date_error

    durations_to_use = list(durations) if durations else list(DEFAULT_HR_DURATIONS)
    params: dict[str, Any] = {
        "curves": _build_curve_ids(curves, start_date, end_date),
        "type": activity_type,
    }

    curve_list, error = await _fetch_curves("hr-curves", params, athlete_id, api_key, "HR curves")
    if error:
        return error
    if not curve_list:
        return f"No HR curve data found ({activity_type})."

    extracted = [_extract_hr_curve(c, durations_to_use) for c in curve_list]
    return format_hr_curves(extracted, activity_type)


@mcp.tool()
async def get_pace_curves(
    activity_type: str = "Run",
    distances: list[float] | None = None,
    curves: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    gap: bool = False,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Get pace curves for an athlete from Intervals.icu.

    Returns the best time and pace for selected distances across one or more time periods.
    Pace is shown as min/km (min/100m for swims). Read-only.

    Args:
        activity_type: Activity type (e.g. "Run", "Swim", "TrailRun"). Default is "Run".
        distances: Distances in metres to include. Default for runs is
            [400, 800, 1000, 3000, 5000, 10000, 21097.5, 42195]; for swims [50, 100, 200, 300, 400].
            Distances not present in the curve are listed as not available.
        curves: Curve identifiers, e.g. ["90d", "1y"], ["s0"] (this season), ["s1"] (last season)
            or ["r.2026-01-01.2026-03-01"] (custom range). Default is ["90d"].
        start_date: Start date (YYYY-MM-DD) for an additional custom range curve. Must be used with end_date.
        end_date: End date (YYYY-MM-DD) for an additional custom range curve. Must be used with start_date.
        gap: Use gradient adjusted pace (GAP) instead of raw pace (default False).
        athlete_id: Intervals.icu athlete ID (optional, uses ATHLETE_ID from .env if not provided)
        api_key: Optional API key override. Uses API_KEY from .env if not provided.
    """
    date_error = _validate_dates(start_date, end_date)
    if date_error:
        return date_error

    is_swim = activity_type in SWIM_TYPES
    if distances:
        distances_to_use = [float(d) for d in distances]
    else:
        distances_to_use = list(DEFAULT_SWIM_DISTANCES if is_swim else DEFAULT_RUN_DISTANCES)

    params: dict[str, Any] = {
        "curves": _build_curve_ids(curves, start_date, end_date),
        "type": activity_type,
    }
    if gap:
        params["gap"] = True

    curve_list, error = await _fetch_curves(
        "pace-curves", params, athlete_id, api_key, "pace curves"
    )
    if error:
        return error
    if not curve_list:
        return f"No pace curve data found ({activity_type})."

    extracted = [_extract_pace_curve(c, distances_to_use) for c in curve_list]
    return format_pace_curves(extracted, activity_type, gap, per_100m=is_swim)
