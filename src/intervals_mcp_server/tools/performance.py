"""
Performance data MCP tools for Intervals.icu.

This module contains tools for retrieving athlete performance data including power curves,
heart rate curves, and pace curves.
"""

from intervals_mcp_server.api.client import make_intervals_request
from intervals_mcp_server.config import get_config
from intervals_mcp_server.utils.validation import resolve_athlete_id

# Import mcp instance from shared module for tool registration
from intervals_mcp_server.mcp_instance import mcp  # noqa: F401

config = get_config()


@mcp.tool()
async def get_power_curves(
    athlete_id: str | None = None,
    api_key: str | None = None,
    activity_type: str = "Ride",
) -> str:
    """Get power curve data for an athlete from Intervals.icu

    Returns best power outputs across different durations for various time periods.
    Shows peak capabilities and performance progression over time.

    Args:
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
        activity_type: Activity type to get curves for (default: "Ride", can be "Run", "Swim", etc.)
    """
    # Resolve athlete ID
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    # Call the Intervals.icu API
    params = {"type": activity_type}

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/power-curves.json",
        api_key=api_key,
        params=params,
    )

    if isinstance(result, dict) and "error" in result:
        return f"Error fetching power curves: {result.get('message')}"

    # Format the response
    if not result or not isinstance(result, dict) or not result.get("list"):
        return f"No power curve data found for athlete {athlete_id_to_use} with activity type '{activity_type}'."

    output = [f"Power Curves for {activity_type}:\n"]

    for period in result["list"]:
        output.append(f"\n{period['label']} ({period['days']} days)")
        output.append(f"  Period: {period['start_date_local']} to {period['end_date_local']}")

        # Get the watts and secs arrays
        watts = period.get("watts", [])
        secs = period.get("secs", [])

        if not watts or not secs:
            output.append("  No power data available")
            continue

        # Show key power metrics
        output.append("\n  Key Power Outputs:")

        # Define durations to show
        key_durations = {
            "5 sec": 5,
            "15 sec": 15,
            "30 sec": 30,
            "1 min": 60,
            "2 min": 120,
            "5 min": 300,
            "8 min": 480,
            "10 min": 600,
            "20 min": 1200,
            "30 min": 1800,
            "1 hour": 3600,
            "2 hours": 7200,
        }

        for label, target_secs in key_durations.items():
            # Find closest matching duration
            idx = next((i for i, s in enumerate(secs) if s >= target_secs), None)
            if idx is not None and idx < len(watts):
                power = watts[idx]
                actual_secs = secs[idx]
                output.append(f"    {label:10} {power:4.0f}W (at {actual_secs}s)")

        # Show summary stats if available
        if period.get("moving_time"):
            moving_hours = period["moving_time"] / 3600
            output.append(f"\n  Total Moving Time: {moving_hours:.1f} hours")
        if period.get("training_load"):
            output.append(f"  Total Training Load: {period['training_load']}")

    return "\n".join(output)


@mcp.tool()
async def get_hr_curves(
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Get heart rate curve data for an athlete from Intervals.icu

    Returns best heart rate efforts across different durations for various time periods.

    Args:
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
    """
    # Resolve athlete ID
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    # Call the Intervals.icu API
    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/hr-curves.json", api_key=api_key
    )

    if isinstance(result, dict) and "error" in result:
        return f"Error fetching HR curves: {result.get('message')}"

    # Format the response
    if not result or not isinstance(result, dict) or not result.get("list"):
        return f"No HR curve data found for athlete {athlete_id_to_use}."

    output = ["Heart Rate Curves:\n"]

    for period in result["list"]:
        output.append(f"\n{period['label']} ({period['days']} days)")
        output.append(f"  Period: {period['start_date_local']} to {period['end_date_local']}")

        # Get the HR values and secs arrays
        hr_values = period.get("values", [])  # HR data uses 'values' field
        secs = period.get("secs", [])

        if not hr_values or not secs:
            output.append("  No HR data available")
            continue

        # Show key HR metrics
        output.append("\n  Peak Heart Rates:")

        # Define durations to show
        key_durations = {
            "10 sec": 10,
            "30 sec": 30,
            "1 min": 60,
            "3 min": 180,
            "5 min": 300,
            "10 min": 600,
            "20 min": 1200,
            "30 min": 1800,
            "1 hour": 3600,
        }

        for label, target_secs in key_durations.items():
            # Find closest matching duration
            idx = next((i for i, s in enumerate(secs) if s >= target_secs), None)
            if idx is not None and idx < len(hr_values):
                hr = hr_values[idx]
                actual_secs = secs[idx]
                output.append(f"    {label:10} {hr:3.0f} bpm (at {actual_secs}s)")

    return "\n".join(output)


@mcp.tool()
async def get_pace_curves(
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Get pace curve data for an athlete from Intervals.icu

    Returns best pace performances across different distances for various time periods.

    Args:
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
    """
    # Resolve athlete ID
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    # Call the Intervals.icu API
    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/pace-curves.json", api_key=api_key
    )

    if isinstance(result, dict) and "error" in result:
        return f"Error fetching pace curves: {result.get('message')}"

    # Format the response
    if not result or not isinstance(result, dict) or not result.get("list"):
        return f"No pace curve data found for athlete {athlete_id_to_use}."

    output = ["Pace Curves:\n"]

    for period in result["list"]:
        output.append(f"\n{period['label']} ({period['days']} days)")
        output.append(f"  Period: {period['start_date_local']} to {period['end_date_local']}")

        # Get the distance and pace (secs) arrays
        distances = period.get("distance", [])  # in meters
        paces = period.get("secs", [])  # seconds per distance

        if not distances or not paces:
            output.append("  No pace data available")
            continue

        # Show key pace metrics
        output.append("\n  Best Paces:")

        # Define key distances to show (in meters)
        key_distances = {
            "400m": 400,
            "800m": 800,
            "1 km": 1000,
            "1 mile": 1609,
            "5 km": 5000,
            "10 km": 10000,
            "Half Marathon": 21097,
            "Marathon": 42195,
        }

        for label, target_dist in key_distances.items():
            # Find closest matching distance
            idx = next((i for i, d in enumerate(distances) if d >= target_dist), None)
            if idx is not None and idx < len(paces):
                pace_secs = paces[idx]
                actual_dist = distances[idx]

                # Calculate pace per km
                pace_per_km = (pace_secs / actual_dist) * 1000
                mins = int(pace_per_km // 60)
                secs = int(pace_per_km % 60)

                output.append(
                    f"    {label:15} {mins:2d}:{secs:02d}/km (at {actual_dist:.0f}m)"
                )

    return "\n".join(output)