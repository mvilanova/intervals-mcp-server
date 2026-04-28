"""
Unit tests for the Value dataclass in intervals_mcp_server.utils.types.

These tests verify that the Value dataclass correctly handles:
- String formatting for percent FTP units
- Ramp intervals (start/end values)
- Deserialisation of pace/swim-pace unit strings returned by the Intervals.icu API
"""

import pytest

from intervals_mcp_server.utils.types import Value, ValueUnits


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
