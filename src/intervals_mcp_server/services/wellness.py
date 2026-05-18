"""Wellness domain service for Intervals.icu."""

from typing import Any

from intervals_mcp_server.api.client import make_intervals_request


async def get_wellness(
    athlete_id: str,
    api_key: str | None,
    start_date: str,
    end_date: str,
) -> dict[str, Any] | list[dict[str, Any]]:
    """Fetch wellness data for an athlete in the given date range."""
    return await make_intervals_request(
        url=f"/athlete/{athlete_id}/wellness",
        api_key=api_key,
        params={"oldest": start_date, "newest": end_date},
    )
