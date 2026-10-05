"""
Unit tests for the make_intervals_request function in intervals_mcp_server.server.

These tests focus on error handling, particularly the scenario where the API returns invalid JSON.
Mock classes are used to simulate httpx responses and client behavior.
"""

import asyncio
import logging
import os
import pathlib
import sys
from json import JSONDecodeError

import httpx

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("API_KEY", "test")
os.environ.setdefault("ATHLETE_ID", "i1")

from intervals_mcp_server import server  # pylint: disable=wrong-import-position
from intervals_mcp_server.api import client as api_client  # pylint: disable=wrong-import-position
from intervals_mcp_server.config import Config  # pylint: disable=wrong-import-position


class MockBadJSONResponse:
    """
    Simulates an httpx response object that returns invalid JSON content.
    Used to test error handling for JSONDecodeError in make_intervals_request.
    """

    def __init__(self):
        self.content = b"bad"
        self.status_code = 200

    def raise_for_status(self):
        """Mock raise_for_status that does nothing."""
        return None

    def json(self):
        """Raise JSONDecodeError to simulate invalid JSON."""
        raise JSONDecodeError("Expecting value", "bad", 0)


class MockAsyncClient:
    """
    Simulates an httpx.AsyncClient for use in monkeypatching.
    Always returns a MockBadJSONResponse from get().
    """

    def __init__(self, *_args, **_kwargs):
        # Accept any arguments to match httpx.AsyncClient's interface
        self.is_closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass

    async def get(self, _url, **_kwargs):
        """Mock get method that returns MockBadJSONResponse."""
        return MockBadJSONResponse()

    async def request(self, *_args, **_kwargs):
        """Mock request method that returns MockBadJSONResponse."""
        return MockBadJSONResponse()

    async def aclose(self):
        """Simulate closing the AsyncClient."""
        self.is_closed = True


def test_make_intervals_request_bad_json(monkeypatch, caplog):
    """
    Test that make_intervals_request returns an error dict when the response contains invalid JSON.
    Ensures proper logging and error message content.
    """
    monkeypatch.setenv("API_KEY", "test")
    monkeypatch.setenv("ATHLETE_ID", "i1")
    # Reset the singleton so config picks up the monkeypatched env vars
    monkeypatch.setattr("intervals_mcp_server.config._config_instance", None)
    monkeypatch.setattr(server, "httpx_client", MockAsyncClient())
    monkeypatch.setattr(
        api_client,
        "get_config",
        lambda: Config(
            api_key="test",
            athlete_id="i1",
            intervals_api_base_url="https://intervals.icu/api/v1",
            user_agent="test-agent",
        ),
    )

    # Ensure the config singleton has an API key, regardless of test execution order
    from intervals_mcp_server.config import get_config  # pylint: disable=import-outside-toplevel
    monkeypatch.setattr(get_config(), "api_key", "test")

    with caplog.at_level(logging.ERROR):
        result = asyncio.run(server.make_intervals_request("/bad"))

    assert result["error"] is True
    assert "Invalid JSON in response" in result["message"]


def test_athlete_id_is_redacted_in_logged_urls():
    """
    Test that logged URLs never contain the athlete ID and httpx request logging is silenced.
    """
    redact = api_client._redact  # pylint: disable=protected-access
    assert redact("/athlete/i12345/activities") == "/athlete/***/activities"
    assert redact("https://intervals.icu/api/v1/athlete/i12345?x=1") == "https://intervals.icu/api/v1/athlete/***?x=1"
    assert redact("/activity/i999/intervals") == "/activity/i999/intervals"
    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING


def test_http_error_body_is_redacted_in_logs(caplog):
    """
    Test that an error response echoing the request path does not leak the athlete ID into logs.
    """
    request = httpx.Request("GET", "https://intervals.icu/api/v1/athlete/i12345/events/1")
    response = httpx.Response(404, text='{"path":"/api/v1/athlete/i12345/events/1"}', request=request)
    error = httpx.HTTPStatusError("not found", request=request, response=response)
    with caplog.at_level(logging.ERROR):
        result = api_client._handle_http_status_error(error)  # pylint: disable=protected-access
    assert result["status_code"] == 404
    assert "i12345" not in caplog.text
    assert "/athlete/***/events/1" in caplog.text
