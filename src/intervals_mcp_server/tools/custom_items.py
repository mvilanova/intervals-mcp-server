"""
Custom items MCP tools for Intervals.icu.

This module contains tools for managing athlete custom items (charts, fields, zones, etc.)
and a per-process cache of the custom item definitions. The definitions are needed to
label custom activity fields, interval fields, streams and wellness fields (name, units,
select options), so they are fetched once per athlete and reused by the other tools.
"""

import json
from typing import Any

from intervals_mcp_server.api import client as api_client
from intervals_mcp_server.api.client import make_intervals_request
from intervals_mcp_server.config import get_config
from intervals_mcp_server.utils.custom_fields import CustomItemIndex, index_custom_items
from intervals_mcp_server.utils.formatting import format_custom_item_details
from intervals_mcp_server.utils.validation import resolve_athlete_id

# Import mcp instance from shared module for tool registration
from intervals_mcp_server.mcp_instance import mcp  # noqa: F401

config = get_config()

# Module-level cache of the raw custom item list per athlete. Errors are not cached.
_CUSTOM_ITEMS_CACHE: dict[str, list[dict[str, Any]]] = {}


async def get_custom_items_raw(
    athlete_id: str,
    api_key: str | None = None,
    *,
    refresh: bool = False,
) -> list[dict[str, Any]]:
    """Return (and cache) the raw custom item list for an athlete.

    One API call per athlete per process lifetime unless ``refresh=True`` or the
    previous fetch failed. The request is issued through ``api.client`` so that a
    monkeypatched client is honoured even when the caller patched only that module.
    """
    if not refresh and athlete_id in _CUSTOM_ITEMS_CACHE:
        return _CUSTOM_ITEMS_CACHE[athlete_id]

    result = await api_client.make_intervals_request(
        url=f"/athlete/{athlete_id}/custom-item", api_key=api_key
    )
    if not isinstance(result, list):
        return []
    items = [item for item in result if isinstance(item, dict)]
    _CUSTOM_ITEMS_CACHE[athlete_id] = items
    return items


async def get_custom_item_index(
    athlete_id: str,
    api_key: str | None = None,
    *,
    refresh: bool = False,
) -> CustomItemIndex:
    """Custom item definitions grouped by item type and code (see utils.custom_fields)."""
    return index_custom_items(await get_custom_items_raw(athlete_id, api_key, refresh=refresh))


def invalidate_custom_items_cache(athlete_id: str) -> None:
    """Drop the cached definitions of an athlete (after create/update/delete)."""
    _CUSTOM_ITEMS_CACHE.pop(athlete_id, None)


@mcp.tool()
async def get_custom_items(
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Get custom items (charts, custom fields, zones, etc.) for an athlete from Intervals.icu

    Args:
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/custom-item", api_key=api_key
    )

    if isinstance(result, dict) and "error" in result:
        return f"Error fetching custom items: {result.get('message')}"

    if not result:
        return f"No custom items found for athlete {athlete_id_to_use}."

    if isinstance(result, list):
        _CUSTOM_ITEMS_CACHE[athlete_id_to_use] = [
            item for item in result if isinstance(item, dict)
        ]

    output = "Custom Items:\n\n"
    for item in result:
        if isinstance(item, dict):
            output += f"- ID: {item.get('id')}\n"
            output += f"  Name: {item.get('name', 'N/A')}\n"
            output += f"  Type: {item.get('type', 'N/A')}\n"
            if item.get("description"):
                output += f"  Description: {item['description']}\n"
            output += "\n"
    return output


@mcp.tool()
async def get_custom_item_by_id(
    item_id: int,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Get detailed information for a specific custom item from Intervals.icu

    Args:
        item_id: The custom item ID
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/custom-item/{item_id}", api_key=api_key
    )

    if isinstance(result, dict) and "error" in result:
        return f"Error fetching custom item: {result.get('message')}"

    if not result or not isinstance(result, dict):
        return f"No custom item found with ID {item_id}."

    return format_custom_item_details(result)


@mcp.tool()
async def create_custom_item(
    name: str,
    item_type: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
    description: str | None = None,
    content: dict[str, Any] | None = None,
    visibility: str | None = None,
) -> str:
    """Create a new custom item for an athlete on Intervals.icu

    Args:
        name: Name of the custom item
        item_type: Type of custom item (e.g. FITNESS_CHART, TRACE_CHART, INPUT_FIELD, ACTIVITY_FIELD, INTERVAL_FIELD, ACTIVITY_STREAM, ACTIVITY_CHART, ACTIVITY_HISTOGRAM, ACTIVITY_HEATMAP, ACTIVITY_MAP, ACTIVITY_PANEL, ZONES)
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
        description: Description of the custom item (optional)
        content: Configuration content for the custom item as a dict (optional). Important enum values:
            - "type" field for INPUT_FIELD/ACTIVITY_FIELD: must be "numeric", "text", or "select" (NOT "number")
            - "aggregate" field: must be "MIN", "SUM", "MAX", or "AVERAGE" (NOT "AVG")
        visibility: Visibility setting: PRIVATE, FOLLOWERS, or PUBLIC (optional)
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    data: dict[str, Any] = {"name": name, "type": item_type}
    if description is not None:
        data["description"] = description
    if content is not None:
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except json.JSONDecodeError:
                return "Error: content must be valid JSON when passed as a string."
        data["content"] = content
    if visibility is not None:
        data["visibility"] = visibility

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/custom-item",
        api_key=api_key,
        data=data,
        method="POST",
    )

    if isinstance(result, dict) and "error" in result:
        return f"Error creating custom item: {result.get('message')}"

    if not result or not isinstance(result, dict):
        return "Error: Unexpected response when creating custom item."

    invalidate_custom_items_cache(athlete_id_to_use)
    return f"Successfully created custom item:\n\n{format_custom_item_details(result)}"


@mcp.tool()
async def update_custom_item(
    item_id: int,
    athlete_id: str | None = None,
    api_key: str | None = None,
    name: str | None = None,
    item_type: str | None = None,
    description: str | None = None,
    content: dict[str, Any] | None = None,
    visibility: str | None = None,
) -> str:
    """Update an existing custom item for an athlete on Intervals.icu

    Args:
        item_id: The custom item ID to update
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
        name: New name for the custom item (optional)
        item_type: New type for the custom item (optional)
        description: New description for the custom item (optional)
        content: New configuration content for the custom item as a dict (optional). Important enum values:
            - "type" field for INPUT_FIELD/ACTIVITY_FIELD: must be "numeric", "text", or "select" (NOT "number")
            - "aggregate" field: must be "MIN", "SUM", "MAX", or "AVERAGE" (NOT "AVG")
        visibility: New visibility setting: PRIVATE, FOLLOWERS, or PUBLIC (optional)
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    data: dict[str, Any] = {}
    if name is not None:
        data["name"] = name
    if item_type is not None:
        data["type"] = item_type
    if description is not None:
        data["description"] = description
    if content is not None:
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except json.JSONDecodeError:
                return "Error: content must be valid JSON when passed as a string."
        data["content"] = content
    if visibility is not None:
        data["visibility"] = visibility

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/custom-item/{item_id}",
        api_key=api_key,
        data=data,
        method="PUT",
    )

    if isinstance(result, dict) and "error" in result:
        return f"Error updating custom item: {result.get('message')}"

    if not result or not isinstance(result, dict):
        return "Error: Unexpected response when updating custom item."

    invalidate_custom_items_cache(athlete_id_to_use)
    return f"Successfully updated custom item:\n\n{format_custom_item_details(result)}"


@mcp.tool()
async def delete_custom_item(
    item_id: int,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Delete a custom item for an athlete from Intervals.icu

    Args:
        item_id: The custom item ID to delete
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/custom-item/{item_id}",
        api_key=api_key,
        method="DELETE",
    )

    if isinstance(result, dict) and "error" in result:
        return f"Error deleting custom item: {result.get('message')}"

    invalidate_custom_items_cache(athlete_id_to_use)
    return f"Successfully deleted custom item {item_id}."
