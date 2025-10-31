import types
import builtins

import pytest


def test_register_tool_api(monkeypatch):
    """When a runtime exposes `register_tool`, mcp_compat should call it."""
    calls = []

    def fake_register_tool(name=None, func=None, description=None):
        calls.append((name, func, description))

    fake_mod = types.SimpleNamespace(register_tool=fake_register_tool, run=lambda: None)

    # Monkeypatch import to return our fake module when probed
    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name.startswith("openai") or name.startswith("openai_mcp"):
            return fake_mod
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    from intervals_mcp_server.mcp_compat import FastMCP

    mcp = FastMCP("test")

    @mcp.tool()
    async def mytool(x: int = 1):
        """Test tool"""
        return x

    # Calling run should use our fake runtime and register the tool
    mcp.run()

    assert calls, "register_tool should have been called"
    assert calls[0][0] == "mytool"


def test_tool_decorator_api(monkeypatch):
    """When a runtime exposes `tool` as a decorator, mcp_compat should use it."""
    calls = []

    def fake_tool(name=None, description=None):
        def decorator(func):
            calls.append((name, description, func))
            return func

        return decorator

    fake_mod = types.SimpleNamespace(tool=fake_tool, run=lambda: None)

    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name.startswith("openai") or name.startswith("openai_mcp"):
            return fake_mod
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    from intervals_mcp_server.mcp_compat import FastMCP

    mcp = FastMCP("test2")

    @mcp.tool()
    async def mytool2():
        """Another test tool"""
        return True

    mcp.run()

    assert calls, "tool decorator should have been used"
    assert calls[0][0] in ("mytool2", None)
