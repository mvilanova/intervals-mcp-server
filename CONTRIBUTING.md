# Contributing to Intervals.icu MCP Server

Thank you for taking the time to contribute! This project uses **Python 3.12** and manages its dependencies with [uv](https://github.com/astral-sh/uv). The following guide summarizes how to set up your environment and outlines the workflow we expect for pull requests.

## Development environment

1. Create a virtual environment and activate it:
   ```bash
   uv venv --python 3.12
   source .venv/bin/activate
   ```
2. Install all dependencies (including development extras):
   ```bash
   uv sync --all-extras
   ```
3. When working on or manually running the server, use:
   ```bash
   mcp run src/intervals_mcp_server/server.py
   ```

## Dependency changes

1. Edit `pyproject.toml`.
2. Run `uv lock` (or `uv sync`).
3. Commit **both** `pyproject.toml` and `uv.lock` in the same commit.

If you add, remove, or relax a dependency but forget to update the lock file, CI will fail. Treat `uv.lock` as a first-class artifact: review it when it changes, but don’t fear committing it.

## Code-only changes

For changes that do not modify dependencies, keep the lock file untouched. Run your tests with:

```bash
uv run --locked pytest
```

CI will also run `uv lock --check` to ensure `uv.lock` stays in sync.

## Why keep the lock file?

* **Reproducibility** – All collaborators and CI runners install identical hashes.
* **Security** – Hash pinning in `uv.lock` helps prevent supply-chain attacks.
* **Speed** – `uv` skips resolution when the lock matches, keeping installs lightning-fast.

Automated dependency upgrades are encouraged. You can use Dependabot, Renovate, or a scheduled GitHub Action that runs `uv lock --upgrade && git push` to keep the file fresh and generate tidy PRs.

## Testing

Before opening a pull request, ensure all checks pass locally:

```bash
ruff check .
mypy src tests
uv run --locked pytest
```

## Pull request guidelines

* Use concise commit messages.
* Title your pull request using the format `[intervals-mcp-server] <brief description>`.
* Describe any manual testing you performed and confirm whether `ruff`, `mypy`, and `pytest` passed.

We appreciate your contributions and your attention to these guidelines. Happy coding!
