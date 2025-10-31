<#
Start the MCP server using the project's virtual environment.

Usage (PowerShell):
  .\.venv\Scripts\Activate.ps1
  .\scripts\run_local.ps1
#>

$python = "$PSScriptRoot\\..\\.venv\\Scripts\\python.exe"
if (-not (Test-Path $python)) {
    Write-Error "Python executable not found at $python. Activate your venv or adjust the path."
    exit 1
}

& $python -m src.intervals_mcp_server.server
