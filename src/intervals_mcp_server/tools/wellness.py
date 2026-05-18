"""
Wellness-related MCP tools for Intervals.icu.

This module contains tools for retrieving athlete wellness data.
"""

from intervals_mcp_server.utils.formatting import format_wellness_entry
from intervals_mcp_server.utils.validation import resolve_date_params
from intervals_mcp_server.tools.common import format_tool_error, is_error_result, resolve_tool_context
import intervals_mcp_server.services.wellness as wellness_service

# Import mcp instance from shared module for tool registration
from intervals_mcp_server.mcp_instance import mcp  # noqa: F401


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
    athlete_id_to_use, api_key, error_msg = resolve_tool_context(athlete_id, api_key)
    if error_msg:
        return error_msg

    start_date, end_date = resolve_date_params(start_date, end_date)

    result = await wellness_service.get_wellness(athlete_id_to_use, api_key, start_date, end_date)

    if is_error_result(result):
        return format_tool_error("fetching wellness data", result)

    if not result:
        return f"No wellness data found for athlete {athlete_id_to_use} in the specified date range."

    wellness_summary = "Wellness Data:\n\n"

    if isinstance(result, dict):
        for date_str, data in result.items():
            if isinstance(data, dict):
                if "date" not in data:
                    data["date"] = date_str
                wellness_summary += (
                    format_wellness_entry(data, include_all_fields=include_all_fields) + "\n\n"
                )
    elif isinstance(result, list):
        for entry in result:
            if isinstance(entry, dict):
                wellness_summary += (
                    format_wellness_entry(entry, include_all_fields=include_all_fields) + "\n\n"
                )

    return wellness_summary
