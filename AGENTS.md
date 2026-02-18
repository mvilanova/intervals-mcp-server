# Contributor Guide

This project is a Python 3.12 backend service built with FastMCP and httpx. All source code lives under `src/intervals_mcp_server` and tests live under `tests`.

## Project Architecture

The codebase follows a modular architecture:

- **MCP Tools**: Organized by domain in `src/intervals_mcp_server/tools/`:
  - `activities.py` - Activity retrieval and analysis
  - `events.py` - Calendar event management
  - `wellness.py` - Wellness data retrieval
  - `plans.py` - Training plan management
  - `performance.py` - Athlete performance data retrieval
  - `__init__.py` - Tool registration and exports

- **API Client**: `src/intervals_mcp_server/api/client.py`
  - `make_intervals_request()` - Central HTTP client function
  - Shared `httpx.AsyncClient` with connection pooling
  - Comprehensive error handling

- **Utilities**: `src/intervals_mcp_server/utils/`
  - `formatting.py` - Data formatting for MCP responses
  - `validation.py` - Input validation helpers
  - `dates.py` - Date handling utilities
  - `types.py` - Type definitions

- **Server**: `src/intervals_mcp_server/server.py` - FastMCP server initialization

## Development Environment
- Use [uv](https://github.com/astral-sh/uv) to create and manage the virtual environment.
  - `uv venv --python 3.12`
  - `source .venv/bin/activate`
- Sync dependencies including dev extras with `uv sync --all-extras`.
- When editing or running the server manually use `mcp run src/intervals_mcp_server/server.py`.

## Testing Instructions
- Run unit tests with `pytest` from the repository root.
- Ensure linting passes with `ruff .` (no configuration file means default rules).
- Run static type checks using `mypy src tests`.
- All three steps (`ruff`, `mypy`, and `pytest`) should succeed before committing.

## PR Instructions
- Use concise commit messages.
- Title pull requests using the format `[intervals-mcp-server] <brief description>`.
- Describe any manual testing steps performed and mention whether `pytest`, `ruff`, and `mypy` passed.

There is currently no frontend code in this repository. If a frontend is added in the future (for example with React or another framework), document how to run and test it within this file.
