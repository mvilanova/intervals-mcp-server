"""
Wellness-related MCP tools for Intervals.icu.

This module contains tools for retrieving and updating athlete wellness data.
"""

from intervals_mcp_server.api.client import make_intervals_request
from intervals_mcp_server.config import get_config
from intervals_mcp_server.utils.formatting import format_wellness_entry
from intervals_mcp_server.utils.validation import resolve_athlete_id, resolve_date_params

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


@mcp.tool()
async def update_wellness_data(
    date: str,
    fields: dict,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Update wellness data for an athlete on a specific date.

    Uses the Intervals.icu bulk wellness upload endpoint (PUT /athlete/{id}/wellness-bulk).
    Accepts a date and a dictionary of field name-value pairs to update.
    Custom fields are referenced by their field code (e.g. "Alcohol", "weight", "restingHR").

    Args:
        date: The date in YYYY-MM-DD format to update wellness data for.
        fields: Dictionary of field names to values (e.g. {"weight": 77.5, "Alcohol": 0.0})
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    # The bulk wellness endpoint accepts an array of objects, each with an "id" (date) plus fields
    payload = [{"id": date, **fields}]

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/wellness-bulk",
        api_key=api_key,
        method="PUT",
        data=payload,
    )

    if isinstance(result, dict) and "error" in result:
        return f"Error updating wellness data: {result.get('message')}"

    updated_fields = ", ".join(f"{k}={v}" for k, v in fields.items())
    return f"Wellness data updated for {date}: {updated_fields}"
