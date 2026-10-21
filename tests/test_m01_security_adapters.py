"""Security-adapter and HTTP-contract tests for M01."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from restaurant_app.core.config import Settings
from restaurant_app.main import create_app
from restaurant_app.modules.m01_access.adapters.outbound.password_hasher import (
    Argon2PasswordHasher,
)
from restaurant_app.modules.m01_access.adapters.outbound.token_provider import JwtTokenProvider
from restaurant_app.modules.m01_access.domain.entities import RoleCode, SessionKind
from restaurant_app.modules.m01_access.domain.errors import InvalidTokenError

JWT_SECRET = "unit-test-jwt-secret-with-more-than-32-characters"


def make_provider(
    *,
    now: datetime | None = None,
    audience: str = "restaurant-app-v2-api",
) -> JwtTokenProvider:
    return JwtTokenProvider(
        secret=JWT_SECRET,
        issuer="restaurant-app-v2",
        audience=audience,
        access_ttl=timedelta(minutes=15),
        refresh_ttl=timedelta(days=7),
        now=(lambda: now) if now is not None else (lambda: datetime.now(UTC)),
    )


def test_argon2id_hashes_and_verifies_without_accepting_malformed_hash() -> None:
    hasher = Argon2PasswordHasher()

    encoded = hasher.hash("correct horse battery staple")

    assert encoded.startswith("$argon2id$")
    assert "correct horse battery staple" not in encoded
    assert hasher.verify("correct horse battery staple", encoded)
    assert not hasher.verify("wrong", encoded)
    assert not hasher.verify("anything", "not-an-argon-hash")


def test_jwt_round_trip_enforces_kind_roles_and_token_type() -> None:
    provider = make_provider()
    user_id = uuid4()
    session_id = uuid4()
    access = provider.create_access_token(
        user_id=user_id,
        session_id=session_id,
        roles=frozenset({RoleCode.ADMIN, RoleCode.CASHIER}),
        kind=SessionKind.USER,
    )
    refresh = provider.create_refresh_token(session_id=session_id)

    payload = provider.decode_access_token(access)

    assert payload.user_id == user_id
    assert payload.session_id == session_id
    assert payload.roles == {RoleCode.ADMIN, RoleCode.CASHIER}
    assert provider.decode_refresh_token(refresh) == session_id
    with pytest.raises(InvalidTokenError):
        provider.decode_access_token(refresh)
    with pytest.raises(InvalidTokenError):
        provider.decode_refresh_token(access)


def test_guest_access_token_has_no_user_or_roles() -> None:
    provider = make_provider()
    session_id = uuid4()

    payload = provider.decode_access_token(
        provider.create_access_token(
            user_id=None,
            session_id=session_id,
            roles=frozenset(),
            kind=SessionKind.GUEST,
        )
    )

    assert payload.user_id is None
    assert payload.roles == frozenset()
    assert payload.kind is SessionKind.GUEST


def test_jwt_rejects_expired_tampered_and_wrong_audience_tokens() -> None:
    expired_provider = make_provider(now=datetime.now(UTC) - timedelta(hours=1))
    session_id = uuid4()
    expired = expired_provider.create_access_token(
        user_id=uuid4(),
        session_id=session_id,
        roles=frozenset({RoleCode.CUSTOMER}),
        kind=SessionKind.USER,
    )

    with pytest.raises(InvalidTokenError):
        expired_provider.decode_access_token(expired)
    with pytest.raises(InvalidTokenError):
        make_provider(audience="different-audience").decode_access_token(
            make_provider().create_access_token(
                user_id=uuid4(),
                session_id=uuid4(),
                roles=frozenset({RoleCode.CUSTOMER}),
                kind=SessionKind.USER,
            )
        )

    valid = make_provider().create_refresh_token(session_id=session_id)
    with pytest.raises(InvalidTokenError):
        make_provider().decode_refresh_token(f"{valid}tampered")


def test_refresh_digest_matches_only_the_exact_token() -> None:
    provider = make_provider()
    token = provider.create_refresh_token(session_id=uuid4())
    digest = provider.hash_token(token)

    assert token not in digest
    assert provider.token_matches_hash(token, digest)
    assert not provider.token_matches_hash(f"{token}x", digest)


def test_settings_reject_short_or_placeholder_jwt_secrets_outside_local() -> None:
    with pytest.raises(ValidationError, match="at least 32"):
        Settings(_env_file=None, jwt_secret="short")

    with pytest.raises(ValidationError, match="replace the local JWT secret"):
        Settings(
            _env_file=None,
            environment="staging",
            postgres_password="staging-database-password",
        )


def test_openapi_exposes_only_m01_routes_and_bearer_security_where_required() -> None:
    application = create_app(
        Settings(
            _env_file=None,
            environment="test",
            postgres_db="restaurant_app_test",
            postgres_password="test",
            jwt_secret=JWT_SECRET,
        )
    )

    schema = application.openapi()

    expected = {
        "/api/v1/auth/register",
        "/api/v1/auth/login",
        "/api/v1/auth/guest",
        "/api/v1/auth/refresh",
        "/api/v1/auth/logout",
        "/api/v1/users/{user_id}/roles",
    }
    assert expected <= set(schema["paths"])
    assert schema["paths"]["/api/v1/auth/logout"]["post"]["security"] == [{"BearerAuth": []}]
    assert schema["paths"]["/api/v1/users/{user_id}/roles"]["post"]["security"] == [
        {"BearerAuth": []}
    ]


def test_validation_error_does_not_echo_password_input() -> None:
    application = create_app(
        Settings(
            _env_file=None,
            environment="test",
            postgres_db="restaurant_app_test",
            postgres_password="test",
            jwt_secret=JWT_SECRET,
        )
    )

    with TestClient(application) as client:
        response = client.post(
            "/api/v1/auth/register",
            json={
                "display_name": "Client",
                "email": "client@example.test",
                "password": "secret",
            },
        )

    assert response.status_code == 422
    assert "secret" not in response.text
    assert all("input" not in item for item in response.json()["detail"])
