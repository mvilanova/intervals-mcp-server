"""Shared helpers for MCP tool implementations."""

from typing import Any, TypeGuard

from intervals_mcp_server.config import get_config
from intervals_mcp_server.models import IntervalsError
from intervals_mcp_server.utils.validation import resolve_athlete_id


def resolve_tool_context(
    athlete_id: str | None,
    api_key: str | None,
) -> tuple[str, str | None, str | None]:
    """Resolve athlete ID from parameter or env config; propagate api_key.

    Returns (athlete_id_to_use, api_key, error_msg). error_msg is None on success.
    """
    config = get_config()
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    return athlete_id_to_use, api_key, error_msg


def is_error_result(result: Any) -> TypeGuard[dict[str, Any]]:
    """Return True when result is an error response dict from make_intervals_request."""
    return isinstance(result, dict) and "error" in result


def format_tool_error(action: str, result: dict[str, Any]) -> str:
    """Format an API error dict as a human-readable tool response.

    Produces "Error <action>: <message>" with an "Unknown error" fallback.
    """
    error_message = result.get("message", "Unknown error")
    return f"Error {action}: {error_message}"


def parse_error_result(result: dict[str, Any]) -> IntervalsError:
    """Convert a make_intervals_request error dict into a typed IntervalsError.

    Callers that need structured access to error fields (e.g. status_code)
    can use this instead of probing the raw dict directly.
    """
    return IntervalsError.from_dict(result)
