"""Launch the MCP SSE server and an ngrok tunnel in one step.

Run this script from the repo root:

    python scripts/launch_stack.py

Options allow customizing the port, ngrok binary, or subdomain. The script
spawns both processes, forwards their output with simple prefixes, and
shuts everything down on Ctrl+C.
"""
from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from shutil import which
from typing import Iterable

try:
    from dotenv import dotenv_values
except ImportError as exc:  # pragma: no cover - runtime guard
    raise SystemExit(
        "python-dotenv is required. Activate the project virtualenv or install python-dotenv."
    ) from exc

REPO_ROOT = Path(__file__).resolve().parents[1]
VENV_BIN = REPO_ROOT / ".venv" / "Scripts"
DEFAULT_MCP = VENV_BIN / "mcp.exe"
DEFAULT_PYTHON = VENV_BIN / "python.exe"
DEFAULT_NGROK = which("ngrok") or str(Path.home() / "AppData" / "Local" / "ngrok" / "ngrok.exe")


def existing(path: Path | str | None) -> Path | None:
    if not path:
        return None
    p = Path(path)
    return p if p.exists() else None


def stream_output(label: str, stream: Iterable[str]) -> None:
    for line in stream:
        print(f"[{label}] {line.rstrip()}", flush=True)


def launch_process(
    name: str,
    args: list[str],
    cwd: Path,
    env: dict[str, str] | None = None,
) -> subprocess.Popen[str]:
    try:
        proc = subprocess.Popen(
            args,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            env=env,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"Failed to launch {name}: {exc}") from exc

    assert proc.stdout is not None
    thread = threading.Thread(target=stream_output, args=(name, proc.stdout), daemon=True)
    thread.start()
    return proc


def main() -> None:
    parser = argparse.ArgumentParser(description="Start MCP SSE server plus ngrok tunnel")
    parser.add_argument("--port", type=int, default=8000, help="Local port to tunnel (server listens on 8000)")
    parser.add_argument("--python", dest="python_path", help="Path to python.exe (defaults to .venv)")
    parser.add_argument("--mcp", dest="mcp_path", help="Path to mcp.exe (defaults to .venv)")
    parser.add_argument("--ngrok", dest="ngrok_path", help="Path to ngrok executable")
    parser.add_argument(
        "--hostname",
        help="Optional ngrok reserved domain (requires paid plan)",
    )
    parser.add_argument("--region", help="ngrok tunnel region code", default=None)
    parser.add_argument("--no-ngrok", action="store_true", help="Skip starting ngrok")
    args = parser.parse_args()

    python_exe = existing(args.python_path) or existing(DEFAULT_PYTHON)
    if python_exe is None:
        raise SystemExit("Could not locate python.exe in .venv; pass --python explicitly.")

    mcp_exe = existing(args.mcp_path) or existing(DEFAULT_MCP)
    if mcp_exe is None:
        raise SystemExit("Could not locate mcp.exe; ensure the venv is installed or pass --mcp.")

    ngrok_exe = None
    if not args.no_ngrok:
        ngrok_exe = existing(args.ngrok_path) or existing(DEFAULT_NGROK)
        if ngrok_exe is None:
            raise SystemExit("ngrok executable not found; install ngrok or pass --no-ngrok.")

    server_port = 8000

    if args.port != server_port:
        print(
            "Warning: current mcp CLI always listens on port 8000; using that for the server and tunnelling"
            f" port {server_port} instead."
        )

    server_args = [
        str(mcp_exe),
        "run",
        "-t",
        "sse",
        "src/intervals_mcp_server/sse_server.py:mcp",
    ]

    # Apply .env values to child processes so they see the correct credentials.
    env = os.environ.copy()
    env_update = dotenv_values(REPO_ROOT / ".env")
    env.update({k: v for k, v in env_update.items() if v is not None})

    print("Starting MCP server...")
    server_proc = launch_process("mcp", server_args, cwd=REPO_ROOT, env=env)

    tunnel_proc = None
    if ngrok_exe is not None:
        tunnel_args = [str(ngrok_exe), "http", str(server_port)]
        if args.hostname:
            tunnel_args.extend(["--hostname", args.hostname])
        if args.region:
            tunnel_args.extend(["--region", args.region])
        print("Starting ngrok tunnel...")
    tunnel_proc = launch_process("ngrok", tunnel_args, cwd=REPO_ROOT, env=env)

    print("Processes running. Press Ctrl+C to stop.")
    try:
        while True:
            if server_proc.poll() is not None:
                raise RuntimeError("MCP server exited unexpectedly.")
            if tunnel_proc and tunnel_proc.poll() is not None:
                raise RuntimeError("ngrok exited unexpectedly.")
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        for proc, label in ((server_proc, "mcp"), (tunnel_proc, "ngrok")):
            if proc and proc.poll() is None:
                try:
                    proc.send_signal(signal.CTRL_BREAK_EVENT)
                except Exception:
                    proc.terminate()
        for proc in (server_proc, tunnel_proc):
            if proc:
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as err:
        print(err, file=sys.stderr)
        raise SystemExit(1)
