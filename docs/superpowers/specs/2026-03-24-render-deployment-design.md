# Render Deployment Design: intervals-mcp-server

**Date:** 2026-03-24
**Status:** Approved

## Goal

Deploy the intervals-mcp-server to Render so it is accessible from Claude on any device (phone, tablet, other laptops) — not just the local machine.

## Context

The server currently runs locally via stdio transport, which means it is only available in Claude Desktop on the machine where it runs. The server already supports SSE and Streamable HTTP transports via the `MCP_TRANSPORT` environment variable. A Dockerfile already exists.

## Approach

Deploy as a Render Web Service using the existing Dockerfile, with `MCP_TRANSPORT=sse`. Claude (web and mobile) supports remote MCP servers via SSE. The Render-provided HTTPS URL is used directly as the MCP server URL in Claude's integrations settings.

Security relies on URL obscurity (the Render subdomain is not guessable). No additional authentication is added.

## Architecture

```
Claude (any device, any platform)
        │  HTTPS + SSE
        ▼
Render Web Service  (Docker)
  └── intervals-mcp-server
        │  MCP_TRANSPORT=sse
        │  FASTMCP_HOST=0.0.0.0
        │  FASTMCP_PORT=8000
        └── Intervals.icu API (HTTPS)
```

## Changes Required

### 1. Dockerfile — CMD change

The current `CMD` uses `mcp run`, which bypasses the `__main__` block in `server.py` and therefore ignores the `MCP_TRANSPORT` environment variable. Change it to invoke Python directly:

```dockerfile
# Before
CMD ["mcp", "run", "src/intervals_mcp_server/server.py"]

# After
CMD ["python", "src/intervals_mcp_server/server.py"]
```

No other code changes are required. The transport selection logic in `server_setup.py` already handles SSE correctly.

### 2. Render Web Service configuration

| Setting | Value |
|---|---|
| Type | Web Service |
| Runtime | Docker |
| Branch | `main` |
| Port | `8000` |
| Health check path | `/sse` |

Environment variables to set in Render dashboard:

| Variable | Value |
|---|---|
| `MCP_TRANSPORT` | `sse` |
| `FASTMCP_HOST` | `0.0.0.0` |
| `FASTMCP_PORT` | `8000` |
| `ATHLETE_ID` | your Intervals.icu athlete ID |
| `API_KEY` | your Intervals.icu API key |
| `INTERVALS_API_BASE_URL` | `https://intervals.icu/api/v1` |
| `LOG_LEVEL` | `INFO` |

### 3. Claude integration configuration

In Claude (web or mobile): **Settings → Integrations → Add MCP Server**

- **Name:** Intervals.icu
- **URL:** `https://<your-render-service-name>.onrender.com/sse`

This works on all devices where the user is logged in to Claude.

## Out of Scope

- Authentication / access control (URL obscurity accepted as sufficient for personal use)
- Streamable HTTP transport (SSE chosen for broader claude.ai support)
- CI/CD pipeline changes (Render auto-deploys from the connected GitHub branch)

## Testing

1. After deploy, verify the service starts and the health check at `/sse` returns HTTP 200.
2. Add the SSE URL to Claude integrations and confirm the tools (`get_activities`, `get_wellness_data`, etc.) appear.
3. Test a tool call from Claude mobile to confirm end-to-end connectivity.
