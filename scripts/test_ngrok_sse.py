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
            resp = client.get(url)
    except Exception as exc:
        print(f"Request failed: {exc}")
        sys.exit(2)

    print(f"Status: {resp.status_code}")
    ct = resp.headers.get("content-type", "")
    print(f"Content-Type: {ct}")

    text = resp.text[:2000]
    if "text/event-stream" in ct.lower():
        print("Looks like an SSE stream (content-type header present).")
        print("First chunk of response:\n", text)
        sys.exit(0)

    # Heuristics: SSE responses start with 'event:' or 'data:' lines
    if text.strip().startswith("event:") or text.strip().startswith("data:"):
        print("Looks like SSE by content. First chunk:\n", text)
        sys.exit(0)

    # Otherwise, likely HTML (ngrok landing page)
    if "ngrok" in text.lower() or text.lower().strip().startswith("<!doctype html"):
        print("Response appears to be an ngrok landing page or HTML, not an SSE stream.")
        print(text)
        sys.exit(3)

    print("Unknown response type. Dumping snippet:\n", text)
    sys.exit(4)


if __name__ == "__main__":
    main()
