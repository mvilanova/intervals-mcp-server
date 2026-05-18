"""
Custom items MCP tools for Intervals.icu.

This module contains tools for managing athlete custom items (charts, fields, zones, etc.).
"""

import json
from typing import Any

from intervals_mcp_server.api.client import make_intervals_request
from intervals_mcp_server.utils.formatting import format_custom_item_details
from intervals_mcp_server.tools.common import format_tool_error, is_error_result, resolve_tool_context

# Import mcp instance from shared module for tool registration
from intervals_mcp_server.mcp_instance import mcp  # noqa: F401


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
    athlete_id_to_use, api_key, error_msg = resolve_tool_context(athlete_id, api_key)
    if error_msg:
        return error_msg

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/custom-item", api_key=api_key
    )

    if is_error_result(result):
        return format_tool_error("fetching custom items", result)

    if not result:
        return f"No custom items found for athlete {athlete_id_to_use}."

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
    athlete_id_to_use, api_key, error_msg = resolve_tool_context(athlete_id, api_key)
    if error_msg:
        return error_msg

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/custom-item/{item_id}", api_key=api_key
    )

    if is_error_result(result):
        return format_tool_error("fetching custom item", result)

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
    athlete_id_to_use, api_key, error_msg = resolve_tool_context(athlete_id, api_key)
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

    if is_error_result(result):
        return format_tool_error("creating custom item", result)

    if not result or not isinstance(result, dict):
        return "Error: Unexpected response when creating custom item."

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
    athlete_id_to_use, api_key, error_msg = resolve_tool_context(athlete_id, api_key)
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

    if is_error_result(result):
        return format_tool_error("updating custom item", result)

    if not result or not isinstance(result, dict):
        return "Error: Unexpected response when updating custom item."

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
    athlete_id_to_use, api_key, error_msg = resolve_tool_context(athlete_id, api_key)
    if error_msg:
        return error_msg

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/custom-item/{item_id}",
        api_key=api_key,
        method="DELETE",
    )

    if is_error_result(result):
        return format_tool_error("deleting custom item", result)

    return f"Successfully deleted custom item {item_id}."
