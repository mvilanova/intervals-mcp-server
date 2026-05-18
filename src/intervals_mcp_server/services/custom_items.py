"""Custom items domain service for Intervals.icu."""

from typing import Any

from intervals_mcp_server.api.client import make_intervals_request


async def list_custom_items(
    athlete_id: str, api_key: str | None
) -> dict[str, Any] | list[dict[str, Any]]:
    """Fetch all custom items for an athlete."""
    return await make_intervals_request(
        url=f"/athlete/{athlete_id}/custom-item", api_key=api_key
    )


async def get_custom_item(
    item_id: int, athlete_id: str, api_key: str | None
) -> dict[str, Any] | list[dict[str, Any]]:
    """Fetch a single custom item by ID."""
    return await make_intervals_request(
        url=f"/athlete/{athlete_id}/custom-item/{item_id}", api_key=api_key
    )


async def create_custom_item(
    athlete_id: str, api_key: str | None, data: dict[str, Any]
) -> dict[str, Any] | list[dict[str, Any]]:
    """Create a new custom item."""
    return await make_intervals_request(
        url=f"/athlete/{athlete_id}/custom-item",
        api_key=api_key,
        data=data,
        method="POST",
    )


async def update_custom_item(
    item_id: int, athlete_id: str, api_key: str | None, data: dict[str, Any]
) -> dict[str, Any] | list[dict[str, Any]]:
    """Update an existing custom item."""
    return await make_intervals_request(
        url=f"/athlete/{athlete_id}/custom-item/{item_id}",
        api_key=api_key,
        data=data,
        method="PUT",
    )


async def delete_custom_item(
    item_id: int, athlete_id: str, api_key: str | None
) -> dict[str, Any] | list[dict[str, Any]]:
    """Delete a custom item by ID."""
    return await make_intervals_request(
        url=f"/athlete/{athlete_id}/custom-item/{item_id}",
        api_key=api_key,
        method="DELETE",
    )
