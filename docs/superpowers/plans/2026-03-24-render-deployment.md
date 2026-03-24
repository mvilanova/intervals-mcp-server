# Render Deployment Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy intervals-mcp-server to Render as a Docker Web Service with SSE transport so Claude can connect from any device.

**Architecture:** The server runs as a Render Web Service using the existing Dockerfile. Two code changes are needed: `server.py` must pass `FASTMCP_HOST` from the environment to the `FastMCP` constructor (otherwise the server binds to `127.0.0.1` inside the container and is unreachable), and the Dockerfile `CMD` must invoke Python directly so the `MCP_TRANSPORT` env var is respected. After deployment, the Render HTTPS URL is added as a remote MCP server in Claude's integrations settings.

**Tech Stack:** Python 3.12, FastMCP (mcp[cli]), Docker, Render Web Service, pytest

---

## Chunk 1: Code changes

### Task 1: Fix FASTMCP_HOST binding in server.py

**Files:**
- Modify: `src/intervals_mcp_server/server.py:64`
- Create: `tests/test_server_config.py`

**Background:** `FastMCP.__init__` passes `host="127.0.0.1"` as an explicit keyword argument to its internal pydantic `Settings()`. Explicit kwargs take priority over environment variables in pydantic-settings, so `FASTMCP_HOST=0.0.0.0` in the environment is silently ignored. The fix is to pass the env var value explicitly at construction time.

- [ ] **Step 1: Write the failing test**

Create `tests/test_server_config.py`:

```python
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
    # Remove cached intervals_mcp_server modules so the import picks up the new env var
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/stevenboere/intervals-mcp-server/.claude/worktrees/modest-wilson
uv run pytest tests/test_server_config.py -v
```

Expected: `test_fastmcp_host_reads_from_env` FAILS (host is still `127.0.0.1`). `test_fastmcp_host_default_is_localhost` may pass or fail depending on module cache state.

- [ ] **Step 3: Implement the fix in server.py**

In `src/intervals_mcp_server/server.py`, add `os` to the standard library imports at the top of the file (after the existing `import logging`):

```python
import logging
import os
```

Then change line 64 from:

```python
mcp = FastMCP("intervals-icu", lifespan=setup_api_client)
```

to:

```python
mcp = FastMCP("intervals-icu", lifespan=setup_api_client, host=os.getenv("FASTMCP_HOST", "127.0.0.1"))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_server_config.py -v
```

Expected: both tests PASS.

- [ ] **Step 5: Run the full test suite to confirm no regressions**

```bash
uv run pytest -v tests
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/intervals_mcp_server/server.py tests/test_server_config.py
git commit -m "fix: read FASTMCP_HOST from env when creating FastMCP instance"
```

---

### Task 2: Fix Dockerfile CMD

**Files:**
- Modify: `Dockerfile:26`

**Background:** The current `CMD ["mcp", "run", "src/intervals_mcp_server/server.py"]` uses the `mcp` CLI, which does not execute the `if __name__ == "__main__":` block in `server.py`. This means `setup_transport()` and `start_server()` are never called, so `MCP_TRANSPORT=sse` is ignored and the server starts on stdio instead of SSE.

- [ ] **Step 1: Update the Dockerfile CMD**

Change the last line of `Dockerfile` from:

```dockerfile
CMD ["mcp", "run", "src/intervals_mcp_server/server.py"]
```

to:

```dockerfile
CMD ["python", "src/intervals_mcp_server/server.py"]
```

- [ ] **Step 2: Commit**

```bash
git add Dockerfile
git commit -m "fix: use python entrypoint in Dockerfile so MCP_TRANSPORT is respected"
```

---

## Chunk 2: Render deployment

These are manual steps, not code changes. Complete them after the code changes are merged to `main`.

### Task 3: Create Render Web Service

- [ ] **Step 1: Push the branch and merge to main**

Ensure both commits from Chunk 1 are on `main` (or open a PR and merge).

- [ ] **Step 2: Create a new Web Service on Render**

1. Go to [render.com](https://render.com) → **New** → **Web Service**
2. Connect your GitHub repository (`intervals-mcp-server`)
3. Set **Branch** to `main`
4. Set **Runtime** to **Docker**
5. Set **Port** to `8000`
6. Set **Health Check Path** to `/sse`

- [ ] **Step 3: Set environment variables**

In the Render dashboard, under **Environment**, add:

| Key | Value |
|---|---|
| `MCP_TRANSPORT` | `sse` |
| `FASTMCP_HOST` | `0.0.0.0` |
| `ATHLETE_ID` | your Intervals.icu athlete ID (e.g. `i12345`) |
| `API_KEY` | your Intervals.icu API key |
| `INTERVALS_API_BASE_URL` | `https://intervals.icu/api/v1` |

- [ ] **Step 4: Deploy and verify**

1. Click **Create Web Service** — Render will build the Docker image and deploy.
2. Wait for the health check to pass (green status in Render dashboard).
3. Note your service URL, e.g. `https://intervals-mcp-server-xxxx.onrender.com`.
4. Verify the SSE endpoint responds: open `https://<your-service>.onrender.com/sse` in a browser — you should see a `text/event-stream` response (the connection stays open).

---

### Task 4: Configure Claude integrations

- [ ] **Step 1: Add MCP server in Claude**

On any device:

1. Open Claude (web or mobile) → **Settings** → **Integrations** (or **MCP Servers**)
2. Click **Add** (or **Connect apps**)
3. Fill in:
   - **Name:** `Intervals.icu`
   - **URL:** `https://<your-render-service>.onrender.com/sse`
4. Save.

- [ ] **Step 2: Verify tools are available**

Open a new Claude conversation and ask:
> "What MCP tools do you have available?"

Expected: tools like `get_activities`, `get_wellness_data`, `get_events` etc. appear in the list.

- [ ] **Step 3: End-to-end test**

Ask Claude:
> "Fetch my recent activities from Intervals.icu"

Expected: Claude calls `get_activities` and returns your real activity data.
