#!/usr/bin/env bash
set -e
cd /home/jochem/intervals-mcp-server
export MCP_TRANSPORT=http
export API_KEY=28zrr3v30oon1bt5bejcw2a0y
export ATHLETE_ID=i85629
exec /home/jochem/.local/bin/uv run --directory /home/jochem/intervals-mcp-server --with-editable . python src/intervals_mcp_server/server.py
