"""
Weather-related MCP tools for Intervals.icu.

This module contains tools for retrieving weather forecast information.
"""

from datetime import datetime

from intervals_mcp_server.api.client import make_intervals_request
from intervals_mcp_server.config import get_config
from intervals_mcp_server.utils.validation import resolve_athlete_id

# Import mcp instance from shared module for tool registration
from intervals_mcp_server.mcp_instance import mcp  # noqa: F401

config = get_config()


@mcp.tool()
async def get_weather_forecast(
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Get weather forecast information for an athlete from Intervals.icu

    Returns configured weather forecasts including location, coordinates, and provider.

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
        url=f"/athlete/{athlete_id_to_use}/weather-forecast", api_key=api_key
    )

    if isinstance(result, dict) and "error" in result:
        return f"Error fetching weather forecast: {result.get('message')}"

    # Format the response
    if not result:
        return f"No weather forecast data found for athlete {athlete_id_to_use}."

    # Extract forecasts array
    forecasts = result.get("forecasts", [])
    if not forecasts:
        return f"No weather forecasts configured for athlete {athlete_id_to_use}."

    weather_summary = "Weather Forecasts:\n\n"

    for forecast in forecasts:
        location = forecast.get("location", "Unknown")
        label = forecast.get("label", "")
        lat = forecast.get("lat", 0.0)
        lon = forecast.get("lon", 0.0)
        provider = forecast.get("provider", "Unknown")
        enabled = forecast.get("enabled", False)
        status = "Enabled" if enabled else "Disabled"

        weather_summary += f"📍 {location}"
        if label:
            weather_summary += f" ({label})"
        weather_summary += f"\n"
        weather_summary += f"   Coordinates: {lat:.4f}, {lon:.4f}\n"
        weather_summary += f"   Provider: {provider}\n"
        weather_summary += f"   Status: {status}\n\n"

        # Add daily forecast if available
        daily = forecast.get("daily", [])
        if daily:
            weather_summary += "   📅 Daily Forecast (next 7 days):\n"
            for day in daily[:7]:  # Show only next 7 days
                date_str = day.get("id", "")
                temp = day.get("temp", {})
                temp_min = temp.get("min", 0)
                temp_max = temp.get("max", 0)
                weather_list = day.get("weather", [])
                description = weather_list[0].get("description", "N/A") if weather_list else "N/A"
                rain = day.get("rain", 0)
                wind = day.get("wind_speed", 0)

                # Parse date and get day of week
                try:
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                    day_of_week = date_obj.strftime("%A")
                    formatted_date = f"{day_of_week}, {date_str}"
                except (ValueError, AttributeError):
                    formatted_date = date_str

                weather_summary += f"      {formatted_date}: {description.capitalize()}\n"
                weather_summary += f"         Temp: {temp_min:.1f}°C - {temp_max:.1f}°C"
                if rain > 0:
                    weather_summary += f", Rain: {rain:.1f}mm"
                weather_summary += f", Wind: {wind:.1f}m/s\n"

        weather_summary += "\n"

    return weather_summary