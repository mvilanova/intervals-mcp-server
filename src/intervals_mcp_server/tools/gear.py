"""
Gear-related MCP tools for Intervals.icu.

This module provides:
- A module-level cache of the athlete's gear list (bikes, shoes, etc.) to avoid
  hitting the /athlete/{id}/gear endpoint on every activity lookup.
- A helper to inject the human-readable gear name into an activity dict (under
  `_resolved_gear_name`), which the formatter then displays in the `Gear:` block.
- A user-facing MCP tool `get_gear_list` so the assistant can discover or
  refresh the gear catalog on demand.

Intervals.icu's activity payload includes only the gear ID (e.g. `b16177481`)
but not the gear name. The gear name lives in a separate endpoint
`/athlete/{athlete_id}/gear` that returns the full catalog. To avoid an extra
round-trip per activity, we cache the gear catalog per athlete for the lifetime
of the MCP server process. Call `get_gear_list` again to bust the cache.
"""

from typing import Any

from intervals_mcp_server.api.client import make_intervals_request
from intervals_mcp_server.config import get_config
from intervals_mcp_server.utils.validation import resolve_athlete_id

# Import mcp instance from shared module for tool registration
from intervals_mcp_server.mcp_instance import mcp  # noqa: F401

config = get_config()

# Module-level cache: {athlete_id: {gear_id: gear_name}}.
# Keyed by athlete_id so the same MCP process can serve multiple athletes,
# although the typical case is a single athlete via ATHLETE_ID env var.
_GEAR_CACHE: dict[str, dict[str, str]] = {}


def _extract_gear_id(activity: dict[str, Any]) -> str | None:
    """Pull the gear ID out of an activity dict, handling the two known shapes."""
    gear_raw = activity.get("gear")
    if isinstance(gear_raw, dict):
        gear_id = gear_raw.get("id")
        if gear_id:
            return str(gear_id)
    gear_id = activity.get("gear_id")
    if gear_id:
        return str(gear_id)
    return None


async def _fetch_gear_map(
    athlete_id: str,
    api_key: str | None = None,
) -> dict[str, str]:
    """Fetch the athlete's gear catalog from Intervals.icu and return {id: name}."""
    result = await make_intervals_request(
        url=f"/athlete/{athlete_id}/gear", api_key=api_key
    )
    gear_map: dict[str, str] = {}

    items: list[Any] = []
    if isinstance(result, list):
        items = result
    elif isinstance(result, dict):
        # Some endpoints wrap the list in a container; pull any list value.
        for value in result.values():
            if isinstance(value, list):
                items = value
                break

    for item in items:
        if not isinstance(item, dict):
            continue
        gid = item.get("id")
        name = item.get("name") or item.get("display_name")
        if gid and name:
            gear_map[str(gid)] = str(name)

    return gear_map


async def get_gear_map(
    athlete_id: str | None = None,
    api_key: str | None = None,
    *,
    refresh: bool = False,
) -> dict[str, str]:
    """Return (and cache) the gear map {gear_id: gear_name} for an athlete.

    Args:
        athlete_id: Athlete to look up. Defaults to ATHLETE_ID env var via config.
        api_key: Override the configured API key.
        refresh: If True, ignore the cache and re-fetch from the API.
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg or not athlete_id_to_use:
        return {}

    if not refresh and athlete_id_to_use in _GEAR_CACHE:
        return _GEAR_CACHE[athlete_id_to_use]

    gear_map = await _fetch_gear_map(athlete_id_to_use, api_key=api_key)
    _GEAR_CACHE[athlete_id_to_use] = gear_map
    return gear_map


async def resolve_gear_for_activity(
    activity: dict[str, Any],
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> None:
    """Inject `_resolved_gear_name` into an activity dict if gear info is present.

    Mutates the activity dict in place. Safe to call when gear is absent (no-op).
    Uses the cached gear map; the first call per athlete triggers a fetch.
    """
    gear_id = _extract_gear_id(activity)
    if not gear_id:
        return

    gear_map = await get_gear_map(athlete_id=athlete_id, api_key=api_key)
    name = gear_map.get(gear_id)
    if name:
        activity["_resolved_gear_name"] = name


async def resolve_gear_for_activities(
    activities: list[dict[str, Any]],
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> None:
    """Inject `_resolved_gear_name` into each activity in a list. In-place."""
    if not activities:
        return
    # Pre-warm the cache once, then iterate.
    _ = await get_gear_map(athlete_id=athlete_id, api_key=api_key)
    for activity in activities:
        if isinstance(activity, dict):
            await resolve_gear_for_activity(
                activity, athlete_id=athlete_id, api_key=api_key
            )


@mcp.tool()
async def get_gear_list(
    athlete_id: str | None = None,
    api_key: str | None = None,
    refresh: bool = False,
) -> str:
    """Get the gear catalog (bikes, shoes, etc.) for an athlete from Intervals.icu.

    Returns one line per gear item with id, type, name, and basic stats.
    The result is cached for the MCP process lifetime; pass refresh=True to
    re-fetch.

    Args:
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
        refresh: If True, bypass the cache and re-fetch from the API (default False)
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if not athlete_id_to_use:
        return "Error: athlete_id is required (either as argument or via ATHLETE_ID env var)."

    # Fetch + cache via the helper.
    gear_map = await get_gear_map(
        athlete_id=athlete_id_to_use, api_key=api_key, refresh=refresh
    )

    if not gear_map:
        return f"No gear found for athlete {athlete_id_to_use}."

    # For the rich listing, refetch the raw list once so we can include type
    # and stats. (The cached map only stores id→name.)
    raw = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/gear", api_key=api_key
    )

    items: list[dict[str, Any]] = []
    if isinstance(raw, list):
        items = [it for it in raw if isinstance(it, dict)]
    elif isinstance(raw, dict):
        for value in raw.values():
            if isinstance(value, list):
                items = [it for it in value if isinstance(it, dict)]
                break

    output = f"Gear catalog for athlete {athlete_id_to_use}:\n\n"
    output += f"{'ID':<14} {'Type':<8} {'Name':<32} {'Default':<8} {'Acts':<6} {'Dist (km)':<10} {'Retired':<8}\n"
    output += f"{'-' * 14} {'-' * 8} {'-' * 32} {'-' * 8} {'-' * 6} {'-' * 10} {'-' * 8}\n"
    for it in items:
        gid = str(it.get("id", "?"))
        gtype = str(it.get("component_type", it.get("type", "?")))
        name = str(it.get("name", "?"))[:32]
        default_for = it.get("default_for_type") or it.get("default_for") or ""
        acts = str(it.get("activities", it.get("activity_count", "?")))
        dist_m = it.get("distance", 0) or 0
        dist_km = f"{dist_m / 1000:.1f}" if isinstance(dist_m, (int, float)) else "?"
        retired = "yes" if it.get("retired") else ""
        output += f"{gid:<14} {gtype:<8} {name:<32} {str(default_for):<8} {acts:<6} {dist_km:<10} {retired:<8}\n"

    return output
