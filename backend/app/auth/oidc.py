import base64
import hashlib
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import HTTPException, status

from app.auth.session import Session
from app.config import Settings


class OidcClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def discovery(self) -> dict:
        url = f"{str(self.settings.oidc_issuer).rstrip('/')}/.well-known/openid-configuration"
        async with httpx.AsyncClient(timeout=self.settings.openmetadata_timeout_seconds) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()

    async def authorization_url(self, session: Session) -> str:
        metadata = await self.discovery()
        challenge = base64.urlsafe_b64encode(hashlib.sha256(session.code_verifier.encode()).digest()).decode().rstrip("=")
        query = {
            "response_type": "code",
            "client_id": self.settings.oidc_client_id,
            "redirect_uri": str(self.settings.oidc_redirect_uri),
            "scope": self.settings.oidc_scopes,
            "state": session.state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        # Google OIDC (and many standards-compliant providers) derives the ID-token
        # audience from client_id. Sending a generic `audience` request parameter
        # causes Google's `invalid_audience` error. Keep audience validation during
        # token verification; provider-specific requested audiences belong in a
        # dedicated provider extension when a deployment needs one.
        return f"{metadata['authorization_endpoint']}?{urlencode(query)}"

    async def exchange_code(self, code: str, session: Session) -> dict:
        metadata = await self.discovery()
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": str(self.settings.oidc_redirect_uri),
            "client_id": self.settings.oidc_client_id,
            "code_verifier": session.code_verifier,
        }
        if self.settings.oidc_client_secret:
            data["client_secret"] = self.settings.oidc_client_secret
        async with httpx.AsyncClient(timeout=self.settings.openmetadata_timeout_seconds) as client:
            response = await client.post(metadata["token_endpoint"], data=data)
            if response.is_error:
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, "OIDC code exchange failed")
            tokens = response.json()
        claims = await self.validate_id_token(tokens["id_token"], metadata)
        return claims

    async def validate_id_token(self, token: str, metadata: dict) -> dict:
        async with httpx.AsyncClient(timeout=self.settings.openmetadata_timeout_seconds) as client:
            jwks = (await client.get(metadata["jwks_uri"])).json()
        header = jwt.get_unverified_header(token)
        key = next((key for key in jwks["keys"] if key.get("kid") == header.get("kid")), None)
        if not key:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "OIDC signing key not found")
        try:
            return jwt.decode(
                token,
                jwt.algorithms.RSAAlgorithm.from_jwk(key),
                algorithms=["RS256", "RS384", "RS512"],
                audience=self.settings.oidc_audience or self.settings.oidc_client_id,
                issuer=str(self.settings.oidc_issuer).rstrip("/"),
                options={"require": ["exp", "iat", "sub"]},
            )
        except jwt.PyJWTError as exc:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "OIDC token validation failed") from exc
