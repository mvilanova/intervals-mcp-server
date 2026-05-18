"""Tests for shared MCP tool helpers in tools/common.py."""

from __future__ import annotations

from intervals_mcp_server.tools.common import (
    format_tool_error,
    is_error_result,
    resolve_tool_context,
)


class TestIsErrorResult:
    def test_error_dict_returns_true(self):
        assert is_error_result({"error": True, "message": "Something failed"}) is True

    def test_error_dict_with_false_value_returns_true(self):
        # key presence matters, not truthiness of value
        assert is_error_result({"error": False, "message": "ok"}) is True

    def test_regular_dict_returns_false(self):
        assert is_error_result({"id": 1, "name": "test"}) is False

    def test_list_returns_false(self):
        assert is_error_result([{"id": 1}]) is False

    def test_none_returns_false(self):
        assert is_error_result(None) is False

    def test_empty_dict_returns_false(self):
        assert is_error_result({}) is False


class TestFormatToolError:
    def test_formats_with_message(self):
        result = {"error": True, "message": "Not found"}
        assert format_tool_error("fetching activities", result) == "Error fetching activities: Not found"

    def test_falls_back_when_message_missing(self):
        result = {"error": True}
        assert format_tool_error("deleting event", result) == "Error deleting event: Unknown error"

    def test_message_none_renders_as_none(self):
        # dict.get fallback only fires for missing key, not None value
        result = {"error": True, "message": None}
        assert format_tool_error("creating item", result) == "Error creating item: None"

    def test_preserves_action_string_verbatim(self):
        result = {"error": True, "message": "bad request"}
        output = format_tool_error("updating custom item", result)
        assert output.startswith("Error updating custom item:")


class TestResolveToolContext:
    def test_explicit_athlete_id_resolves(self):
        athlete_id, api_key, error_msg = resolve_tool_context("i123", "key")
        assert athlete_id == "i123"
        assert api_key == "key"
        assert error_msg is None

    def test_api_key_propagated_unchanged(self):
        _, api_key, _ = resolve_tool_context("i1", "my-api-key")
        assert api_key == "my-api-key"

    def test_api_key_none_propagated(self):
        _, api_key, _ = resolve_tool_context("i1", None)
        assert api_key is None

    def test_missing_athlete_id_returns_error(self, monkeypatch):
        # Patch config so the default athlete_id is empty
        monkeypatch.setattr(
            "intervals_mcp_server.tools.common.get_config",
            lambda: type("C", (), {"athlete_id": ""})(),
        )
        athlete_id, _api_key, error_msg = resolve_tool_context(None, None)
        assert athlete_id == ""
        assert error_msg is not None
        assert "athlete" in error_msg.lower()

    def test_falls_back_to_config_athlete_id(self, monkeypatch):
        monkeypatch.setattr(
            "intervals_mcp_server.tools.common.get_config",
            lambda: type("C", (), {"athlete_id": "i99"})(),
        )
        athlete_id, _, error_msg = resolve_tool_context(None, None)
        assert athlete_id == "i99"
        assert error_msg is None

    def test_explicit_overrides_config(self, monkeypatch):
        monkeypatch.setattr(
            "intervals_mcp_server.tools.common.get_config",
            lambda: type("C", (), {"athlete_id": "i99"})(),
        )
        athlete_id, _, error_msg = resolve_tool_context("i42", None)
        assert athlete_id == "i42"
        assert error_msg is None
