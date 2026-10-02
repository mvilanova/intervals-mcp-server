"""Unit tests for the update_wellness tool."""

import asyncio

from intervals_mcp_server.tools.wellness import update_wellness


def _patch(monkeypatch, response, calls):
    async def fake_request(*args, **kwargs):
        calls.append((args, kwargs))
        return response

    monkeypatch.setattr("intervals_mcp_server.tools.wellness.make_intervals_request", fake_request)


def test_update_wellness_sends_only_passed_fields(monkeypatch):
    """Comment and injury are written; synced values are not part of the body."""
    calls: list = []
    _patch(
        monkeypatch,
        {
            "id": "2024-01-01",
            "injury": 2,
            "comments": "left knee niggle",
            "weight": 70.0,
            "hrv": 55,
        },
        calls,
    )
    result = asyncio.run(
        update_wellness(date="2024-01-01", injury=2, comments="left knee niggle", athlete_id="1")
    )
    assert len(calls) == 1
    kwargs = calls[0][1]
    assert kwargs["method"] == "PUT"
    assert kwargs["url"] == "/athlete/1/wellness/2024-01-01"
    assert kwargs["data"] == {"injury": 2, "comments": "left knee niggle"}
    assert result == (
        "Wellness updated:\n\n"
        "Wellness Data:\nDate: 2024-01-01\n\n"
        "Vital Signs:\n- Weight: 70.0 kg\n- HRV: 55\n\n"
        "Subjective Feelings:\n  Injury Level: 2 (Niggle)\n\n"
        "Comments: left knee niggle"
    )


def test_update_wellness_single_scale_field(monkeypatch):
    """A single scale value produces a single-key body."""
    calls: list = []
    _patch(monkeypatch, {"id": "2024-01-01", "soreness": 3}, calls)
    asyncio.run(update_wellness(date="2024-01-01", soreness=3, athlete_id="1"))
    assert calls[0][1]["data"] == {"soreness": 3}


def test_update_wellness_no_fields(monkeypatch):
    """No field passed returns an error and makes no request."""
    calls: list = []
    _patch(monkeypatch, {}, calls)
    result = asyncio.run(update_wellness(date="2024-01-01", athlete_id="1"))
    assert result.startswith("Error: No wellness fields provided")
    assert not calls


def test_update_wellness_invalid_date(monkeypatch):
    """Malformed dates are rejected before any request."""
    calls: list = []
    _patch(monkeypatch, {}, calls)
    result = asyncio.run(update_wellness(date="01-01-2024", mood=3, athlete_id="1"))
    assert "Invalid date format" in result
    assert not calls


def test_update_wellness_out_of_range(monkeypatch):
    """Scale values outside 1-4 are rejected before any request."""
    calls: list = []
    _patch(monkeypatch, {}, calls)
    for kwargs in ({"mood": 0}, {"stress": 5}, {"injury": -1}):
        result = asyncio.run(update_wellness(date="2024-01-01", athlete_id="1", **kwargs))
        assert "must be an integer between 1 and 4" in result
    assert not calls


def test_update_wellness_empty_comment_is_sent(monkeypatch):
    """An empty string comment is a deliberate value (clears the comment) and is sent."""
    calls: list = []
    _patch(monkeypatch, {"id": "2024-01-01", "comments": ""}, calls)
    asyncio.run(update_wellness(date="2024-01-01", comments="", athlete_id="1"))
    assert calls[0][1]["data"] == {"comments": ""}


def test_update_wellness_api_error(monkeypatch):
    """API errors are surfaced as an error string."""
    calls: list = []
    _patch(monkeypatch, {"error": True, "message": "boom"}, calls)
    result = asyncio.run(update_wellness(date="2024-01-01", mood=3, athlete_id="1"))
    assert result == "Error updating wellness data: boom"


def test_update_wellness_empty_response(monkeypatch):
    """An empty response is reported as an error."""
    calls: list = []
    _patch(monkeypatch, {}, calls)
    result = asyncio.run(update_wellness(date="2024-01-01", mood=3, athlete_id="1"))
    assert result.startswith("Error updating wellness data")


def test_update_wellness_missing_athlete(monkeypatch):
    """Without athlete id (param or env) an error is returned."""
    calls: list = []
    _patch(monkeypatch, {}, calls)
    monkeypatch.setattr("intervals_mcp_server.tools.wellness.config.athlete_id", "")
    result = asyncio.run(update_wellness(date="2024-01-01", mood=3))
    assert "No athlete ID" in result
    assert not calls
