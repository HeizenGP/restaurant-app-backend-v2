"""Strict HS256 JWT adapter for M01 access and refresh tokens."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from hmac import compare_digest
from typing import Any
from uuid import UUID, uuid4

import jwt

from restaurant_app.modules.m01_access.domain.entities import (
    RoleCode,
    SessionKind,
    TokenPayload,
)
from restaurant_app.modules.m01_access.domain.errors import InvalidTokenError


def _utc_now() -> datetime:
    return datetime.now(UTC)


class JwtTokenProvider:
    """Issue signed tokens and require their type, issuer, audience, and expiry."""

    _ALGORITHM = "HS256"

    def __init__(
        self,
        *,
        secret: str,
        issuer: str,
        audience: str,
        access_ttl: timedelta,
        refresh_ttl: timedelta,
        now: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._secret = secret
        self._issuer = issuer
        self._audience = audience
        self._access_ttl = access_ttl
        self._refresh_ttl = refresh_ttl
        self._now = now

    def _base_claims(self, *, subject: str, token_type: str, ttl: timedelta) -> dict[str, Any]:
        now = self._now()
        return {
            "sub": subject,
            "type": token_type,
            "iss": self._issuer,
            "aud": self._audience,
            "iat": now,
            "exp": now + ttl,
            "jti": str(uuid4()),
        }

    def create_access_token(
        self,
        *,
        user_id: UUID | None,
        session_id: UUID,
        roles: frozenset[RoleCode],
        kind: SessionKind,
    ) -> str:
        subject = str(user_id) if user_id is not None else f"guest:{session_id}"
        claims = self._base_claims(subject=subject, token_type="access", ttl=self._access_ttl)
        claims.update(
            {
                "sid": str(session_id),
                "kind": kind.value,
                "roles": sorted(role.value for role in roles),
            }
        )
        return jwt.encode(claims, self._secret, algorithm=self._ALGORITHM)

    def create_refresh_token(self, *, session_id: UUID) -> str:
        claims = self._base_claims(
            subject=str(session_id),
            token_type="refresh",
            ttl=self._refresh_ttl,
        )
        claims["sid"] = str(session_id)
        return jwt.encode(claims, self._secret, algorithm=self._ALGORITHM)

    def _decode(self, token: str, *, expected_type: str) -> dict[str, Any]:
        try:
            claims = jwt.decode(
                token,
                self._secret,
                algorithms=[self._ALGORITHM],
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["sub", "type", "iss", "aud", "iat", "exp", "jti", "sid"]},
            )
            if claims["type"] != expected_type:
                raise InvalidTokenError
            return claims
        except InvalidTokenError:
            raise
        except (jwt.PyJWTError, KeyError, TypeError, ValueError) as error:
            raise InvalidTokenError from error

    def decode_access_token(self, token: str) -> TokenPayload:
        try:
            claims = self._decode(token, expected_type="access")
            session_id = UUID(claims["sid"])
            kind = SessionKind(claims["kind"])
            roles = frozenset(RoleCode(value) for value in claims["roles"])
            if kind is SessionKind.GUEST:
                if claims["sub"] != f"guest:{session_id}" or roles:
                    raise InvalidTokenError
                user_id = None
            else:
                user_id = UUID(claims["sub"])
            return TokenPayload(
                user_id=user_id,
                session_id=session_id,
                roles=roles,
                kind=kind,
            )
        except InvalidTokenError:
            raise
        except (KeyError, TypeError, ValueError) as error:
            raise InvalidTokenError from error

    def decode_refresh_token(self, token: str) -> UUID:
        try:
            claims = self._decode(token, expected_type="refresh")
            session_id = UUID(claims["sid"])
            if claims["sub"] != str(session_id):
                raise InvalidTokenError
            return session_id
        except InvalidTokenError:
            raise
        except (KeyError, TypeError, ValueError) as error:
            raise InvalidTokenError from error

    def hash_token(self, token: str) -> str:
        return sha256(token.encode("utf-8")).hexdigest()

    def token_matches_hash(self, token: str, token_hash: str) -> bool:
        return compare_digest(self.hash_token(token), token_hash)
