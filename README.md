[![MseeP.ai Security Assessment Badge](https://mseep.net/pr/mvilanova-intervals-mcp-server-badge.png)](https://mseep.ai/app/mvilanova-intervals-mcp-server)

# Intervals.icu MCP Server

Model Context Protocol (MCP) server for connecting Claude with the Intervals.icu API. It provides tools for authentication and data retrieval for activities, events, and wellness data.

## Requirements

- Python 3.10 or higher
- [Model Context Protocol (MCP) Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- httpx
- python-dotenv

## Setup

### 1. Install uv (recommended)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Clone this repository

```bash
git clone https://github.com/mvilanova/intervals-mcp-server.git
cd intervals-mcp-server
```

### 3. Create and activate a virtual environment

```bash
# Create virtual environment
uv venv

# Activate virtual environment
# On macOS/Linux:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate
```

### 4. Install dependencies

```bash
uv pip install -e .
```

### 5. Set up environment variables

Make a copy of `.env.example` and name it `.env` by running the following command:

```bash
cp .env.example .env
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

## Usage

### 1. Configure Claude Desktop

To use this server with Claude Desktop, you need to add it to your Claude Desktop configuration.

1. Run the following from the `intervals_mcp_server` directory to configure Claude Desktop:

```bash
mcp install src/intervals_mcp_server/server.py --name "Intervals.icu MCP Server"
```

2. If you open your Claude Desktop App configuration file `claude_desktop_config.json`, it should look like this:

```json
{
  "mcpServers": {
    "Intervals.icu": {
      "command": "uv",
      "args": [
        "run",
        "--with",
        "mcp[cli]",
        "mcp",
        "run",
        "/path/to/intervals-mcp-server/src/intervals_mcp_server/server.py"
      ]
    }
  }
}
```

Where `/path/to/` is the path to the `intervals-mcp-server` code folder in your system.

If you observe the following error messages when you open Claude Desktop, include the full path to `uv` in the command key in the `claude_desktop_config.json` configuration file. You can get the full path by running `which uv` in the terminal.

```
2025-04-28T10:21:11.462Z [info] [Intervals.icu MCP Server] Initializing server...
2025-04-28T10:21:11.477Z [error] [Intervals.icu MCP Server] spawn uv ENOENT
2025-04-28T10:21:11.477Z [error] [Intervals.icu MCP Server] spawn uv ENOENT
2025-04-28T10:21:11.481Z [info] [Intervals.icu MCP Server] Server transport closed
2025-04-28T10:21:11.481Z [info] [Intervals.icu MCP Server] Client transport closed
```

3. Restart Claude Desktop.

### 2. Use the MCP server with Claude

Once the server is running and Claude Desktop is configured, you can use the following tools to ask questions about your past and future activities, events, and wellness data.

- `get_activities`: Retrieve a list of activities
- `get_activity_details`: Get detailed information for a specific activity
- `get_activity_intervals`: Get detailed interval data for a specific activity
- `get_wellness_data`: Fetch wellness data
- `get_events`: Retrieve upcoming events (workouts, races, etc.)
- `get_event_by_id`: Get detailed information for a specific event

## License

The GNU General Public License v3.0

## Featured

### Glama.ai

<a href="https://glama.ai/mcp/servers/@mvilanova/intervals-mcp-server">
  <img width="380" height="200" src="https://glama.ai/mcp/servers/@mvilanova/intervals-mcp-server/badge" alt="Intervals.icu Server MCP server" />
</a>
