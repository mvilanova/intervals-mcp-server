"""Tests for the optional OAuth resource server support."""

import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from mcp.server.fastmcp import FastMCP
from starlette.testclient import TestClient

from intervals_mcp_server.auth import JWTTokenVerifier, auth_settings_from_env

ISSUER = "https://auth.example.com/realms/mcp"
RESOURCE = "https://mcp.example.com/mcp"

_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


class _StaticKeySource:  # pylint: disable=too-few-public-methods
    """Stands in for PyJWKClient: always returns the test public key."""

    def get_signing_key_from_jwt(self, token: str):  # noqa: ARG002 - protocol signature
        return SimpleNamespace(key=_KEY.public_key())


def _token(key=_KEY, **overrides) -> str:
    now = int(time.time())
    claims = {
        "iss": ISSUER,
        "aud": [RESOURCE, "account"],
        "sub": "user-1",
        "iat": now,
        "exp": now + 600,
        "typ": "Bearer",
        "azp": "claude",
        "scope": "profile offline_access",
        "preferred_username": "alice",
    }
    claims.update(overrides)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, key, algorithm="RS256")


def _verifier(**kwargs) -> JWTTokenVerifier:
    return JWTTokenVerifier(ISSUER, RESOURCE, key_source=_StaticKeySource(), **kwargs)


# --- configuration ---------------------------------------------------------------------


def test_no_oauth_variables_disables_auth():
    assert not auth_settings_from_env({})


@pytest.mark.parametrize(
    "env",
    [{"OAUTH_ISSUER": ISSUER}, {"MCP_RESOURCE_URL": RESOURCE}],
)
def test_half_configured_oauth_refuses_to_start(env):
    with pytest.raises(ValueError, match="must be set together"):
        auth_settings_from_env(env)


def test_oauth_variables_build_settings():
    settings = auth_settings_from_env(
        {"OAUTH_ISSUER": ISSUER, "MCP_RESOURCE_URL": RESOURCE, "MCP_ALLOWED_USERS": "alice, bob"}
    )
    verifier = settings["token_verifier"]
    assert isinstance(verifier, JWTTokenVerifier)
    assert verifier.audience == RESOURCE
    assert verifier.allowed_users == {"alice", "bob"}
    assert str(settings["auth"].resource_server_url) == RESOURCE


def test_scopes_are_parsed():
    settings = auth_settings_from_env(
        {"OAUTH_ISSUER": ISSUER, "MCP_RESOURCE_URL": RESOURCE, "OAUTH_SCOPES": "openid, profile offline_access"}
    )
    assert settings["auth"].required_scopes == ["openid", "profile", "offline_access"]


def test_no_scopes_by_default():
    settings = auth_settings_from_env({"OAUTH_ISSUER": ISSUER, "MCP_RESOURCE_URL": RESOURCE})
    assert settings["auth"].required_scopes is None


# --- token validation ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_valid_token_is_accepted():
    access = await _verifier().verify_token(_token())
    assert access is not None
    assert access.client_id == "claude"
    assert access.scopes == ["profile", "offline_access"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "token",
    [
        pytest.param(_token(aud="https://other.example.com/mcp"), id="wrong-audience"),
        pytest.param(_token(iss="https://evil.example.com/realms/mcp"), id="wrong-issuer"),
        pytest.param(_token(exp=int(time.time()) - 3600), id="expired"),
        pytest.param(_token(typ="Refresh"), id="refresh-token"),
        pytest.param(_token(typ="ID"), id="id-token"),
        pytest.param(_token(key=_OTHER_KEY), id="bad-signature"),
        pytest.param(_token(sub=None), id="missing-sub"),
        pytest.param("not-a-jwt", id="garbage"),
    ],
)
async def test_invalid_tokens_are_rejected(token):
    assert await _verifier().verify_token(token) is None


@pytest.mark.asyncio
async def test_user_allowlist():
    verifier = _verifier(allowed_users=["bob"])
    assert await verifier.verify_token(_token()) is None
    assert await verifier.verify_token(_token(preferred_username="bob")) is not None


# --- HTTP behaviour --------------------------------------------------------------------


@pytest.fixture(name="client")
def _client():
    settings = auth_settings_from_env({"OAUTH_ISSUER": ISSUER, "MCP_RESOURCE_URL": RESOURCE})
    settings["token_verifier"] = _verifier()
    server = FastMCP("test", **settings)
    # Newer SDKs enable DNS rebinding protection for the default localhost binding.
    with TestClient(server.streamable_http_app(), base_url="http://127.0.0.1:8000") as client:
        yield client


_INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "0"},
    },
}
_HEADERS = {"Accept": "application/json, text/event-stream"}


def test_request_without_token_gets_401_with_resource_metadata(client):
    response = client.post("/mcp", json=_INITIALIZE, headers=_HEADERS)
    assert response.status_code == 401
    challenge = response.headers["www-authenticate"]
    assert challenge.startswith("Bearer")
    assert (
        'resource_metadata="https://mcp.example.com/.well-known/oauth-protected-resource/mcp"'
        in challenge
    )


def test_request_with_wrong_audience_gets_401(client):
    headers = {**_HEADERS, "Authorization": f"Bearer {_token(aud='https://other.example.com/mcp')}"}
    assert client.post("/mcp", json=_INITIALIZE, headers=headers).status_code == 401


def test_request_with_valid_token_is_served(client):
    headers = {**_HEADERS, "Authorization": f"Bearer {_token()}"}
    response = client.post("/mcp", json=_INITIALIZE, headers=headers)
    assert response.status_code == 200


@pytest.fixture(name="scoped_client")
def _scoped_client():
    settings = auth_settings_from_env(
        {"OAUTH_ISSUER": ISSUER, "MCP_RESOURCE_URL": RESOURCE, "OAUTH_SCOPES": "profile offline_access"}
    )
    settings["token_verifier"] = _verifier()
    server = FastMCP("test", **settings)
    with TestClient(server.streamable_http_app(), base_url="http://127.0.0.1:8000") as client:
        yield client


def test_scopes_are_published_in_metadata(scoped_client):
    metadata = scoped_client.get("/.well-known/oauth-protected-resource/mcp").json()
    assert metadata["scopes_supported"] == ["profile", "offline_access"]


def test_token_missing_a_required_scope_is_refused(scoped_client):
    headers = {**_HEADERS, "Authorization": f"Bearer {_token(scope='profile')}"}
    assert scoped_client.post("/mcp", json=_INITIALIZE, headers=headers).status_code == 403
    headers = {**_HEADERS, "Authorization": f"Bearer {_token()}"}
    assert scoped_client.post("/mcp", json=_INITIALIZE, headers=headers).status_code == 200


def test_protected_resource_metadata(client):
    response = client.get("/.well-known/oauth-protected-resource/mcp")
    assert response.status_code == 200
    metadata = response.json()
    assert metadata["resource"] == RESOURCE
    assert metadata["authorization_servers"] == [ISSUER]
