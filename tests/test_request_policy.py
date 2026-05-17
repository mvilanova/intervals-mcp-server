"""Tests for the request retry/rate-limit policy in make_intervals_request.

Covers:
- 429 with Retry-After header
- 429 without Retry-After (exponential backoff)
- 500 retry then success
- Permanent 401/404 - no retry
- Network error retry then success
- Exhausted retries returns error
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest

from intervals_mcp_server.api.client import _BASE_DELAY_SECS, MAX_RETRIES, make_intervals_request
from intervals_mcp_server.config import Config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class MockResponse:
    """Minimal httpx.Response stand-in for retry policy tests."""

    def __init__(
        self,
        status_code: int,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self._data = data or {}
        self.headers = headers or {}
        self.content = b"body"
        self.text = f"HTTP {status_code}"

    def json(self) -> dict[str, Any]:
        return self._data

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            req = httpx.Request("GET", "https://intervals.icu/api/v1/test")
            raise httpx.HTTPStatusError(
                message=f"HTTP error {self.status_code}",
                request=req,
                response=self,  # type: ignore[arg-type]
            )


class MockSequentialClient:
    """Async httpx client that returns pre-set responses in order.

    An entry in `responses` may be an Exception subclass *instance*; in that
    case the mock raises it instead of returning a response.
    """

    def __init__(self, responses: list[Any]) -> None:
        self._responses = responses
        self._idx = 0
        self.is_closed = False
        self.call_count = 0

    async def request(self, *_args: Any, **_kwargs: Any) -> MockResponse:
        resp = self._responses[self._idx]
        self._idx += 1
        self.call_count += 1
        if isinstance(resp, BaseException):
            raise resp
        return resp  # type: ignore[return-value]

    async def aclose(self) -> None:
        self.is_closed = True


def _fake_get_config() -> Config:
    return Config(
        api_key="test-key",
        athlete_id="i1",
        intervals_api_base_url="https://intervals.icu/api/v1",
        user_agent="test-agent",
    )


def _patch_client(
    monkeypatch: pytest.MonkeyPatch,
    mock_client: MockSequentialClient,
    sleep_calls: list[float],
) -> None:
    """Wire up the mock client and a non-sleeping sleep stub."""

    async def fake_get_client() -> MockSequentialClient:
        return mock_client

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr("intervals_mcp_server.api.client._get_httpx_client", fake_get_client)
    monkeypatch.setattr("asyncio.sleep", fake_sleep)
    monkeypatch.setattr("intervals_mcp_server.api.client.get_config", _fake_get_config)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_429_with_retry_after_uses_header_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    """429 with Retry-After header sleeps for that many seconds then succeeds."""
    sleep_calls: list[float] = []
    client = MockSequentialClient(
        [
            MockResponse(429, headers={"Retry-After": "7"}),
            MockResponse(200, data={"athlete": "ok"}),
        ]
    )
    _patch_client(monkeypatch, client, sleep_calls)

    result = asyncio.run(make_intervals_request("/athlete/i1"))

    assert result == {"athlete": "ok"}
    assert client.call_count == 2
    assert len(sleep_calls) == 1
    assert sleep_calls[0] == 7.0


def test_429_without_retry_after_uses_exponential_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    """429 without Retry-After falls back to exponential backoff (BASE * 2^attempt)."""
    sleep_calls: list[float] = []
    client = MockSequentialClient(
        [
            MockResponse(429),
            MockResponse(200, data={"ok": True}),
        ]
    )
    _patch_client(monkeypatch, client, sleep_calls)

    result = asyncio.run(make_intervals_request("/athlete/i1"))

    assert result == {"ok": True}
    assert len(sleep_calls) == 1
    assert sleep_calls[0] == _BASE_DELAY_SECS * (2**0)  # attempt 0 → 1.0s


def test_500_retries_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    """5xx responses trigger retry; success on a later attempt is returned."""
    sleep_calls: list[float] = []
    client = MockSequentialClient(
        [
            MockResponse(500),
            MockResponse(200, data={"result": "good"}),
        ]
    )
    _patch_client(monkeypatch, client, sleep_calls)

    result = asyncio.run(make_intervals_request("/athlete/i1"))

    assert result == {"result": "good"}
    assert client.call_count == 2
    assert len(sleep_calls) == 1


def test_401_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    """401 Unauthorized is a permanent error and must never be retried."""
    sleep_calls: list[float] = []
    client = MockSequentialClient([MockResponse(401)])
    _patch_client(monkeypatch, client, sleep_calls)

    result = asyncio.run(make_intervals_request("/athlete/i1"))

    assert result.get("error") is True  # type: ignore[union-attr]
    assert result.get("status_code") == 401  # type: ignore[union-attr]
    assert client.call_count == 1
    assert sleep_calls == []


def test_404_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    """404 Not Found is a permanent error and must never be retried."""
    sleep_calls: list[float] = []
    client = MockSequentialClient([MockResponse(404)])
    _patch_client(monkeypatch, client, sleep_calls)

    result = asyncio.run(make_intervals_request("/athlete/i1/missing"))

    assert result.get("error") is True  # type: ignore[union-attr]
    assert result.get("status_code") == 404  # type: ignore[union-attr]
    assert client.call_count == 1
    assert sleep_calls == []


def test_network_error_retries_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    """Transient network errors trigger retry; success on next attempt is returned."""
    sleep_calls: list[float] = []
    client = MockSequentialClient(
        [
            httpx.ConnectError("connection refused"),
            MockResponse(200, data={"connected": True}),
        ]
    )
    _patch_client(monkeypatch, client, sleep_calls)

    result = asyncio.run(make_intervals_request("/athlete/i1"))

    assert result == {"connected": True}
    assert client.call_count == 2
    assert len(sleep_calls) == 1


def test_exhausted_retries_returns_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """When all attempts return 500, an error dict is returned after MAX_RETRIES+1 calls."""
    sleep_calls: list[float] = []
    client = MockSequentialClient([MockResponse(500)] * (MAX_RETRIES + 1))
    _patch_client(monkeypatch, client, sleep_calls)

    result = asyncio.run(make_intervals_request("/athlete/i1"))

    assert result.get("error") is True  # type: ignore[union-attr]
    assert client.call_count == MAX_RETRIES + 1
    assert len(sleep_calls) == MAX_RETRIES


def test_retry_after_capped_at_max_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    """Retry-After values larger than _MAX_DELAY_SECS are capped."""
    sleep_calls: list[float] = []
    client = MockSequentialClient(
        [
            MockResponse(429, headers={"Retry-After": "9999"}),
            MockResponse(200, data={}),
        ]
    )
    _patch_client(monkeypatch, client, sleep_calls)

    asyncio.run(make_intervals_request("/athlete/i1"))

    from intervals_mcp_server.api.client import _MAX_DELAY_SECS

    assert sleep_calls[0] == _MAX_DELAY_SECS
