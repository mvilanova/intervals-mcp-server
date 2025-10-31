"""Compatibility shim to expose a FastMCP-like API while allowing
an easy migration to OpenAI/ChatGPT MCP runtime.

This module provides a minimal `FastMCP` class with a `.tool()` decorator
and a `.run()` method. It collects registered tools so a downstream
starter can wire them into the OpenAI MCP runtime. The shim intentionally
does not import the OpenAI SDK directly so the repository remains
importable for tests until dependencies are added.

Usage:
    from intervals_mcp_server.mcp_compat import FastMCP

    mcp = FastMCP("intervals-icu", lifespan=lifespan)

The shim stores tool callables and exposes `get_tools()` to allow a
bootstrapper to register them with the real MCP runtime.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, Callable, Coroutine, Dict, List, Optional


class Tool:
    def __init__(self, func: Callable[..., Coroutine[Any, Any, Any]], name: Optional[str] = None):
        self.func = func
        self.name = name or func.__name__
        self.doc = func.__doc__ or ""


class FastMCP:
    """Minimal FastMCP-compatible façade.

    - `.tool()` is a decorator for async tool callables
    - `.run()` is a placeholder runner; if OpenAI's MCP runtime isn't
      installed it raises an informative error.
    - `get_tools()` returns registered tools for external wiring.
    """

    def __init__(self, name: str, *, lifespan: Optional[Callable] = None):
        self.name = name
        self._lifespan = lifespan
        self._tools: Dict[str, Tool] = {}

    def tool(self):
        """Decorator to register a coroutine function as a tool."""

        def decorator(func: Callable[..., Coroutine[Any, Any, Any]]):
            tool = Tool(func)
            self._tools[tool.name] = tool
            return func

        return decorator

    def get_tools(self) -> List[Tool]:
        """Return a list of registered tools."""
        return list(self._tools.values())

    async def _call_lifespan(self):
        """Run the lifespan context if provided."""
        if self._lifespan is None:
            return
        # lifespan is expected to be an asynccontextmanager factory
        try:
            cm = self._lifespan(self)
        except TypeError:
            # lifespan might be an async contextmanager itself
            cm = self._lifespan
        async with cm:
            yield

    def run(self) -> None:
        """Placeholder run method.

        If you want to run under the OpenAI/ChatGPT MCP runtime, wire the
        tools returned by `get_tools()` into that runtime. This placeholder
        raises a helpful message rather than trying to import the OpenAI
        packages at shim-import time.
        """
        # Try to import the OpenAI MCP runtime (the package name and
        # runtime API may vary depending on OpenAI's distribution; we'll
        # attempt to import a likely entry point and register tools. If
        # the import fails, provide a helpful error with the registered
        # tools so a developer can wire them manually.
        try:
            # Probe likely packages and import points for OpenAI's MCP
            # runtime. We don't require a specific package; instead we try
            # several common candidates and adapt to a few expected APIs.
            candidates = [
                ("openai.mcp", "openai.mcp"),
                ("openai_mcp", "openai_mcp"),
                ("openai_mcp.server", "openai_mcp.server"),
            ]

            runtime_server = None
            for mod_name, _label in candidates:
                try:
                    mod = __import__(mod_name, fromlist=["*"])
                except Exception:
                    continue
                # Accept module if it exposes a server-like object
                if hasattr(mod, "server"):
                    runtime_server = getattr(mod, "server")
                    break
                # Or if the module itself exposes registration helpers
                runtime_server = mod
                break

            if runtime_server is None:
                # If no candidate found, raise so fallback behavior can run
                raise ImportError("No OpenAI MCP runtime candidate imported")

            # Try to register tools. Common patterns:
            # - runtime_server.register_tool(name=..., func=..., description=...)
            # - runtime_server.tool(...)(func) as decorator
            # - runtime_server.FastMCP or runtime_server.create_server()
            for tool in self.get_tools():
                registered = False
                # 1) register_tool(name=..., func=...)
                register = getattr(runtime_server, "register_tool", None)
                if callable(register):
                    try:
                        register(name=tool.name, func=tool.func, description=tool.doc)
                        registered = True
                    except TypeError:
                        # Try without description
                        register(name=tool.name, func=tool.func)
                        registered = True

                if not registered:
                    # 2) tool decorator style: runtime_server.tool(name=..., description=...)
                    tool_deco = getattr(runtime_server, "tool", None)
                    if callable(tool_deco):
                        try:
                            deco = tool_deco(name=tool.name, description=tool.doc)
                            deco(tool.func)
                            registered = True
                        except TypeError:
                            try:
                                deco = tool_deco(tool.name)
                                deco(tool.func)
                                registered = True
                            except Exception:
                                pass

                if not registered:
                    # 3) If the runtime exposes a FastMCP-like class, instantiate and register
                    RuntimeFast = getattr(runtime_server, "FastMCP", None) or getattr(runtime_server, "Server", None)
                    if RuntimeFast:
                        try:
                            rt = RuntimeFast(self.name, lifespan=self._lifespan)
                            rt.tool()(tool.func)
                            # We don't start here; we will call run on the selected runtime below
                            registered = True
                        except Exception:
                            registered = False

                if not registered:
                    # If we couldn't register in any known way, raise to trigger fallback
                    raise RuntimeError(f"Couldn't register tool {tool.name} with discovered OpenAI runtime")

            # If runtime provides a run() entrypoint, call it (some runtimes
            # will expose the function at top level or under server)
            run_fn = getattr(runtime_server, "run", None) or getattr(runtime_server, "serve", None)
            if callable(run_fn):
                run_fn()
                return

            # If runtime_server is a class we instantiated earlier, try its run
            inst_run = None
            if 'rt' in locals() and hasattr(rt, "run"):
                inst_run = getattr(rt, "run")
            if callable(inst_run):
                inst_run()
                return

            # If we reach here, the runtime was imported and tools registered
            # but we couldn't find a standard entrypoint to start it.
            raise RuntimeError("Imported an OpenAI MCP runtime but couldn't find a run/serve entrypoint")
        except Exception as exc:  # pragma: no cover - runtime-specific
            # Provide developer-friendly guidance including registered tools
            tools = [t.name for t in self.get_tools()]
            # Fall back to the original `mcp` package's FastMCP server if
            # it's installed. This keeps behavior compatible with the
            # previous implementation while allowing a gradual port to
            # OpenAI's runtime.
            try:
                from mcp.server.fastmcp import FastMCP as RealFastMCP  # type: ignore

                real = RealFastMCP(self.name, lifespan=self._lifespan)
                for tool in self.get_tools():
                    # Re-register the tool with the real FastMCP instance
                    real.tool()(tool.func)

                # Launch the original FastMCP server
                real.run()
                return
            except Exception:
                # If fallback fails, raise an informative error.
                raise RuntimeError(
                    "mcp_compat.FastMCP.run() couldn't start OpenAI MCP runtime or fall back to the installed `mcp` package. "
                    f"Registered tools: {tools}. Original error: {exc}"
                )


__all__ = ["FastMCP", "Tool"]
