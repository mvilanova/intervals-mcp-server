"""
Power curve MCP tools for Intervals.icu.

This module contains tools for retrieving athlete power curve data.
"""

import json
from datetime import datetime
from typing import Any

from intervals_mcp_server.api.client import make_intervals_request
from intervals_mcp_server.config import get_config
from intervals_mcp_server.utils.formatting import format_power_curves
from intervals_mcp_server.utils.validation import resolve_activity_type, resolve_athlete_id

# Import mcp instance from shared module for tool registration
from intervals_mcp_server.mcp_instance import mcp  # noqa: F401

config = get_config()

# 5s, 15s, 30s, 1min, 2min, 5min, 10min, 20min, 60min
DEFAULT_DURATIONS = [5, 15, 30, 60, 120, 300, 600, 1200, 3600]


def _build_curves_param(
    this_season: bool,
    last_season: bool,
    start_date: str | None,
    end_date: str | None,
) -> list[str]:
    """Build the curves query parameter list based on user selections.

    Args:
        this_season: Whether to include this season's curve.
        last_season: Whether to include last season's curve.
        start_date: Optional start date for a custom date range curve.
        end_date: Optional end date for a custom date range curve.

    Returns:
        List of curve identifiers for the API request.
    """
    curves: list[str] = []
    if this_season:
        curves.append("s0")
    if last_season:
        curves.append("s1")
    if start_date and end_date:
        curves.append(f"r.{start_date}.{end_date}")
    return curves


def _validate_dates(start_date: str | None, end_date: str | None) -> str | None:
    """Validate that start_date and end_date are either both provided or both absent.

    Returns:
        An error message if validation fails, otherwise None.
    """
    if (start_date is None) != (end_date is None):
        return "Error: Both start_date and end_date must be provided together for a custom date range."
    if start_date and end_date:
        try:
            s = datetime.strptime(start_date, "%Y-%m-%d")
            e = datetime.strptime(end_date, "%Y-%m-%d")
            if s >= e:
                return "Error: start_date must be before end_date."
        except ValueError:
            return "Error: Dates must be in YYYY-MM-DD format."
    return None


def _extract_curve_data(
    curve: dict[str, Any],
    durations: list[int],
    include_normalised: bool,
) -> dict[str, Any]:
    """Extract power data for requested durations from a single curve.

    Args:
        curve: A single curve object from the API response.
        durations: List of durations in seconds to extract.
        include_normalised: Whether to include W/kg data.

    Returns:
        Dictionary with curve metadata and extracted data points.
    """
    secs = curve.get("secs", [])
    values = curve.get("values", [])
    activity_ids = curve.get("activity_id", [])
    watts_per_kg = curve.get("watts_per_kg", [])
    wkg_activity_ids = curve.get("wkg_activity_id", [])

    # Build a lookup from seconds to index for efficient access
    sec_to_idx: dict[int, int] = {s: i for i, s in enumerate(secs)}

    data_points: list[dict[str, Any]] = []
    for dur in durations:
        idx = sec_to_idx.get(dur)
        if idx is None or idx >= len(values):
            continue
        point: dict[str, Any] = {
            "secs": dur,
            "watts": values[idx],
            "activity_id": activity_ids[idx] if idx < len(activity_ids) else None,
        }
        if include_normalised and idx < len(watts_per_kg):
            point["watts_per_kg"] = round(watts_per_kg[idx], 2)
            point["wkg_activity_id"] = (
                wkg_activity_ids[idx] if idx < len(wkg_activity_ids) else None
            )
        data_points.append(point)

    return {
        "id": curve.get("id", ""),
        "label": curve.get("label", curve.get("id", "")),
        "start": curve.get("start_date_local", ""),
        "end": curve.get("end_date_local", ""),
        "data_points": data_points,
    }


@mcp.tool()
async def get_athlete_power_curves(
    activity_type: str,
    durations: list[int] = DEFAULT_DURATIONS,
    indoor_outdoor: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    this_season: bool = True,
    last_season: bool = True,
    include_normalised: bool = True,
    athlete_id: str | None = None,
) -> str:
    """Get power curves for an athlete from Intervals.icu.

    Returns best power output for selected durations across specified time periods.
    Uses FFT power computation. Power values are in watts.

    Args:
        activity_type: Activity type (e.g. "Ride", "Run", "VirtualRide")
        durations: Durations in seconds to include. Default is [5, 15, 30, 60, 120, 300, 600, 1200, 3600]
        indoor_outdoor: Filter by location — "indoor" or "outdoor". Omit for no filtering.
        start_date: Start date (YYYY-MM-DD) for custom date range curve. Must be used with end_date.
        end_date: End date (YYYY-MM-DD) for custom date range curve. Must be used with start_date.
        this_season: Include this season's curve (default True)
        last_season: Include last season's curve (default True)
        include_normalised: Include weight-normalised W/kg values (default True)
        athlete_id: Intervals.icu athlete ID (optional, uses ATHLETE_ID from .env if not provided)
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    activity_type = resolve_activity_type(activity_type)

    if indoor_outdoor and indoor_outdoor not in ("indoor", "outdoor"):
        return "Error: indoor_outdoor must be 'indoor', 'outdoor', or omitted."

    date_error = _validate_dates(start_date, end_date)
    if date_error:
        return date_error

    curves = _build_curves_param(this_season, last_season, start_date, end_date)
    if not curves:
        return "Error: At least one curve must be selected (this_season, last_season, or a date range)."

    params: dict[str, Any] = {
        "curves": curves,
        "type": activity_type,
        "includeRanks": False,
    }
    if indoor_outdoor:
        params["filters"] = json.dumps(
            [{"field_id": "indoor", "value": indoor_outdoor, "id": 1}]
        )

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/power-curves",
        params=params,
    )

    if isinstance(result, dict) and "error" in result:
        error_message = result.get("message", "Unknown error")
        return f"Error fetching power curves: {error_message}"

    # Response has a "list" key containing curve objects
    curve_list: list[dict[str, Any]] = []
    if isinstance(result, dict):
        curve_list = result.get("list", [])
    elif isinstance(result, list):
        curve_list = result

    if not curve_list:
        return f"No power curve data found for athlete {athlete_id_to_use} ({activity_type})."

    extracted: list[dict[str, Any]] = []
    for curve in curve_list:
        if isinstance(curve, dict):
            extracted.append(_extract_curve_data(curve, durations, include_normalised))

    if not extracted:
        return f"No power curve data found for athlete {athlete_id_to_use} ({activity_type})."

    return format_power_curves(extracted, activity_type, include_normalised)
