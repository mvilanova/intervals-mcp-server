"""Check whether an ngrok URL is forwarding an SSE /sse/ endpoint.

Usage:
    python scripts/test_ngrok_sse.py https://<ngrok-id>.ngrok-free.dev

The script will request the /sse/ path and report whether the response
looks like a valid SSE stream (Content-Type text/event-stream) or an
HTML landing page.
"""
from __future__ import annotations

import sys
import argparse
import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("base_url", help="The ngrok base HTTPS URL (no trailing slash)")
    args = parser.parse_args()

    url = args.base_url.rstrip("/") + "/sse/"
    print(f"Probing {url}")

    try:
        with httpx.Client(follow_redirects=True, timeout=10.0) as client:
            with client.stream("GET", url) as resp:
                print(f"Status: {resp.status_code}")
                ct = resp.headers.get("content-type", "")
                print(f"Content-Type: {ct}")

                if resp.status_code != 200:
                    print(resp.text[:2000])
                    sys.exit(5)

                if "text/event-stream" not in ct.lower():
                    # Pull a small chunk anyway to give context.
                    chunk = resp.iter_text()
                    try:
                        first = next(chunk)
                    except StopIteration:
                        first = ""
                    if first.strip().startswith(("event:", "data:")):
                        print("Looks like SSE by content even though header is missing.\n", first[:2000])
                        sys.exit(0)
                    print("Unexpected content-type; first chunk:\n", first[:2000])
                    sys.exit(4)

                # Read only the first data chunk; SSE streams never end.
                chunk = resp.iter_text()
                try:
                    first = next(chunk)
                except StopIteration:
                    first = ""

                if first:
                    print("First SSE chunk:\n", first[:2000])
                else:
                    print("Connection opened but no data yet (this is fine for idle SSE streams).")
                sys.exit(0)
    except Exception as exc:
        print(f"Request failed: {exc}")
        sys.exit(2)


if __name__ == "__main__":
    main()
