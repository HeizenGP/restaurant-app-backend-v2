"""Google OpenID Connect token verification adapter."""

import asyncio
from typing import Any

from google.auth.exceptions import GoogleAuthError
from google.auth.transport import requests
from google.oauth2 import id_token

from restaurant_app.modules.m01_access.application.ports.external_identity import GoogleIdentity
from restaurant_app.modules.m01_access.domain.errors import ExternalAuthenticationError


class GoogleIdTokenVerifier:
    """Validate a Google ID token for the configured backend audience."""

    def __init__(self, *, client_id: str) -> None:
        self._client_id = client_id

    async def verify(self, raw_token: str) -> GoogleIdentity:
        try:
            claims = await asyncio.to_thread(
                id_token.verify_oauth2_token,
                raw_token,
                requests.Request(),
                self._client_id,
            )
        except (GoogleAuthError, ValueError, OSError) as error:
            raise ExternalAuthenticationError from error
        return self._map_claims(claims)

    @staticmethod
    def _map_claims(claims: dict[str, Any]) -> GoogleIdentity:
        subject = claims.get("sub")
        email = claims.get("email")
        verified = claims.get("email_verified")
        if not isinstance(subject, str) or not subject:
            raise ExternalAuthenticationError
        if not isinstance(email, str) or not email or verified is not True:
            raise ExternalAuthenticationError("Google did not provide a verified email")
        display_name = claims.get("name")
        if not isinstance(display_name, str) or not display_name.strip():
            display_name = email.split("@", maxsplit=1)[0]
        avatar_url = claims.get("picture")
        return GoogleIdentity(
            subject=subject,
            email=email.strip().casefold(),
            display_name=display_name.strip(),
            avatar_url=avatar_url if isinstance(avatar_url, str) else None,
        )
