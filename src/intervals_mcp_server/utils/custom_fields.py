"""
Custom item helpers for Intervals.icu MCP Server.

Athletes can define custom items on Intervals.icu (ACTIVITY_FIELD, INTERVAL_FIELD,
ACTIVITY_STREAM, INPUT_FIELD, ...). The API does not return their values in a
dedicated structure:

- custom activity fields are top-level keys of the activity JSON, named by the
  item's ``content.code``;
- custom interval fields are keys of each interval in ``icu_intervals``;
- custom streams are extra entries in the streams list whose ``type`` is the code;
- custom wellness fields (INPUT_FIELD) are keys of each wellness entry.

This module turns the custom item definitions (``/athlete/{id}/custom-item``) into
lookups keyed by code and renders values together with their technical code,
display name, units and, for select fields, the option label. Everything is
data-driven: whatever the athlete has defined is picked up, nothing is hard-coded
for a particular device or vendor.
"""

import json
import math
from typing import Any

ACTIVITY_FIELD = "ACTIVITY_FIELD"
ACTIVITY_STREAM = "ACTIVITY_STREAM"
INTERVAL_FIELD = "INTERVAL_FIELD"
INPUT_FIELD = "INPUT_FIELD"

# code -> normalized definition
CustomFieldDefs = dict[str, dict[str, Any]]
# item type -> definitions
CustomItemIndex = dict[str, CustomFieldDefs]


def normalize_custom_item(item: dict[str, Any]) -> dict[str, Any] | None:
    """Reduce a raw custom item to the attributes needed to render its values.

    Returns None for items without a ``content.code`` (charts, maps, panels ...).
    """
    content = item.get("content")
    if not isinstance(content, dict):
        return None
    code = content.get("code")
    if not code:
        return None
    options = content.get("options")
    units = content.get("units")
    return {
        "id": item.get("id"),
        "type": item.get("type"),
        "code": str(code),
        "name": item.get("name") or content.get("name") or str(code),
        "units": units.strip() if isinstance(units, str) and units.strip() else None,
        "value_type": content.get("type"),
        "options": options if isinstance(options, list) else None,
        "description": item.get("description") or content.get("short_description"),
        "fit_source": content.get("fit_session_field") or content.get("fit_record_field"),
        "has_script": bool(content.get("script")),
    }


def index_custom_items(items: Any) -> CustomItemIndex:
    """Group custom item definitions by item type and code.

    Accepts the raw ``/athlete/{id}/custom-item`` response. Anything that is not a
    list of items with a code is ignored, so an error payload yields an empty index.
    """
    index: CustomItemIndex = {}
    if not isinstance(items, list):
        return index
    for item in items:
        if not isinstance(item, dict):
            continue
        normalized = normalize_custom_item(item)
        if normalized is None:
            continue
        by_code = index.setdefault(str(normalized["type"]), {})
        by_code.setdefault(normalized["code"], normalized)
    return index


def is_missing(value: Any) -> bool:
    """True for null and NaN, which Intervals.icu uses for 'no value'.

    The API serialises NaN either as a bare token (parsed to float nan) or as the
    string "NaN"; both mean that no value is stored.
    """
    if value is None:
        return True
    if isinstance(value, float):
        return math.isnan(value)
    return isinstance(value, str) and value.strip().lower() == "nan"


def format_value(value: Any) -> str:
    """Render a scalar as stored (only float noise beyond 6 decimals is trimmed)."""
    if is_missing(value):
        return "no value"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        rounded = round(value, 6)
        return str(int(rounded)) if rounded.is_integer() else str(rounded)
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _same_number(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return False
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        if math.isnan(left) or math.isnan(right):
            return False
        return float(left) == float(right)
    return False


def select_label(definition: dict[str, Any], value: Any) -> str | None:
    """Resolve the option text of a select field for the stored value."""
    for option in definition.get("options") or []:
        if not isinstance(option, dict):
            continue
        option_value = option.get("value")
        if option_value == value or _same_number(option_value, value):
            text = option.get("text")
            return str(text) if text is not None else None
    return None


def _is_zero(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value == 0


def format_field_value(definition: dict[str, Any], value: Any) -> str:
    """Render a custom field value with its units, select label and a 'possibly missing' marker.

    Intervals.icu stores 0 for a field that is filled from the device file when the
    source field is absent from the file. Such a 0 cannot be told apart from a real
    measurement, so it is reported as stored but marked.
    """
    text = format_value(value)
    if is_missing(value):
        return text
    units = definition.get("units")
    if units:
        text = f"{text} {units}"
    label = select_label(definition, value)
    if label:
        text = f"{text} ({label})"
    if _is_zero(value) and (definition.get("fit_source") or definition.get("has_script")):
        text = f"{text} (0: may be absent in source file)"
    return text


def format_custom_field_lines(
    payload: dict[str, Any], defs: CustomFieldDefs, prefix: str = "- "
) -> list[str]:
    """One line per custom field present on the payload, in definition order."""
    lines: list[str] = []
    for code, definition in defs.items():
        if code not in payload:
            continue
        rendered = format_field_value(definition, payload[code])
        lines.append(f"{prefix}{definition['name']} [{code}]: {rendered}")
    return lines


def format_custom_activity_fields(activity: dict[str, Any], defs: CustomFieldDefs) -> str:
    """Render the 'Custom Activity Fields' section of an activity."""
    lines = ["Custom Activity Fields:"]
    if not defs:
        lines.append("- (no custom activity field definitions found for this athlete)")
        return "\n".join(lines)

    field_lines = format_custom_field_lines(activity, defs)
    if not field_lines:
        lines.append(
            f"- (none of the {len(defs)} defined custom activity fields is present on this activity)"
        )
        return "\n".join(lines)

    lines.extend(field_lines)
    absent = sorted(code for code in defs if code not in activity)
    if absent:
        lines.append(f"Defined but not present on this activity: {', '.join(absent)}")
    lines.append(
        "Note: 'no value' = null/NaN in Intervals.icu. Values are reported exactly as stored; "
        "for fields filled from the device file Intervals.icu stores 0 when the source field "
        "is absent, so a 0 marked 'may be absent' is not necessarily a measurement."
    )
    return "\n".join(lines)
