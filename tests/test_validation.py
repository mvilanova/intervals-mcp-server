"""
Unit tests for resolve_activity_type in intervals_mcp_server.utils.validation.
"""

from intervals_mcp_server.utils.validation import resolve_activity_type, resolve_athlete_id


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


def test_resolve_athlete_id_defaults_when_missing_or_blank():
    """None, empty and blank IDs fall back to the default athlete."""
    for athlete_id in (None, "", "   "):
        assert resolve_athlete_id(athlete_id, "i1") == ("i1", None)


def test_resolve_athlete_id_uses_given_id():
    """A given ID wins over the default and is stripped."""
    assert resolve_athlete_id("i2", "i1") == ("i2", None)
    assert resolve_athlete_id(" 12345 ", "i1") == ("12345", None)


def test_resolve_athlete_id_rejects_invalid_format():
    """IDs that could change the URL path are rejected."""
    for athlete_id in ("i2/events", "../1", "abc", "i 2"):
        athlete_id_to_use, error = resolve_athlete_id(athlete_id, "i1")
        assert athlete_id_to_use == ""
        assert error is not None and error.startswith("Error: athlete_id must be all digits")


def test_resolve_athlete_id_without_default():
    """Without ID and default an error is returned."""
    assert resolve_athlete_id(None) == (
        "",
        "Error: No athlete ID provided and no default ATHLETE_ID found in environment variables.",
    )
