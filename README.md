# Intervals.icu MCP Server

Model Context Protocol (MCP) server for connecting AI assistants (Claude, ChatGPT, Smithery, and custom MCP clients) with the Intervals.icu API. It exposes tools that retrieve and manipulate activities, workouts, events, intervals, and wellness metrics for a configured athlete.

> **About this fork**
>
> This repository is a maintained fork of [@mvilanova/intervals-mcp-server](https://github.com/mvilanova/intervals-mcp-server), now hosted at [@al1sse/intervals-mcp-server](https://github.com/al1sse/intervals-mcp-server). It keeps the original FastMCP tooling while adding first-class support for ChatGPT's SSE transport, one-command launch scripts, and debugging utilities for ngrok/remote MCP clients.

## Requirements

- Python 3.12 or higher
- [Model Context Protocol (MCP) Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- `httpx`
- `python-dotenv`

## Setup

### 1. Install uv (recommended)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Clone this repository

```bash
git clone https://github.com/al1sse/intervals-mcp-server.git
cd intervals-mcp-server
```

### 3. Create and activate a virtual environment

```bash
# Create virtual environment with Python 3.12
uv venv --python 3.12

# Activate virtual environment
# On macOS/Linux:
source .venv/bin/activate
# On Windows (PowerShell):
.venv\Scripts\Activate.ps1
```

### 4. Sync project dependencies

```bash
uv sync
```

### 5. Set up environment variables

Make a copy of `.env.example` and name it `.env`:

```bash
cp .env.example .env              # macOS/Linux
```

```powershell
copy .env.example .env            # Windows PowerShell
```

Then edit the `.env` file and set your Intervals.icu athlete id and API key:

```
API_KEY=your_intervals_api_key_here
ATHLETE_ID=your_athlete_id_here
```

#### Getting your Intervals.icu API Key

1. Log in to your Intervals.icu account
2. Go to Settings > API
3. Generate a new API key

#### Finding your Athlete ID

Your athlete ID is typically visible in the URL when you're logged into Intervals.icu. It looks like:
- `https://intervals.icu/athlete/i12345/...` where `i12345` is your athlete ID

> **Tip:** Placeholder values such as `your_athlete_id_here` or `<YOUR_ATHLETE_ID>` are ignored by the server. If they slip through a client request, the code falls back to the real ID defined in `.env`.

## Quick start: local server + ngrok tunnel

The repository includes helper scripts so you can stand up the whole stack (FastMCP server + ngrok tunnel) with one command:

```powershell
python scripts/launch_stack.py
```

What happens under the hood:

- `mcp run -t sse src/intervals_mcp_server/sse_server.py:mcp` starts automatically.
- The script loads `.env` and forwards `API_KEY`, `ATHLETE_ID`, etc. to the child processes.
- `ngrok http 8000` launches alongside the server and exposes the SSE endpoint.
- Logs from both processes are streamed with prefixes (`[mcp]`, `[ngrok]`).

Use `Ctrl+C` to stop both processes. On Windows you can also double-click `launch_stack.bat`, which wraps the same command.

### Verify the tunnel

Read the HTTPS URL printed by ngrok and probe it:

```bash
python scripts/test_ngrok_sse.py https://<ngrok-id>.ngrok-free.dev
```

The script connects to `<url>/sse/`, checks for `text/event-stream`, and prints the first SSE event so you know the stream is alive.

### Call tools without an AI client

Use the bundled minimal MCP client to list and call tools over SSE:

```bash
python scripts/quick_mcp_client.py --base-url https://<ngrok-id>.ngrok-free.dev list

python scripts/quick_mcp_client.py --base-url https://<ngrok-id>.ngrok-free.dev \
    call get_activities start_date=2025-10-25 end_date=2025-10-25 include_unnamed=true
```

If you want to bypass MCP entirely and invoke the coroutine directly, run:

```bash
python scripts/test_get_activities.py --start-date 2025-10-25 --end-date 2025-10-25
```

### Connect ChatGPT

1. Keep `scripts/launch_stack.py` (or `launch_stack.bat`) running.
2. In ChatGPT open **Settings → MCP Servers → Add Server**.
3. Set **Type** to `sse`, **URL** to `https://<ngrok-id>.ngrok-free.dev/sse/`, and supply headers only if you do **not** want to load credentials from `.env`.
4. Save; ChatGPT should show the connector as **connected**. Turn it on in a new chat and call tools like “List my activities on 25 Oct 2025.”

### Connect Claude Desktop

Claude still works with the classic CLI wiring:

```bash
mcp install src/intervals_mcp_server/server.py \
  --name "Intervals.icu" \
  --with-editable . \
  --env-file .env
```

If Claude cannot find `uv` or `python`, open `claude_desktop_config.json` and replace the `command` with the fully qualified path (for example `"C:\\path\\to\\intervals-mcp-server\\.venv\\Scripts\\python.exe"`). Restart Claude afterwards. You can also point Claude at the ngrok SSE URL the same way as ChatGPT.

## Updating

This project is actively developed, with new features and fixes added regularly. To stay up to date, follow these steps:

### 1. Pull the latest changes from `main`

> ⚠️ Make sure you don’t have uncommitted changes before running this command.

```bash
git checkout main
git pull
```

### 2. Update Python dependencies

Activate your virtual environment and sync dependencies:

```bash
source .venv/bin/activate   # macOS/Linux
uv sync
```

```powershell
.\.venv\Scripts\Activate.ps1
uv sync
```

## Usage

Once the connector (ChatGPT, Claude, or a custom client) is configured, the following tools are available:

- `get_activities`: Retrieve a list of recent activities.
- `get_activity_details`: Detailed information for a specific activity.
- `get_activity_intervals`: Interval metrics for an activity.
- `get_wellness_data`: Daily wellness metrics.
- `get_events`: Upcoming events/workouts.
- `get_event_by_id`: Detailed information for a specific event.
- `add_or_update_event`, `delete_event`, and `delete_events_by_date_range`: Manage calendar entries.

Explore tool signatures inside `src/intervals_mcp_server/server.py` or run `python scripts/quick_mcp_client.py --base-url <url> list` to see them dynamically.

## Development

Install development dependencies and run standard checks with:

```bash
uv sync --all-extras
ruff check .
mypy src tests
pytest -q
```

During development you can run the FastMCP server directly:

```bash
mcp run -t sse src/intervals_mcp_server/sse_server.py:mcp
```

For quick smoke tests without the MCP stack:

- `python scripts/smoke_register.py`: list registered tools.
- `python scripts/test_get_activities.py --start-date YYYY-MM-DD --end-date YYYY-MM-DD`: call tools directly.
- `python scripts/quick_mcp_client.py --base-url <url> call <tool>`: interact with the server over SSE.

## Troubleshooting

- **403 Forbidden from Intervals.icu** – usually an API key or athlete ID mismatch. Confirm `.env` and restart `scripts/launch_stack.py`.
- **`YOUR_ATHLETE_ID` appears in logs** – restart the stack. The server sanitises placeholder IDs, but a restart guarantees the real value is in memory.
- **SSE probe hangs** – run `python scripts/test_ngrok_sse.py <url>` to confirm the tunnel is streaming. ngrok free endpoints often sleep; restart if needed.
- **ChatGPT connector offline** – ensure the connector type is `sse`, the URL ends with `/sse/`, and the tunnel is live. `scripts/quick_mcp_client.py --base-url <url> list` is an easy sanity check.
- **Claude Desktop runtime errors** – edit `claude_desktop_config.json` so the `command` field points to the fully-qualified `python.exe` or `uv` path, then restart Claude.

## License

The GNU General Public License v3.0
