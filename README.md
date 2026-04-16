# Intervals.icu MCP Server

Model Context Protocol (MCP) server for connecting Claude and ChatGPT with the Intervals.icu API. It provides tools for authentication and data retrieval for activities, events, and wellness data.

If you find the Model Context Protocol (MCP) server useful, please consider supporting its continued development with a donation.

## Requirements

- Python 3.12 or higher
- [Model Context Protocol (MCP) Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- httpx
- python-dotenv

## Setup

### 1. Install uv (recommended)

**macOS/Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

After installation, find the full path to `uv` — you'll need it later when configuring Claude Desktop:

```powershell
where.exe uv
# Example output: C:\Users\<USERNAME>\.local\bin\uv.exe
```

### 2. Clone this repository

```bash
git clone https://github.com/mvilanova/intervals-mcp-server.git
cd intervals-mcp-server
```

### 3. Create and activate a virtual environment

```bash
# Create virtual environment with Python 3.12
uv venv --python 3.12

# Activate virtual environment
# On macOS/Linux:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate
```

### 4. Sync project dependencies

```bash
uv sync
```

### 5. Set up environment variables

Make a copy of `.env.example` and name it `.env` by running the following command:

**macOS/Linux:**
```bash
cp .env.example .env
```

**Windows (PowerShell):**
```powershell
Copy-Item .env.example .env
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

## Updating

This project is actively developed, with new features and fixes added regularly. To stay up to date, follow these steps:

### 1. Pull the latest changes from `main`

> ⚠️ Make sure you don't have uncommitted changes before running this command.

**macOS/Linux:**
```bash
git checkout main && git pull
```

**Windows (PowerShell):**
```powershell
git checkout main; git pull
```

### 2. Update Python dependencies

Activate your virtual environment and sync dependencies:

**macOS/Linux:**
```bash
source .venv/bin/activate
uv sync
```

**Windows (PowerShell):**
```powershell
.venv\Scripts\activate
uv sync
```

### Troubleshooting

If Claude Desktop fails due to configuration changes, follow these steps:

1. Delete the existing `Intervals.icu` entry in `claude_desktop_config.json`.
2. Reconfigure Claude Desktop from the `intervals-mcp-server` directory.

**macOS/Linux:**
```bash
mcp install src/intervals_mcp_server/server.py --name "Intervals.icu" --with-editable . --env-file .env
```

**Windows:** Re-add the entry manually as described in the [Windows configuration section](#windows) above.

#### Common errors

**`spawn uv ENOENT`** — Claude Desktop cannot find the `uv` executable. Use the full path to `uv` in the `command` field. Run `which uv` (macOS/Linux) or `where.exe uv` (Windows) to get it.

**`spawn /Users/... ENOENT` on Windows** — The config file contains a macOS/Linux-style path. Replace it with the correct Windows path using backslashes as described above.

**Windows Store install: config changes not taking effect** — You may be editing the wrong config file. Claude Desktop installed from the Microsoft Store reads from `AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\claude_desktop_config.json`, not `AppData\Roaming\Claude\`.

## Usage with Claude

### 1. Configure Claude Desktop

To use this server with Claude Desktop, you need to add it to your Claude Desktop configuration.

#### macOS/Linux

1. Run the following from the `intervals-mcp-server` directory to configure Claude Desktop:

```bash
mcp install src/intervals_mcp_server/server.py --name "Intervals.icu" --with-editable . --env-file .env
```

2. If you open your Claude Desktop App configuration file `claude_desktop_config.json`, it should look like this:

```json
{
  "mcpServers": {
    "Intervals.icu": {
      "command": "/Users/<USERNAME>/.local/bin/uv",
      "args": [
        "run",
        "--with",
        "mcp[cli]",
        "--with-editable",
        "/path/to/intervals-mcp-server",
        "mcp",
        "run",
        "/path/to/intervals-mcp-server/src/intervals_mcp_server/server.py"
      ],
      "env": {
        "INTERVALS_API_BASE_URL": "https://intervals.icu/api/v1",
        "ATHLETE_ID": "<YOUR_ATHLETE_ID>",
        "API_KEY": "<YOUR_API_KEY>",
        "LOG_LEVEL": "INFO"
      }
    }
  }
}
```

Where `/path/to/` is the path to the `intervals-mcp-server` code folder in your system.

#### Windows

The `mcp install` command may fail on Windows due to environment or permission issues. Instead, configure Claude Desktop manually:

1. Find the Claude Desktop config file. If Claude Desktop was installed from the **Microsoft Store**, the config is located at:

   ```
   C:\Users\<USERNAME>\AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\claude_desktop_config.json
   ```

   If installed via the standard installer, it may be at:

   ```
   C:\Users\<USERNAME>\AppData\Roaming\Claude\claude_desktop_config.json
   ```

   If the file or folder does not exist, create it.

2. Add the following entry to `claude_desktop_config.json`, replacing the placeholders with your actual values:

```json
{
  "mcpServers": {
    "Intervals.icu": {
      "command": "C:\\Users\\<USERNAME>\\.local\\bin\\uv.exe",
      "args": [
        "run",
        "--with",
        "mcp[cli]",
        "--with-editable",
        "C:\\path\\to\\intervals-mcp-server",
        "mcp",
        "run",
        "C:\\path\\to\\intervals-mcp-server\\src\\intervals_mcp_server\\server.py"
      ],
      "env": {
        "INTERVALS_API_BASE_URL": "https://intervals.icu/api/v1",
        "ATHLETE_ID": "<YOUR_ATHLETE_ID>",
        "API_KEY": "<YOUR_API_KEY>",
        "LOG_LEVEL": "INFO"
      }
    }
  }
}
```

   - Use double backslashes (`\\`) for all Windows paths in JSON.
   - To find the full path to `uv.exe`, run `where.exe uv` in PowerShell.
   - To find the full path to the cloned repository, run `pwd` from inside the `intervals-mcp-server` folder.

> **Note for Windows Store installs:** Claude Desktop installed from the Microsoft Store sandboxes its config under `AppData\Local\Packages\...`. Editing `AppData\Roaming\Claude\claude_desktop_config.json` will have no effect — make sure you edit the correct file.

3. Restart Claude Desktop.

### 2. Use the MCP server with Claude

Once the server is running and Claude Desktop is configured, you can use the following tools to ask questions about your past and future activities, events, and wellness data.

- `get_activities`: Retrieve a list of activities
- `get_activity_details`: Get detailed information for a specific activity
- `get_activity_intervals`: Get detailed interval data for a specific activity
- `get_wellness_data`: Fetch wellness data
- `get_events`: Retrieve upcoming events (workouts, races, etc.)
- `get_event_by_id`: Get detailed information for a specific event

## Usage with ChatGPT

ChatGPT’s beta MCP connectors can also talk to this server over the SSE transport.

1. Start the server in SSE mode so it exposes the `/sse` and `/messages/` endpoints:

   ```bash
   export FASTMCP_HOST=127.0.0.1 FASTMCP_PORT=8765 MCP_TRANSPORT=sse FASTMCP_LOG_LEVEL=INFO
   python src/intervals_mcp_server/server.py
   ```

   The startup log prints the full URLs (for example `http://127.0.0.1:8765/sse`). ChatGPT needs that public URL, so forward the port with a tool such as `ngrok http 8765` if you are not exposing the server directly.

2. In ChatGPT, open **Settings → Features → Custom MCP Connectors** and click **Add**. Fill in:

   - **Name**: `Intervals.icu`
   - **MCP Server URL**: `https://<your-public-host>/sse`
   - **Authentication**: leave as _No authentication_ unless you have protected your tunnel.

   You can reuse the same `ngrok http 8765` tunnel URL here; just ensure it forwards to the host/port you exported above.

3. Save the connector and open a new chat. ChatGPT will keep the SSE connection open and POST follow-up requests to the `/messages/` endpoint announced by the server. If you restart the MCP server or tunnel, rerun the SSE command and update the connector URL if it changes.

## Development and testing

Install development dependencies and run the test suite with:

```bash
uv sync --all-extras
pytest -v tests
```

### Running the server locally

To start the server manually (useful when developing or testing), run:

```bash
mcp run src/intervals_mcp_server/server.py
```

#### Enabling debug logging

To capture server logs for debugging, wrap the command in a shell and redirect stderr to a file.

**macOS/Linux** — modify your `claude_desktop_config.json` like this:

```json
{
  "mcpServers": {
    "Intervals.icu": {
      "command": "/bin/bash",
      "args": [
        "-c",
        "/Users/<USERNAME>/.local/bin/uv run --with 'mcp[cli]' --with-editable /path/to/intervals-mcp-server mcp run /path/to/intervals-mcp-server/src/intervals_mcp_server/server.py 2>> /path/to/intervals-mcp-server/mcp-server.log"
      ],
      "env": {
        "INTERVALS_API_BASE_URL": "https://intervals.icu/api/v1",
        "ATHLETE_ID": "<YOUR_ATHLETE_ID>",
        "API_KEY": "<YOUR_API_KEY>",
        "LOG_LEVEL": "INFO"
      }
    }
  }
}
```

Then tail the log file to see output in real-time:

```bash
tail -f /path/to/intervals-mcp-server/mcp-server.log
```

**Windows** — modify your `claude_desktop_config.json` like this:

```json
{
  "mcpServers": {
    "Intervals.icu": {
      "command": "powershell",
      "args": [
        "-Command",
        "C:\\Users\\<USERNAME>\\.local\\bin\\uv.exe run --with 'mcp[cli]' --with-editable C:\\path\\to\\intervals-mcp-server mcp run C:\\path\\to\\intervals-mcp-server\\src\\intervals_mcp_server\\server.py 2>> C:\\path\\to\\intervals-mcp-server\\mcp-server.log"
      ],
      "env": {
        "INTERVALS_API_BASE_URL": "https://intervals.icu/api/v1",
        "ATHLETE_ID": "<YOUR_ATHLETE_ID>",
        "API_KEY": "<YOUR_API_KEY>",
        "LOG_LEVEL": "INFO"
      }
    }
  }
}
```

Then monitor the log file in real-time using PowerShell:

```powershell
Get-Content C:\path\to\intervals-mcp-server\mcp-server.log -Wait
```

## License

The GNU General Public License v3.0

## Featured

### Glama.ai

<a href="https://glama.ai/mcp/servers/@mvilanova/intervals-mcp-server">
  <img width="380" height="200" src="https://glama.ai/mcp/servers/@mvilanova/intervals-mcp-server/badge" alt="Intervals.icu Server MCP server" />
</a>
