# Contributor Guide

This project is a Python 3.12 backend service built with FastMCP and httpx. All source code lives under `src/intervals_mcp_server` and tests live under `tests`.

## Development Environment
- Use [uv](https://github.com/astral-sh/uv) to create and manage the virtual environment.
  - `uv venv --python 3.12`
  - `source .venv/bin/activate`
- Sync dependencies including dev extras with `uv sync --all-extras`.
- When running the server manually prefer `mcp run -t sse src/intervals_mcp_server/sse_server.py:mcp` or the convenience script `python scripts/launch_stack.py` (starts FastMCP + ngrok).

## Testing Instructions
- Run unit tests with `pytest` from the repository root.
- Ensure linting passes with `ruff check .`.
- Run static type checks using `mypy src tests`.
- All three steps (`ruff`, `mypy`, and `pytest`) should succeed before committing.

## PR Instructions
- Use concise commit messages.
- Title pull requests using the format `[intervals-mcp-server] <brief description>`.
- Describe any manual testing steps performed and mention whether `pytest`, `ruff`, and `mypy` passed.

There is currently no frontend code in this repository. If a frontend is added in the future (for example with React or another framework), document how to run and test it within this file.
