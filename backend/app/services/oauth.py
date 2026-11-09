"""Microsoft 365 (Outlook) OAuth 2.0 helpers.

Single-tenant Authorization Code + PKCE. Không phụ thuộc thư viện OAuth ngoài:
dùng httpx để gọi token/Graph và PyJWT để xác thực id_token.
"""

import base64
import hashlib
import logging
import secrets
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import quote, urlencode

import httpx
import jwt
from jwt import PyJWKClient

from app.core.config import settings

logger = logging.getLogger("app.oauth")

AUTHORITY = "https://login.microsoftonline.com"
SCOPES = "openid profile email User.Read"
GRAPH_ME_URL = (
    "https://graph.microsoft.com/v1.0/me"
    "?$select=displayName,mail,userPrincipalName,id"
)


class OAuthError(Exception):
    """Lỗi OAuth có mã ngắn để frontend hiển thị thông báo thân thiện."""

    def __init__(self, code: str, message: str = ""):
        super().__init__(message or code)
        self.code = code


@dataclass
class OAuthTransaction:
    state: str
    nonce: str
    code_verifier: str
    next_path: str | None


@dataclass
class MicrosoftProfile:
    provider_user_id: str
    email: str
    full_name: str


def new_transaction(next_path: str | None) -> OAuthTransaction:
    return OAuthTransaction(
        state=secrets.token_urlsafe(32),
        nonce=secrets.token_urlsafe(16),
        code_verifier=secrets.token_urlsafe(64),
        next_path=next_path,
    )


def code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def build_authorize_url(tx: OAuthTransaction) -> str:
    params = {
        "client_id": settings.microsoft_client_id,
        "response_type": "code",
        "redirect_uri": settings.microsoft_redirect_uri,
        "response_mode": "query",
        "scope": SCOPES,
        "state": tx.state,
        "nonce": tx.nonce,
        "code_challenge": code_challenge(tx.code_verifier),
        "code_challenge_method": "S256",
        "prompt": "select_account",
    }
    return (
        f"{AUTHORITY}/{settings.microsoft_tenant_id}/oauth2/v2.0/authorize?"
        f"{urlencode(params, quote_via=quote)}"
    )


async def exchange_code(code: str, code_verifier: str) -> dict:
    data = {
        "client_id": settings.microsoft_client_id,
        "client_secret": settings.microsoft_client_secret,
        "code": code,
        "redirect_uri": settings.microsoft_redirect_uri,
        "grant_type": "authorization_code",
        "code_verifier": code_verifier,
        "scope": SCOPES,
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                f"{AUTHORITY}/{settings.microsoft_tenant_id}/oauth2/v2.0/token",
                data=data,
            )
    except httpx.HTTPError as exc:
        logger.warning("microsoft token exchange network error: %s", exc)
        raise OAuthError("token_exchange_failed") from exc

    if response.status_code != 200:
        logger.warning(
            "microsoft token exchange failed status=%s body=%s",
            response.status_code,
            response.text[:500],
        )
        raise OAuthError("token_exchange_failed")
    return response.json()


@lru_cache(maxsize=1)
def _jwks_client() -> PyJWKClient:
    return PyJWKClient(
        f"{AUTHORITY}/{settings.microsoft_tenant_id}/discovery/v2.0/keys"
    )


def _is_guid(value: str) -> bool:
    parts = value.split("-")
    return len(parts) == 5 and all(
        len(part) in (8, 4, 4, 4, 12) and all(c in "0123456789abcdefABCDEF" for c in part)
        for part in parts
    )


def validate_id_token(id_token: str, nonce: str) -> dict:
    """Xác thực chữ ký + audience + issuer + nonce của id_token Microsoft."""
    try:
        signing_key = _jwks_client().get_signing_key_from_jwt(id_token)
        claims = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.microsoft_client_id,
            options={"verify_iss": False},
        )
    except Exception as exc:  # noqa: BLE001 — mọi lỗi xác thực đều là token_invalid
        logger.warning("microsoft id_token validation failed: %s", exc)
        raise OAuthError("token_invalid") from exc

    tenant_id = str(claims.get("tid") or "").strip()
    if not tenant_id:
        raise OAuthError("token_invalid")
    if claims.get("iss") != f"{AUTHORITY}/{tenant_id}/v2.0":
        logger.warning("microsoft id_token issuer mismatch: %s", claims.get("iss"))
        raise OAuthError("token_invalid")

    configured_tenant = settings.microsoft_tenant_id.strip()
    if _is_guid(configured_tenant) and tenant_id.lower() != configured_tenant.lower():
        logger.warning("microsoft id_token tenant mismatch: %s", tenant_id)
        raise OAuthError("token_invalid")

    if claims.get("nonce") != nonce:
        logger.warning("microsoft id_token nonce mismatch")
        raise OAuthError("token_invalid")
    return claims


async def fetch_graph_profile(access_token: str) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                GRAPH_ME_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
    except httpx.HTTPError as exc:
        logger.warning("microsoft graph profile network error: %s", exc)
        return None

    if response.status_code != 200:
        logger.warning(
            "microsoft graph profile failed status=%s body=%s",
            response.status_code,
            response.text[:300],
        )
        return None
    return response.json()


async def resolve_profile(claims: dict, access_token: str | None) -> MicrosoftProfile:
    email = (
        claims.get("email")
        or claims.get("preferred_username")
        or claims.get("upn")
        or ""
    ).strip().lower()
    full_name = (claims.get("name") or "").strip()
    provider_user_id = str(claims.get("oid") or claims.get("sub") or "").strip()

    if (not email or not full_name) and access_token:
        graph = await fetch_graph_profile(access_token)
        if graph:
            email = email or (
                graph.get("mail") or graph.get("userPrincipalName") or ""
            ).strip().lower()
            full_name = full_name or (graph.get("displayName") or "").strip()
            provider_user_id = provider_user_id or str(graph.get("id") or "").strip()

    if not provider_user_id:
        raise OAuthError("profile_invalid")
    if not email:
        raise OAuthError("email_missing")
    if not full_name:
        full_name = email.split("@")[0]

    allowed = settings.microsoft_allowed_domain_list
    if allowed:
        domain = email.rsplit("@", 1)[-1]
        if domain not in allowed:
            raise OAuthError("domain_not_allowed")

    return MicrosoftProfile(
        provider_user_id=provider_user_id,
        email=email,
        full_name=full_name[:150],
    )
