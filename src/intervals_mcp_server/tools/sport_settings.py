"""
Sport settings MCP tools for Intervals.icu.

This module contains tools for reading and updating per-sport settings
(FTP, LTHR, max HR, zones) and the athlete weight.
"""

from typing import Any
from urllib.parse import quote

from intervals_mcp_server.api.client import make_intervals_request
from intervals_mcp_server.config import get_config
from intervals_mcp_server.utils.formatting import format_sport_settings
from intervals_mcp_server.utils.validation import resolve_athlete_id

# Import mcp instance from shared module for tool registration
from intervals_mcp_server.mcp_instance import mcp  # noqa: F401

config = get_config()

# Sanity limits (inclusive) for values accepted by update_sport_settings.
_LIMITS: dict[str, tuple[int, int]] = {"ftp": (50, 1000), "lthr": (80, 230), "max_hr": (80, 230)}


async def _fetch_weight(athlete_id: str, api_key: str | None) -> float | None:
    """Fetch the athlete weight in kg (icu_weight, falling back to weight)."""
    result = await make_intervals_request(url=f"/athlete/{athlete_id}", api_key=api_key)
    if not isinstance(result, dict) or result.get("error"):
        return None
    for key in ("icu_weight", "weight"):
        value = result.get(key)
        if isinstance(value, (int, float)) and value > 0:
            return float(value)
    return None


@mcp.tool()
async def get_sport_settings(
    sport: str | None = None,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Get sport settings (FTP, LTHR, max HR, zones) and athlete weight from Intervals.icu.

    Power zones are shown as percent of FTP together with watt ranges; heart rate zones
    are shown as bpm ranges. Pace is shown only as the threshold pace (pace zones are not
    shown). Returns all sports, or a single one if `sport` is given.

    Args:
        sport: Activity type such as Ride, Run or Swim (optional, defaults to all sports)
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    url = f"/athlete/{athlete_id_to_use}/sport-settings"
    if sport:
        url += f"/{quote(sport, safe='')}"
    result = await make_intervals_request(url=url, api_key=api_key)

    if isinstance(result, dict) and "error" in result:
        return f"Error fetching sport settings: {result.get('message')}"

    items: list[dict[str, Any]]
    if isinstance(result, list):
        items = [item for item in result if isinstance(item, dict)]
    elif isinstance(result, dict) and result:
        items = [result]
    else:
        items = []

    if not items:
        return f"No sport settings found for athlete {athlete_id_to_use}."

    weight = await _fetch_weight(athlete_id_to_use, api_key)
    return "\n\n".join(format_sport_settings(item, weight=weight) for item in items)


@mcp.tool()
async def update_sport_settings(
    sport: str,
    ftp: int | None = None,
    lthr: int | None = None,
    max_hr: int | None = None,
    recalc_hr_zones: bool = False,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """WRITE: modify sport settings (FTP, LTHR, max HR) in Intervals.icu.

    This tool MODIFIES data in Intervals.icu. Only the values passed are sent in the
    request; at least one of ftp, lthr or max_hr is required. Whether the API leaves all
    other fields unchanged is not guaranteed by its specification. Returns the updated settings.

    Args:
        sport: Activity type such as Ride, Run or Swim
        ftp: New FTP in watts, 50-1000 (optional)
        lthr: New lactate threshold heart rate in bpm, 80-230 (optional)
        max_hr: New maximum heart rate in bpm, 80-230 (optional; must be above lthr if both are given)
        recalc_hr_zones: If False (default), the existing HR zone boundaries are kept and will
            not follow a new LTHR/max HR. If True, Intervals.icu regenerates the HR zones,
            overwriting any custom zones.
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
    """
    if not sport:
        return "Error: sport is required (e.g. Ride, Run, Swim)."

    changes = {"ftp": ftp, "lthr": lthr, "max_hr": max_hr}
    payload = {key: value for key, value in changes.items() if value is not None}
    if not payload:
        return "Error: at least one of ftp, lthr or max_hr must be provided."
    for key, (low, high) in _LIMITS.items():
        value = payload.get(key)
        if value is not None and not low <= value <= high:
            return f"Error: {key} must be between {low} and {high}."
    if lthr is not None and max_hr is not None and lthr >= max_hr:
        return "Error: lthr must be lower than max_hr."

    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    params = {"recalcHrZones": "true" if recalc_hr_zones else "false"}
    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/sport-settings/{quote(sport, safe='')}",
        api_key=api_key,
        method="PUT",
        data=payload,
        params=params,
    )

    if isinstance(result, dict) and "error" in result:
        return f"Error updating sport settings: {result.get('message')}"
    if not isinstance(result, dict) or not result:
        return "Error: unexpected empty response when updating sport settings."

    weight = await _fetch_weight(athlete_id_to_use, api_key)
    return "Sport settings updated.\n\n" + format_sport_settings(result, weight=weight)
