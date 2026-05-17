# Contributor Guide

This project contains a Python 3.12 backend service (source in `src/intervals_mcp_server`, tests in `tests`) plus a Next.js dashboard under `web/`.

## Product Direction

Before implementing dashboard, coach, analytics, roadmap, or product-facing work, read:

- `docs/PRODUCT_DIRECTION.md` - product north star and feature gate.
- `docs/fitness-intelligence-model.md` - decision-engine/spec, if present.

All GitHub issues and PRs should align with the product direction. If an issue conflicts with it, pause and ask the maintainer before implementing.

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

## Merge / Postmerge Operations

Merges require explicit maintainer approval. When a maintainer asks to merge and postmerge a PR, use the project helper as the canonical automation surface instead of rebuilding the checklist by hand:

```bash
python scripts/getmailean_merge_postmerge.py <PR>                 # inspect only
python scripts/getmailean_merge_postmerge.py <PR> --merge --postmerge --yes
```

The helper keeps phase state in `/home/lauureal/projects/getmailean/ops/merge-state/`, cleans canonical worktrees under `/home/lauureal/git/getmAIlean-worktrees/`, updates linked GitHub Issue status labels, checks main-branch CI/CD, checks production `/health`, and writes a handoff only when the risk tier requires one.

Do not duplicate this workflow in ad hoc docs. Keep the helper and the Palmilila `getmailean-merge-postmerge` skill as the SSOT pair for merge/postmerge operations.

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

## Web Dashboard

The Next.js dashboard lives under `web/`.

- Install/sync dependencies from `web/`: `npm install`.
- Start local development from `web/`: `npm run dev`.
- Run dashboard checks from `web/`: `npm run lint`, `npm run typecheck`, `npm run test`, and `npm run build`.
