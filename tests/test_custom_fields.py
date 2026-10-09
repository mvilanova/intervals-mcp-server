"""
Unit tests for intervals_mcp_server.utils.custom_fields.

These cover the indexing of custom item definitions and the rendering of custom
field values (units, select labels, null/NaN handling, the 'possibly missing' marker).
"""

import math

from intervals_mcp_server.utils.custom_fields import (
    ACTIVITY_FIELD,
    ACTIVITY_STREAM,
    INPUT_FIELD,
    INTERVAL_FIELD,
    format_custom_activity_fields,
    format_custom_field_lines,
    format_field_value,
    format_value,
    index_custom_items,
    is_missing,
    select_label,
)
from tests.sample_data import ACTIVITY_WITH_CUSTOM_FIELDS, CUSTOM_ITEMS_DATA


def test_index_custom_items_groups_by_type_and_code():
    """
    Definitions are grouped by item type and keyed by their content.code; items
    without a code (charts) are ignored.
    """
    index = index_custom_items(CUSTOM_ITEMS_DATA)
    assert set(index) == {ACTIVITY_FIELD, INTERVAL_FIELD, ACTIVITY_STREAM, INPUT_FIELD}
    assert set(index[ACTIVITY_FIELD]) == {
        "AerobicEffect", "EPOC", "TrainingEffectSelect", "FlightTime", "Sweatloss"
    }
    epoc = index[ACTIVITY_FIELD]["EPOC"]
    assert epoc["name"] == "EPOC"
    assert epoc["units"] == "ml/kg"
    assert epoc["fit_source"] == "178"
    stamina = index[ACTIVITY_STREAM]["Stamina"]
    assert stamina["name"] == "Garmin Stamina"
    assert stamina["description"] == "Stamina"
    assert stamina["has_script"] is True


def test_index_custom_items_ignores_invalid_payloads():
    """
    Error payloads, non-dict entries and items without content yield no definitions.
    """
    assert not index_custom_items({"error": True})
    assert not index_custom_items(None)
    assert not index_custom_items([1, "x", {"id": 1, "type": "ACTIVITY_FIELD"}])


def test_is_missing_and_format_value():
    """
    null and NaN are 'no value'; numbers keep their stored precision (6 decimals max).
    """
    assert is_missing(None)
    assert is_missing(float("nan"))
    assert is_missing("NaN")  # the API serialises NaN as a string
    assert not is_missing(0)
    assert not is_missing("nano")
    assert format_value(None) == "no value"
    assert format_value(math.nan) == "no value"
    assert format_value("NaN") == "no value"
    assert format_value(100.0) == "100"
    assert format_value(3.5) == "3.5"
    assert format_value(129.58348) == "129.58348"
    assert format_value(1.3794444444444445) == "1.379444"
    assert format_value(True) == "true"
    assert format_value("text") == "text"
    assert format_value([1, 2]) == "[1, 2]"


def test_select_label_matches_numeric_values():
    """
    Select fields resolve the option text for the stored value, tolerating int/float.
    """
    definition = index_custom_items(CUSTOM_ITEMS_DATA)[ACTIVITY_FIELD]["TrainingEffectSelect"]
    assert select_label(definition, 2.0) == "Base"
    assert select_label(definition, 2) == "Base"
    assert select_label(definition, 9) is None
    assert select_label({"options": None}, 1) is None


def test_format_field_value_units_label_and_zero_marker():
    """
    Units and select labels are appended; a 0 in a field read from the device file is marked.
    """
    defs = index_custom_items(CUSTOM_ITEMS_DATA)[ACTIVITY_FIELD]
    assert format_field_value(defs["EPOC"], 129.58348) == "129.58348 ml/kg"
    assert format_field_value(defs["TrainingEffectSelect"], 2.0) == "2 (Base)"
    assert format_field_value(defs["FlightTime"], float("nan")) == "no value"
    assert format_field_value(defs["Sweatloss"], 0.0) == "0 ml (0: may be absent in source file)"
    # A 0 in a field that is not filled from the device file is not marked.
    assert format_field_value(defs["FlightTime"], 0) == "0"


def test_format_custom_field_lines_only_present_fields():
    """
    Only fields present on the payload are listed, in definition order, with the prefix.
    """
    defs = index_custom_items(CUSTOM_ITEMS_DATA)[ACTIVITY_FIELD]
    lines = format_custom_field_lines({"EPOC": 1.5, "unrelated": 1}, defs, prefix="  ")
    assert lines == ["  EPOC [EPOC]: 1.5 ml/kg"]


def test_format_custom_activity_fields_section():
    """
    The section lists present fields, names the absent definitions and explains the markers.
    """
    defs = index_custom_items(CUSTOM_ITEMS_DATA)[ACTIVITY_FIELD]
    text = format_custom_activity_fields(ACTIVITY_WITH_CUSTOM_FIELDS, defs)
    assert text.startswith("Custom Activity Fields:")
    assert "- Aerobic Effect [AerobicEffect]: 3.5" in text
    assert "- EPOC [EPOC]: 129.58348 ml/kg" in text
    assert "- Training Effect [TrainingEffectSelect]: 2 (Base)" in text
    assert "- Flight Time [FlightTime]: no value" in text
    assert "- Sweat loss [Sweatloss]: 0 ml (0: may be absent in source file)" in text
    assert "Defined but not present" not in text
    assert "Note:" in text


def test_format_custom_activity_fields_absent_and_empty():
    """
    Absent definitions are reported, and missing definitions give an explanatory line.
    """
    defs = index_custom_items(CUSTOM_ITEMS_DATA)[ACTIVITY_FIELD]
    text = format_custom_activity_fields({"EPOC": 2}, defs)
    assert "Defined but not present on this activity: AerobicEffect, FlightTime, Sweatloss, TrainingEffectSelect" in text
    assert "none of the 5 defined" in format_custom_activity_fields({"x": 1}, defs)
    assert "no custom activity field definitions" in format_custom_activity_fields({"x": 1}, {})
