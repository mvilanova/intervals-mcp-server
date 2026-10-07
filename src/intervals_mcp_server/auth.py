"""
Optional OAuth 2.1 resource server support for the HTTP transports.

When ``OAUTH_ISSUER`` and ``MCP_RESOURCE_URL`` are set, the server acts as an OAuth
protected resource (MCP authorization spec): it publishes RFC 9728 protected resource
metadata, answers unauthenticated requests with ``401`` and a ``WWW-Authenticate``
header, and validates bearer tokens as JWTs against the issuer's JWKS.

Tokens are validated locally (signature, ``iss``, ``aud``, ``exp``, ``typ``); the
authorization server (e.g. Keycloak, Authentik, Auth0) handles login and consent.
Without these variables the server behaves exactly as before, so stdio and local
HTTP setups are unaffected.
"""

import asyncio
import json
import logging
import os
import urllib.request
from collections.abc import Mapping
from typing import Any, Protocol

import jwt
from jwt import PyJWKClient
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from pydantic import AnyHttpUrl

logger = logging.getLogger("intervals_icu_mcp_server")

_ALGORITHMS = ["RS256", "RS384", "RS512", "PS256", "ES256", "ES384", "EdDSA"]


class SigningKeySource(Protocol):  # pylint: disable=too-few-public-methods
    """Anything that resolves the signing key for a JWT (PyJWKClient in production)."""

    def get_signing_key_from_jwt(self, token: str) -> Any:
        """Return an object with a ``key`` attribute for the token's ``kid``."""


def discover_jwks_uri(issuer: str, timeout: float = 10.0) -> str:
    """Read ``jwks_uri`` from the issuer's OpenID Connect discovery document."""
    url = f"{issuer.rstrip('/')}/.well-known/openid-configuration"
    with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310 - https issuer URL
        document = json.load(response)
    jwks_uri = document.get("jwks_uri")
    if not jwks_uri:
        raise ValueError(f"No jwks_uri in OpenID configuration at {url}")
    return str(jwks_uri)


class JWTTokenVerifier(TokenVerifier):
    """Validate bearer tokens as JWTs issued by an external authorization server."""

    def __init__(
        self,
        issuer: str,
        audience: str,
        allowed_users: list[str] | None = None,
        jwks_uri: str | None = None,
        key_source: SigningKeySource | None = None,
    ):
        self.issuer = issuer.rstrip("/")
        self.audience = audience
        self.allowed_users = set(allowed_users or [])
        self._jwks_uri = jwks_uri
        self._key_source = key_source

    def _signing_key(self, token: str) -> Any:
        if self._key_source is None:
            jwks_uri = self._jwks_uri or discover_jwks_uri(self.issuer)
            self._key_source = PyJWKClient(jwks_uri, cache_keys=True, lifespan=3600)
        return self._key_source.get_signing_key_from_jwt(token).key

    def decode(self, token: str) -> dict[str, Any] | None:
        """Return the validated claims, or ``None`` if the token must be rejected."""
        try:
            key = self._signing_key(token)
            claims: dict[str, Any] = jwt.decode(
                token,
                key,
                algorithms=_ALGORITHMS,
                audience=self.audience,
                issuer=self.issuer,
                options={"require": ["exp", "iss", "aud", "sub"]},
                leeway=30,
            )
        except (jwt.PyJWTError, OSError, ValueError) as exc:
            logger.info("Rejected bearer token: %s", exc)
            return None

        # Only access tokens; Keycloak also signs ID and refresh tokens with the same key.
        token_type = claims.get("typ")
        if token_type is not None and str(token_type).lower() not in ("bearer", "at+jwt"):
            logger.info("Rejected bearer token: unexpected typ %r", token_type)
            return None

        if self.allowed_users and claims.get("preferred_username") not in self.allowed_users:
            logger.info("Rejected bearer token: user %r not allowed", claims.get("preferred_username"))
            return None

        return claims

    async def verify_token(self, token: str) -> AccessToken | None:
        # JWKS discovery/fetching is blocking I/O, keep it off the event loop.
        claims = await asyncio.to_thread(self.decode, token)
        if claims is None:
            return None
        return AccessToken(
            token=token,
            client_id=str(claims.get("azp") or claims.get("client_id") or ""),
            scopes=str(claims.get("scope", "")).split(),
            expires_at=claims.get("exp"),
            resource=self.audience,
        )


def auth_settings_from_env(environ: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Build FastMCP ``auth``/``token_verifier`` keyword arguments from the environment.

    Variables:
        OAUTH_ISSUER: Issuer URL of the authorization server
            (e.g. ``https://auth.example.com/realms/mcp``).
        MCP_RESOURCE_URL: Public URL of this MCP endpoint (e.g. ``https://mcp.example.com/mcp``).
            Published as the protected resource and required in the token's ``aud`` claim.
        MCP_ALLOWED_USERS: Optional comma-separated ``preferred_username`` allowlist.
        OAUTH_JWKS_URL: Optional JWKS URL; discovered from the issuer when unset.
        OAUTH_SCOPES: Optional space- or comma-separated scopes. Published as ``scopes_supported``
            in the protected resource metadata (clients request exactly these instead of every
            scope the authorization server advertises) and required in every token.

    Returns an empty dict when OAuth is not configured.

    Raises:
        ValueError: If only one of OAUTH_ISSUER and MCP_RESOURCE_URL is set, so a
            half-configured server never starts without authentication.
    """
    env = os.environ if environ is None else environ
    issuer = env.get("OAUTH_ISSUER", "").strip()
    resource = env.get("MCP_RESOURCE_URL", "").strip()

    if not issuer and not resource:
        return {}
    if not issuer or not resource:
        raise ValueError("OAUTH_ISSUER and MCP_RESOURCE_URL must be set together to enable OAuth")

    allowed_users = [u.strip() for u in env.get("MCP_ALLOWED_USERS", "").split(",") if u.strip()]
    jwks_uri = env.get("OAUTH_JWKS_URL", "").strip() or None
    scopes = env.get("OAUTH_SCOPES", "").replace(",", " ").split()

    auth_kwargs: dict[str, Any] = {}
    if scopes:
        auth_kwargs["required_scopes"] = scopes
    # Newer SDK versions can additionally match AccessToken.resource against the resource URL.
    if "validate_token_resource" in AuthSettings.model_fields:
        auth_kwargs["validate_token_resource"] = True

    return {
        "token_verifier": JWTTokenVerifier(
            issuer, resource, allowed_users=allowed_users, jwks_uri=jwks_uri
        ),
        "auth": AuthSettings(
            issuer_url=AnyHttpUrl(issuer),
            resource_server_url=AnyHttpUrl(resource),
            **auth_kwargs,
        ),
    }
