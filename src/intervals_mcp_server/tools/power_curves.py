"""
Power curve MCP tools for Intervals.icu.

This module contains tools for retrieving athlete power curve data.
"""

import json
import math
from datetime import datetime
from typing import Any

from intervals_mcp_server.api.client import make_intervals_request
from intervals_mcp_server.config import get_config
from intervals_mcp_server.utils.formatting import format_power_curves
from intervals_mcp_server.utils.validation import resolve_athlete_id

# Import mcp instance from shared module for tool registration
from intervals_mcp_server.mcp_instance import mcp  # noqa: F401

config = get_config()

# 5s, 15s, 30s, 1min, 2min, 5min, 10min, 20min, 60min
DEFAULT_DURATIONS: tuple[int, ...] = (5, 15, 30, 60, 120, 300, 600, 1200, 3600)
DEFAULT_POWER_LAW_TIME_POINTS_MINUTES: tuple[float, ...] = (
    5,
    10,
    20,
    30,
    60,
    120,
    180,
    240,
    300,
)


def _format_power_law_curve(
    durations_minutes: list[float],
    powers_watts: list[float],
    time_points_minutes: list[float] | None = None,
) -> str:
    """Fit and format a power-law regression using duration in minutes."""
    if len(durations_minutes) != len(powers_watts):
        return "Error: durations_minutes and powers_watts must have the same number of values."
    if len(durations_minutes) < 3:
        return "Error: At least three duration and power points are required."

    evaluation_points = time_points_minutes or list(DEFAULT_POWER_LAW_TIME_POINTS_MINUTES)
    all_values = [*durations_minutes, *powers_watts, *evaluation_points]
    if any(not math.isfinite(value) or value <= 0 for value in all_values):
        return "Error: All durations, powers, and time points must be finite positive values."

    log_durations = [math.log(duration) for duration in durations_minutes]
    log_powers = [math.log(power) for power in powers_watts]
    point_count = len(log_durations)
    sum_log_durations = sum(log_durations)
    sum_log_powers = sum(log_powers)
    sum_log_duration_powers = sum(
        duration * power for duration, power in zip(log_durations, log_powers, strict=True)
    )
    sum_log_durations_squared = sum(duration * duration for duration in log_durations)

    denominator = (
        point_count * sum_log_durations_squared - sum_log_durations * sum_log_durations
    )
    if math.isclose(denominator, 0.0):
        return "Error: At least two distinct duration values are required."

    exponent = (
        point_count * sum_log_duration_powers - sum_log_durations * sum_log_powers
    ) / denominator
    coefficient = math.exp((sum_log_powers - exponent * sum_log_durations) / point_count)
    doubling_power_loss_percent = (1 - math.pow(2, exponent)) * 100

    lines = [
        "Power-Law Power Curve:",
        f"power = {coefficient:.4f} * duration_minutes^{exponent:.4f}",
        f"Power loss when duration doubles: {doubling_power_loss_percent:.2f}%",
        "",
        "Modeled values:",
    ]
    for duration in evaluation_points:
        power = coefficient * math.pow(duration, exponent)
        lines.append(f"  {duration:g} min: {power:.2f}W")

    return "\n".join(lines)


@mcp.tool()
async def create_power_law_curve(
    durations_minutes: list[float],
    powers_watts: list[float],
    time_points_minutes: list[float] | None = None,
) -> str:
    """Create a power curve by fitting a power-law regression to power-duration points.

    Fits the equation ``power = a * duration_minutes^b`` using least-squares
    linear regression on the natural logarithms of the supplied points.

    Args:
        durations_minutes: At least three positive duration values in minutes.
        powers_watts: Positive power values in watts, one for each duration.
        time_points_minutes: Positive durations in minutes at which to evaluate the curve.
            Defaults to [5, 10, 20, 30, 60, 120, 180, 240, 300].
    """
    return _format_power_law_curve(durations_minutes, powers_watts, time_points_minutes)


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


@mcp.tool()
async def create_athlete_power_law_curve(
    activity_type: str = "Ride",
    period: str = "this_season",
    indoor_outdoor: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    time_points_minutes: list[float] | None = None,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Create a power-law curve from an athlete's Intervals.icu power-curve data.

    Retrieves the selected power curve from Intervals.icu, converts its durations
    from seconds to minutes, and fits ``power = a * duration_minutes^b``.

    Args:
        activity_type: Activity type (e.g. "Ride", "Run", "VirtualRide").
        period: Curve to fit: "this_season", "last_season", or "custom_range".
        indoor_outdoor: Filter by location — "indoor" or "outdoor". Omit for no filtering.
        start_date: Custom-range start date (YYYY-MM-DD). Required for "custom_range".
        end_date: Custom-range end date (YYYY-MM-DD). Required for "custom_range".
        time_points_minutes: Durations in minutes at which to evaluate the fitted curve.
        athlete_id: Intervals.icu athlete ID. Uses ATHLETE_ID if omitted.
        api_key: Optional API key override. Uses API_KEY if omitted.
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    if period not in ("this_season", "last_season", "custom_range"):
        return "Error: period must be 'this_season', 'last_season', or 'custom_range'."
    if indoor_outdoor and indoor_outdoor not in ("indoor", "outdoor"):
        return "Error: indoor_outdoor must be 'indoor', 'outdoor', or omitted."

    date_error = _validate_dates(start_date, end_date)
    if date_error:
        return date_error
    if period == "custom_range" and not start_date:
        return "Error: start_date and end_date are required when period is 'custom_range'."
    if period != "custom_range" and start_date:
        return "Error: start_date and end_date can only be used with period 'custom_range'."

    curve_id = {
        "this_season": "s0",
        "last_season": "s1",
        "custom_range": f"r.{start_date}.{end_date}",
    }[period]
    params: dict[str, Any] = {
        "curves": [curve_id],
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
        api_key=api_key,
    )
    if isinstance(result, dict) and "error" in result:
        return f"Error fetching power curve: {result.get('message', 'Unknown error')}"

    curve_list = result.get("list", []) if isinstance(result, dict) else result
    if not isinstance(curve_list, list):
        return f"No power curve data found for athlete {athlete_id_to_use} ({activity_type})."
    curve = next(
        (item for item in curve_list if isinstance(item, dict) and item.get("id") == curve_id),
        None,
    )
    if curve is None:
        return f"No {period} power curve data found for athlete {athlete_id_to_use} ({activity_type})."

    seconds = curve.get("secs", [])
    powers = curve.get("values", [])
    if not isinstance(seconds, list) or not isinstance(powers, list):
        return "Error: Intervals.icu returned invalid power curve data."
    points = [
        (seconds_value / 60, power)
        for seconds_value, power in zip(seconds, powers, strict=False)
        if isinstance(seconds_value, (int, float))
        and isinstance(power, (int, float))
        and seconds_value > 0
        and power > 0
    ]
    if len(points) < 3:
        return "Error: At least three valid Intervals.icu power-curve points are required."

    durations_minutes = [duration for duration, _ in points]
    powers_watts = [power for _, power in points]
    return _format_power_law_curve(durations_minutes, powers_watts, time_points_minutes)


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
            "activity_id": (
                activity_ids[idx]
                if idx < len(activity_ids) and activity_ids[idx] is not None
                else ""
            ),
        }
        if include_normalised and idx < len(watts_per_kg):
            point["watts_per_kg"] = round(watts_per_kg[idx], 2)
            point["wkg_activity_id"] = (
                wkg_activity_ids[idx]
                if idx < len(wkg_activity_ids)
                and wkg_activity_ids[idx] is not None
                else ""
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
    activity_type: str = "Ride",
    durations: list[int] | None = None,
    indoor_outdoor: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    this_season: bool = True,
    last_season: bool = True,
    include_normalised: bool = True,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Get power curves for an athlete from Intervals.icu.

    Returns best power output for selected durations across specified time periods.
    Uses FFT power computation. Power values are in watts.

    Args:
        activity_type: Activity type (e.g. "Ride", "Run", "VirtualRide"). Default is "Ride".
        durations: Durations in seconds to include. Default is [5, 15, 30, 60, 120, 300, 600, 1200, 3600]
        indoor_outdoor: Filter by location — "indoor" or "outdoor". Omit for no filtering.
        start_date: Start date (YYYY-MM-DD) for custom date range curve. Must be used with end_date.
        end_date: End date (YYYY-MM-DD) for custom date range curve. Must be used with start_date.
        this_season: Include this season's curve (default True)
        last_season: Include last season's curve (default True)
        include_normalised: Include weight-normalised W/kg values (default True)
        athlete_id: Intervals.icu athlete ID (optional, uses ATHLETE_ID from .env if not provided)
        api_key: Optional API key override. Uses API_KEY from .env if not provided.
    """
    if durations is None:
        durations = list(DEFAULT_DURATIONS)

    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

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
        api_key=api_key,
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
