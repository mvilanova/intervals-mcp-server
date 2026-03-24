"""
Tests for server configuration — specifically that FASTMCP_HOST env var
is respected when creating the FastMCP instance.
"""
import os
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("API_KEY", "test")
os.environ.setdefault("ATHLETE_ID", "i1")


def _fresh_server(monkeypatch, host):
    """Import server.py in a fresh module context with FASTMCP_HOST set."""
    monkeypatch.setenv("FASTMCP_HOST", host)
    for key in list(sys.modules.keys()):
        if "intervals_mcp_server" in key:
            del sys.modules[key]
    import intervals_mcp_server.server as srv  # pylint: disable=import-outside-toplevel
    return srv


def test_fastmcp_host_default_is_localhost(monkeypatch):
    """When FASTMCP_HOST is not set, the mcp instance should bind to 127.0.0.1."""
    monkeypatch.delenv("FASTMCP_HOST", raising=False)
    for key in list(sys.modules.keys()):
        if "intervals_mcp_server" in key:
            del sys.modules[key]
    import intervals_mcp_server.server as srv  # pylint: disable=import-outside-toplevel
    assert srv.mcp.settings.host == "127.0.0.1"


def test_fastmcp_host_reads_from_env(monkeypatch):
    """When FASTMCP_HOST=0.0.0.0 is set, the mcp instance should bind to 0.0.0.0."""
    srv = _fresh_server(monkeypatch, "0.0.0.0")
    assert srv.mcp.settings.host == "0.0.0.0"
