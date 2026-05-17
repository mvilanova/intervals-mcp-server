# Contributor Guide

This project is a Python 3.12 backend service built with FastMCP and httpx. All source code lives under `src/intervals_mcp_server` and tests live under `tests`.

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

## GitHub Issue Workflow for Agents

GitHub Issues are the coordination surface for this repository. Before starting work, check the open issues and only pick issues that are not already claimed.

Use these status labels consistently so other agents know what is safe to pick:

- `status:available` means the issue is ready for an agent to take.
- `status:claimed` means an agent is actively working on it.
- `status:blocked` means work cannot continue without a decision or dependency.
- `status:done` means the issue has been implemented and is waiting for closure or merge confirmation.

When taking an issue:

1. Add `status:claimed`.
2. Remove `status:available` if present.
3. Assign yourself when possible.
4. Leave a short comment naming the agent working on it and, when useful, the intended scope.

Example:

```bash
gh issue edit <issue-number> --add-label "status:claimed" --remove-label "status:available" --add-assignee @me
gh issue comment <issue-number> --body "Claimed by: <agent-name>\n\nScope: <short description of planned work>"
```

When stopping work without finishing, remove `status:claimed`, unassign yourself, and either restore `status:available` or add `status:blocked` with a comment explaining the blocker.

There is currently no frontend code in this repository. If a frontend is added in the future (for example with React or another framework), document how to run and test it within this file.
