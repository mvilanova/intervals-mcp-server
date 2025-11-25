"""
Unit tests for the Value dataclass in intervals_mcp_server.utils.types.

These tests verify that the Value dataclass correctly handles:
- String formatting for percent FTP units
- Ramp intervals (start/end values)
"""

from intervals_mcp_server.utils.types import Value, ValueUnits


def test_str_percent_ftp():
    """Test formatting percentage FTP values."""
    val = Value(value=95.0, units=ValueUnits.PERCENT_FTP)
    assert str(val) == "95% ftp"


def test_str_ramp_percent_ftp():
    """Test formatting ramp intervals with percentage FTP."""
    val = Value(start=65, end=85, units=ValueUnits.PERCENT_FTP)
    assert str(val) == "65%-85% ftp"
