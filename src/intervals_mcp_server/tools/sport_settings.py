"""
Sport settings MCP tools for Intervals.icu.

This module contains tools for retrieving and updating athlete sport settings
(FTP, LTHR, max HR, power zones, etc.).
"""

from typing import Any

from intervals_mcp_server.api.client import make_intervals_request
from intervals_mcp_server.config import get_config
from intervals_mcp_server.utils.validation import resolve_athlete_id

# Import mcp instance from shared module for tool registration
from intervals_mcp_server.mcp_instance import mcp  # noqa: F401

config = get_config()


@mcp.tool()
async def get_sport_settings(
    sport_type: str = "Ride",
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Get current sport settings (FTP, LTHR, zones, etc.) for a sport.

    Args:
        sport_type: Sport type identifier (e.g. "Ride", "Run", "Swim"). Defaults to "Ride".
                   Matches the sport settings grouping in Intervals.icu.
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)

    Returns:
        Formatted string with current sport settings.
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    # List all sport settings to find the one matching our sport type
    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/sport-settings",
        api_key=api_key,
    )

    if isinstance(result, dict) and "error" in result:
        error_message = result.get("message", "Unknown error")
        return f"Error fetching sport settings: {error_message}"

    if not isinstance(result, list):
        return "Error: Unexpected response when fetching sport settings."

    # Find the settings matching the requested sport type
    for settings in result:
        types = settings.get("types", [])
        if sport_type in types:
            output_parts = [f"Sport settings for {sport_type}:"]
            useful_fields = [
                ("ftp", "FTP (W)"),
                ("indoor_ftp", "Indoor FTP (W)"),
                ("lthr", "LTHR (bpm)"),
                ("max_hr", "Max HR (bpm)"),
                ("p_max", "Pmax (W)"),
                ("w_prime", "W' (kJ)"),
                ("sweet_spot_min", "Sweet Spot Min (%FTP)"),
                ("sweet_spot_max", "Sweet Spot Max (%FTP)"),
                ("threshold_pace", "Threshold Pace"),
                ("hr_load_type", "HR Load Type"),
                ("gap_model", "GAP Model"),
            ]
            for field_key, field_label in useful_fields:
                value = settings.get(field_key)
                if value is not None:
                    output_parts.append(f"  {field_label}: {value}")

            hr_zones = settings.get("hr_zones")
            if hr_zones:
                zone_labels = settings.get("hr_zone_names", [])
                parts = []
                for i, zone in enumerate(hr_zones):
                    label = zone_labels[i] if i < len(zone_labels) else f"Zone {i + 1}"
                    parts.append(f"{label}: {zone}")
                output_parts.append(f"  HR Zones: {', '.join(parts)}")

            power_zones = settings.get("power_zones")
            if power_zones:
                zone_labels = settings.get("power_zone_names", [])
                parts = []
                for i, zone in enumerate(power_zones):
                    label = zone_labels[i] if i < len(zone_labels) else f"Zone {i + 1}"
                    parts.append(f"{label}: {zone}")
                output_parts.append(f"  Power Zones: {', '.join(parts)}")

            default_gear = settings.get("default_gear_id")
            if default_gear:
                output_parts.append(f"  Default Gear ID: {default_gear}")
            indoor_gear = settings.get("default_indoor_gear_id")
            if indoor_gear:
                output_parts.append(f"  Default Indoor Gear ID: {indoor_gear}")

            return "\n".join(output_parts)

    return (f"No sport settings found for '{sport_type}'. "
            f"Available types are defined in the activity types for each sport settings record.")


@mcp.tool()
async def update_sport_settings(
    sport_type: str = "Ride",
    ftp: int | None = None,
    indoor_ftp: int | None = None,
    lthr: int | None = None,
    max_hr: int | None = None,
    p_max: int | None = None,
    w_prime: int | None = None,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Update sport settings (FTP, LTHR, etc.) for a sport type.

    Only the fields you provide are updated — unspecified fields are left unchanged.

    Args:
        sport_type: Sport type identifier (e.g. "Ride", "Run", "Swim"). Defaults to "Ride".
                   Matches the sport settings grouping in Intervals.icu.
        ftp: Functional Threshold Power in watts (optional)
        indoor_ftp: Indoor FTP in watts, typically slightly lower than outdoor FTP (optional)
        lthr: Lactate Threshold Heart Rate in bpm (optional)
        max_hr: Maximum Heart Rate in bpm (optional)
        p_max: Maximum power output in watts (optional)
        w_prime: W' (Anaerobic Work Capacity) in kJ (optional)
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)

    Returns:
        Confirmation message with updated values.
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    # Build payload with only the fields the caller explicitly set
    payload: dict[str, Any] = {}
    if ftp is not None:
        payload["ftp"] = ftp
    if indoor_ftp is not None:
        payload["indoor_ftp"] = indoor_ftp
    if lthr is not None:
        payload["lthr"] = lthr
    if max_hr is not None:
        payload["max_hr"] = max_hr
    if p_max is not None:
        payload["p_max"] = p_max
    if w_prime is not None:
        payload["w_prime"] = w_prime

    if not payload:
        return "Error: No fields to update. Provide at least ftp, indoor_ftp, lthr, max_hr, p_max, or w_prime."

    # The sport-settings/{id} endpoint accepts the sport type name as the id parameter
    url = f"/athlete/{athlete_id_to_use}/sport-settings/{sport_type}"

    result = await make_intervals_request(
        url=url,
        api_key=api_key,
        data=payload,
        method="PUT",
    )

    if isinstance(result, dict) and "error" in result:
        error_message = result.get("message", "Unknown error")
        return f"Error updating sport settings: {error_message}"

    if not result or not isinstance(result, dict):
        return "Error: Unexpected response when updating sport settings."

    updated_fields = list(payload)
    updated_values = ", ".join(f"{k}={v}" for k, v in payload.items())
    return (f"Successfully updated {sport_type} sport settings "
            f"({', '.join(updated_fields)}): {updated_values}")
