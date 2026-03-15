"""
Unit tests for resolve_activity_type in intervals_mcp_server.utils.validation.
"""

from intervals_mcp_server.utils.validation import resolve_activity_type


def test_explicit_activity_type_returned_as_is():
    """Explicit activity_type is returned unchanged."""
    assert resolve_activity_type(None, "VirtualRide") == "VirtualRide"
    assert resolve_activity_type("morning swim", "Run") == "Run"


def test_keyword_ride():
    """Cycling keywords resolve to Ride."""
    for name in ["Morning Ride", "cycling session", "bike workout", "cycle"]:
        assert resolve_activity_type(name) == "Ride"


def test_keyword_run():
    """Running keywords resolve to Run."""
    for name in ["Easy Run", "jogging", "morning jog", "running"]:
        assert resolve_activity_type(name) == "Run"


def test_keyword_swim():
    """Swimming keywords resolve to Swim."""
    for name in ["Pool Swim", "swimming drills", "swim"]:
        assert resolve_activity_type(name) == "Swim"


def test_keyword_walk():
    """Walking keywords resolve to Walk."""
    for name in ["Evening Walk", "hiking trip", "hike", "walking"]:
        assert resolve_activity_type(name) == "Walk"


def test_keyword_row():
    """Rowing keywords resolve to Row."""
    for name in ["Rowing session", "morning row"]:
        assert resolve_activity_type(name) == "Row"


def test_default_ride_when_no_match():
    """Defaults to Ride when no keyword matches."""
    assert resolve_activity_type("stretching") == "Ride"
    assert resolve_activity_type(None) == "Ride"
    assert resolve_activity_type("") == "Ride"


def test_case_insensitive():
    """Keyword matching is case-insensitive."""
    assert resolve_activity_type("MORNING RUN") == "Run"
    assert resolve_activity_type("SWIM") == "Swim"
