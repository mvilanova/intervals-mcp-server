"""
API client for Intervals.icu MCP Server.

This module handles all HTTP communication with the Intervals.icu API,
including request management, error handling, and client lifecycle.
"""

from json import JSONDecodeError
import json
import logging
import sys
from contextlib import asynccontextmanager
from http import HTTPStatus
from typing import Any

import httpx  # pylint: disable=import-error
from mcp.server.fastmcp import FastMCP  # pylint: disable=import-error

from intervals_mcp_server.config import get_config

logger = logging.getLogger("intervals_icu_mcp_server")

# Create a single AsyncClient instance for all requests (lazily initialized)
# This can be monkeypatched via server.httpx_client for testing
httpx_client: httpx.AsyncClient | None = None


async def _get_httpx_client() -> httpx.AsyncClient:
    """
    Lazily create or reuse the shared httpx AsyncClient.

    The client may be closed by downstream transports between tool invocations,
    so we recreate it when necessary.

    This function checks server.httpx_client first (if available) to support
    test monkeypatching via server.httpx_client.
    """
    global httpx_client  # pylint: disable=global-statement  # noqa: PLW0603 - we intentionally manage the shared client here

    # Check for monkeypatched client in server module first (for test compatibility)
    # This allows tests to monkeypatch server.httpx_client and have it work
    try:
        server_module = sys.modules.get("intervals_mcp_server.server")
        if server_module and hasattr(server_module, "httpx_client"):
            server_client = server_module.httpx_client
            if server_client is not None and not server_client.is_closed:
                return server_client
    except (AttributeError, ImportError):
        pass

    # Use this module's httpx_client
    if httpx_client is None or httpx_client.is_closed:
        httpx_client = httpx.AsyncClient()
    return httpx_client


@asynccontextmanager
async def setup_api_client(_app: FastMCP):
    """
    Context manager to ensure the shared httpx client is closed when the server stops.

    Args:
        _app (FastMCP): The MCP server application instance.
    """
    try:
        yield
    finally:
        # Close the module-level httpx_client
        if httpx_client and not httpx_client.is_closed:
            await httpx_client.aclose()

        # Also close server.httpx_client if it exists (for test compatibility)
        # This ensures monkeypatched clients in tests are properly closed
        try:
            server_module = sys.modules.get("intervals_mcp_server.server")
            if server_module and hasattr(server_module, "httpx_client"):
                server_client = getattr(server_module, "httpx_client", None)
                if server_client is not None and not server_client.is_closed:
                    await server_client.aclose()
        except (AttributeError, ImportError):
            pass


def _get_error_message(error_code: int, error_text: str) -> str:
    """Return a user-friendly error message for a given HTTP status code."""
    error_messages = {
        HTTPStatus.UNAUTHORIZED: f"{HTTPStatus.UNAUTHORIZED.value} {HTTPStatus.UNAUTHORIZED.phrase}: Please check your API key.",
        HTTPStatus.FORBIDDEN: f"{HTTPStatus.FORBIDDEN.value} {HTTPStatus.FORBIDDEN.phrase}: You may not have permission to access this resource.",
        HTTPStatus.NOT_FOUND: f"{HTTPStatus.NOT_FOUND.value} {HTTPStatus.NOT_FOUND.phrase}: The requested endpoint or ID doesn't exist.",
        HTTPStatus.UNPROCESSABLE_ENTITY: f"{HTTPStatus.UNPROCESSABLE_ENTITY.value} {HTTPStatus.UNPROCESSABLE_ENTITY.phrase}: The server couldn't process the request (invalid parameters or unsupported operation).",
        HTTPStatus.TOO_MANY_REQUESTS: f"{HTTPStatus.TOO_MANY_REQUESTS.value} {HTTPStatus.TOO_MANY_REQUESTS.phrase}: Too many requests in a short time period.",
        HTTPStatus.INTERNAL_SERVER_ERROR: f"{HTTPStatus.INTERNAL_SERVER_ERROR.value} {HTTPStatus.INTERNAL_SERVER_ERROR.phrase}: The Intervals.icu server encountered an internal error.",
        HTTPStatus.SERVICE_UNAVAILABLE: f"{HTTPStatus.SERVICE_UNAVAILABLE.value} {HTTPStatus.SERVICE_UNAVAILABLE.phrase}: The Intervals.icu server might be down or undergoing maintenance.",
    }
    try:
        status = HTTPStatus(error_code)
        return error_messages.get(status, error_text)
    except ValueError:
        return error_text


def _prepare_request_config(
    url: str,
    api_key: str | None,
    method: str,
) -> tuple[str, httpx.BasicAuth, dict[str, str], str | None]:
    """Prepare request configuration including headers, auth, and URL.

    Returns:
        Tuple of (full_url, auth, headers, error_message).
        error_message is None if configuration is valid.
    """
    config = get_config()
    headers = {"User-Agent": config.user_agent, "Accept": "application/json"}

    if method in ["POST", "PUT"]:
        headers["Content-Type"] = "application/json"

    # Use provided api_key or fall back to global API_KEY
    key_to_use = api_key if api_key is not None else config.api_key
    if not key_to_use:
        logger.error("No API key provided for request to: %s", url)
        return (
            "",
            httpx.BasicAuth("", ""),
            {},
            "API key is required. Set API_KEY env var or pass api_key",
        )

    auth = httpx.BasicAuth("API_KEY", key_to_use)
    full_url = f"{config.intervals_api_base_url}{url}"
    return full_url, auth, headers, None


def _parse_response(
    response: httpx.Response, full_url: str
) -> dict[str, Any] | list[dict[str, Any]]:
    """Parse HTTP response and return JSON data or error dict.

    Returns:
        Parsed JSON response or error dict.
    """
    try:
        response_data = response.json() if response.content else {}
    except JSONDecodeError:
        logger.error("Invalid JSON in response from: %s", full_url)
        return {"error": True, "message": "Invalid JSON in response"}
    response.raise_for_status()
    return response_data


async def make_intervals_request(
    url: str,
    api_key: str | None = None,
    params: dict[str, Any] | None = None,
    method: str = "GET",
    data: dict[str, Any] | None = None,
) -> dict[str, Any] | list[dict[str, Any]]:
    """
    Make a request to the Intervals.icu API with proper error handling.

    Args:
        url (str): The API endpoint path (e.g., '/athlete/{id}/activities').
        api_key (str | None): Optional API key to use for authentication. Defaults to the global API_KEY.
        params (dict[str, Any] | None): Optional query parameters for the request.
        method (str): HTTP method to use (GET, POST, etc.). Defaults to GET.
        data (dict[str, Any] | None): Optional data to send in the request body.

    Returns:
        dict[str, Any] | list[dict[str, Any]]: The parsed JSON response from the API, or an error dict.
    """
    # Prepare request configuration
    full_url, auth, headers, error_msg = _prepare_request_config(url, api_key, method)
    if error_msg:
        return {"error": True, "message": error_msg}

    async def _send_request(client: httpx.AsyncClient) -> httpx.Response:
        if method in {"POST", "PUT"} and data is not None:
            return await client.request(
                method=method,
                url=full_url,
                headers=headers,
                params=params,
                auth=auth,
                timeout=30.0,
                content=json.dumps(data),
            )
        return await client.request(
            method=method,
            url=full_url,
            headers=headers,
            params=params,
            auth=auth,
            timeout=30.0,
        )

    try:
        client = await _get_httpx_client()

        try:
            response = await _send_request(client)
        except RuntimeError as runtime_error:
            # httpx closes the client when the underlying connection is severed;
            # recreate the shared client lazily and retry once.
            if "client has been closed" not in str(runtime_error).lower():
                raise
            logger.warning("HTTPX client was closed; creating a new instance for retries.")
            global httpx_client  # pylint: disable=global-statement  # noqa: PLW0603 - we intentionally manage the shared client here
            httpx_client = None
            client = await _get_httpx_client()
            response = await _send_request(client)

        return _parse_response(response, full_url)
    except httpx.HTTPStatusError as e:
        return _handle_http_status_error(e)
    except httpx.RequestError as e:
        logger.error("Request error: %s", str(e))
        return {"error": True, "message": f"Request error: {str(e)}"}
    except httpx.HTTPError as e:
        logger.error("HTTP client error: %s", str(e))
        return {"error": True, "message": f"HTTP client error: {str(e)}"}


def _handle_http_status_error(e: httpx.HTTPStatusError) -> dict[str, Any]:
    """Handle HTTP status errors and return formatted error dict.

    Args:
        e: The HTTPStatusError exception.

    Returns:
        Error dictionary with status code and message.
    """
    error_code = e.response.status_code
    error_text = e.response.text
    logger.error("HTTP error: %s - %s", error_code, error_text)
    return {
        "error": True,
        "status_code": error_code,
        "message": _get_error_message(error_code, error_text),
    }
