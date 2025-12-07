"""
Tests for environment-based host/port overrides when initializing FastMCP.

These ensure module-level construction honors FASTMCP_HOST/FASTMCP_PORT and
falls back to defaults when unset.
"""

import importlib
import sys

import pytest


@pytest.mark.parametrize(
    ("env_host", "env_port", "expected_host", "expected_port"),
    [
        (None, None, "127.0.0.1", 8000),
        ("0.0.0.0", None, "0.0.0.0", 8000),
        (None, "9000", "127.0.0.1", 9000),
        ("0.0.0.0", "9000", "0.0.0.0", 9000),
    ],
)
def test_fastmcp_host_port_env(monkeypatch, env_host, env_port, expected_host, expected_port):
    """
    FastMCP should honor env overrides for host/port during module import.
    """
    if env_host is not None:
        monkeypatch.setenv("FASTMCP_HOST", env_host)
    else:
        monkeypatch.delenv("FASTMCP_HOST", raising=False)

    if env_port is not None:
        monkeypatch.setenv("FASTMCP_PORT", env_port)
    else:
        monkeypatch.delenv("FASTMCP_PORT", raising=False)

    # Provide deterministic config values and clear cached modules/config.
    monkeypatch.setenv("API_KEY", "test")
    monkeypatch.setenv("ATHLETE_ID", "i1")
    for module_name in (
        "intervals_mcp_server.server",
        "intervals_mcp_server.config",
        "intervals_mcp_server.mcp_instance",
    ):
        sys.modules.pop(module_name, None)

    try:
        config_module = importlib.import_module("intervals_mcp_server.config")
        config_module._config_instance = None  # type: ignore[attr-defined]

        server_module = importlib.import_module("intervals_mcp_server.server")
        assert server_module.mcp.settings.host == expected_host
        assert server_module.mcp.settings.port == expected_port
    finally:
        for module_name in (
            "intervals_mcp_server.server",
            "intervals_mcp_server.config",
            "intervals_mcp_server.mcp_instance",
        ):
            sys.modules.pop(module_name, None)
