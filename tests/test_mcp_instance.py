"""Tests for reading FastMCP network settings from environment variables."""

import pytest

from intervals_mcp_server.mcp_instance import fastmcp_settings_from_env


def test_empty_environment_returns_no_overrides():
    assert fastmcp_settings_from_env({}) == {}


def test_host_port_and_paths_are_read():
    settings = fastmcp_settings_from_env(
        {
            "FASTMCP_HOST": "0.0.0.0",
            "FASTMCP_PORT": "8765",
            "FASTMCP_STREAMABLE_HTTP_PATH": "/secret/mcp",
            "FASTMCP_SSE_PATH": "/secret/sse",
            "FASTMCP_LOG_LEVEL": "debug",
        }
    )
    assert settings == {
        "host": "0.0.0.0",
        "port": 8765,
        "streamable_http_path": "/secret/mcp",
        "sse_path": "/secret/sse",
        "log_level": "DEBUG",
    }


def test_blank_values_are_ignored():
    assert fastmcp_settings_from_env({"FASTMCP_HOST": "  ", "FASTMCP_PORT": ""}) == {}


def test_invalid_port_raises():
    with pytest.raises(ValueError, match="FASTMCP_PORT"):
        fastmcp_settings_from_env({"FASTMCP_PORT": "abc"})


def test_settings_are_applied_to_fastmcp():
    from mcp.server.fastmcp import FastMCP

    server = FastMCP(
        "test", **fastmcp_settings_from_env({"FASTMCP_HOST": "0.0.0.0", "FASTMCP_PORT": "8765"})
    )
    assert server.settings.host == "0.0.0.0"
    assert server.settings.port == 8765
