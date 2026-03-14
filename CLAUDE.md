# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies (including dev)
uv sync --all-extras

# Run all tests
pytest -v

# Run a single test
pytest tests/test_server.py::test_get_activities -v

# Lint
ruff check .
ruff check . --fix    # auto-fix

# Type check
mypy src tests

# Run server manually
mcp run src/intervals_mcp_server/server.py
```

All three checks (ruff, mypy, pytest) must pass before committing.

## Architecture

This is an MCP (Model Context Protocol) server that wraps the [Intervals.icu](https://intervals.icu) fitness API. Built with FastMCP and httpx.

### Key design decisions

- **Shared MCP instance**: `mcp_instance.py` holds the single `FastMCP` instance to prevent cyclic imports between `server.py` and tool modules.
- **Tool modules register themselves**: Each file in `tools/` uses `@mcp.tool()` decorators. They are imported by `server.py` to trigger registration.
- **All tools are async** and return formatted strings (not JSON).
- **Single API entry point**: All HTTP calls go through `api/client.py` → `make_intervals_request()`. Uses HTTP Basic Auth with username `"API_KEY"`.
- **Singleton config**: `config.py` loads env vars once; validated at runtime (not import time) so tests can mock.
- **Lazy httpx client**: `AsyncClient` created on demand with retry on unexpected close.

### Module layout

- `src/intervals_mcp_server/tools/` — MCP tools: `activities.py` (6), `events.py` (6), `wellness.py` (1), `athlete.py` (3), `custom_items.py` (5), `search.py` (2), `workouts.py` (3), `seasons.py` (3)
- `src/intervals_mcp_server/api/client.py` — HTTP client, error handling, response parsing
- `src/intervals_mcp_server/utils/` — Validation, date helpers, formatting, type definitions (enums + dataclasses), schemas (dataclass definitions for API responses)
- `src/intervals_mcp_server/config.py` — Singleton config from env vars
- `src/intervals_mcp_server/server_setup.py` — Transport setup (stdio or SSE)

### Adding a new tool

1. Create or edit a file in `tools/`
2. Import `mcp` from `mcp_instance`
3. Decorate with `@mcp.tool()`
4. Use `make_intervals_request()` for API calls
5. Import the tool module in `server.py`

## Testing patterns

- Async tests use `@pytest.mark.asyncio`
- Mock API with `monkeypatch.setattr` on both `api.client.make_intervals_request` and the tool module's imported reference
- Sample data lives in `tests/sample_data.py`

## Environment variables

Required: `API_KEY`, `ATHLETE_ID`. Optional: `INTERVALS_API_BASE_URL`, `MCP_TRANSPORT` (stdio/sse), `FASTMCP_HOST`, `FASTMCP_PORT`.

## PR conventions

Title format: `[intervals-mcp-server] <brief description>`
