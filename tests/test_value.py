"""
Unit tests for the Value dataclass in intervals_mcp_server.utils.types.

These tests verify that the Value dataclass correctly handles:
- String formatting for percent FTP units
- Ramp intervals (start/end values)
- Deserialisation of pace/swim-pace unit strings returned by the Intervals.icu API
"""

import pytest

from intervals_mcp_server.utils.types import Step, Value, ValueUnits


def test_str_percent_ftp():
    """Test formatting percentage FTP values."""
    val = Value(value=95.0, units=ValueUnits.PERCENT_FTP)
    assert str(val) == "95% ftp"


def test_str_ramp_percent_ftp():
    """Test formatting ramp intervals with percentage FTP."""
    val = Value(start=65, end=85, units=ValueUnits.PERCENT_FTP)
    assert str(val) == "65%-85% ftp"


@pytest.mark.parametrize("unit_str,expected_enum", [
    ("MINS_KM", ValueUnits.MINS_KM),
    ("MINS_MILE", ValueUnits.MINS_MILE),
    ("SECS_100M", ValueUnits.SECS_100M),
    ("SECS_500M", ValueUnits.SECS_500M),
])
def test_pace_units_deserialise_from_api_string(unit_str, expected_enum):
    """Pace/swim-pace unit strings returned by the Intervals.icu API must round-trip
    through Value.from_dict without raising ValueError.  This test would fail if any
    of these unit strings were missing from the ValueUnits enum."""
    val = Value.from_dict({"value": 5.0, "units": unit_str})
    assert val.units == expected_enum


@pytest.mark.parametrize("val,expected", [
    (Value(value=335, units=ValueUnits.MINS_KM), "5:35/km Pace"),
    (Value(value=5.5833, units=ValueUnits.MINS_KM), "5:35/km Pace"),
    (Value(value=240, units=ValueUnits.MINS_KM), "4:00/km Pace"),
    (Value(value=4.0, units=ValueUnits.MINS_KM), "4:00/km Pace"),
    (Value(value=540, units=ValueUnits.MINS_MILE), "9:00/mi Pace"),
    (Value(value=105, units=ValueUnits.SECS_100M), "1:45/100m Pace"),
    (Value(value=120, units=ValueUnits.SECS_500M), "2:00/500m Pace"),
    (Value(start=330, end=340, units=ValueUnits.MINS_KM), "5:30-5:40/km Pace"),
    (Value(start=5.5, end=5.6667, units=ValueUnits.MINS_KM), "5:30-5:40/km Pace"),
    (Value(start=100, end=110, units=ValueUnits.SECS_100M), "1:40-1:50/100m Pace"),
])
def test_str_absolute_pace(val, expected):
    """Absolute paces use the Intervals.icu syntax "m:ss/<unit> Pace"; seconds and
    decimal minutes both work, and ranges carry the suffix only once."""
    assert str(val) == expected


def test_step_str_absolute_pace():
    """A step with an absolute pace must produce a description Intervals.icu parses as pace."""
    step = Step.from_dict({"duration": 2700, "pace": {"value": 335, "units": "MINS_KM"}, "text": "locker"})
    assert str(step).strip() == "- 45m 5:35/km Pace locker"
