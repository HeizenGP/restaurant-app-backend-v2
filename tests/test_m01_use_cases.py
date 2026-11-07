"""Unit tests for the framework-free M01 handlers and role policy."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from restaurant_app.modules.m01_access.application.ports.external_identity import GoogleIdentity
from restaurant_app.modules.m01_access.application.use_cases import (
    AssignUserRole,
    AuthenticateRequest,
    AuthorizeRoles,
    LoginUser,
    LoginWithGoogle,
    RefreshSession,
    RegisterUser,
    RegisterUserCommand,
    RequestPasswordReset,
    ResetPassword,
    RevokeSession,
    StartGuestSession,
    UpdateUserProfile,
)
from restaurant_app.modules.m01_access.domain.entities import (
    AuthSession,
    Principal,
    RoleCode,
    SessionKind,
    TokenPayload,
    User,
)
from restaurant_app.modules.m01_access.domain.errors import (
    AuthorizationError,
    EmailAlreadyRegisteredError,
    ExternalAuthenticationError,
    InvalidCredentialsError,
    InvalidPasswordResetTokenError,
    InvalidTokenError,
    RoleAlreadyAssignedError,
    SessionExpiredError,
    UserInactiveError,
)

NOW = datetime(2026, 10, 21, 18, 0, tzinfo=UTC)


def make_user(
    *,
    email: str = "client@example.test",
    roles: frozenset[RoleCode] = frozenset({RoleCode.CUSTOMER}),
    is_active: bool = True,
) -> User:
    return User(
        id=uuid4(),
        display_name="Client",
        email=email,
        is_active=is_active,
        roles=roles,
        created_at=NOW,
    )


class FakePasswordHasher:
    def __init__(self) -> None:
        self.dummy_verifications = 0

    def hash(self, password: str) -> str:
        return f"argon::{password}"

    def verify(self, password: str, hash_: str) -> bool:
        return hash_ == self.hash(password)

    def verify_dummy(self, password: str) -> None:
        del password
        self.dummy_verifications += 1


class FakeUserRepository:
    def __init__(self, entries: list[tuple[User, str]] | None = None) -> None:
        self._entries: dict[str, tuple[User, str | None]] = {
            user.email: (user, password_hash) for user, password_hash in entries or []
        }
        self._google_subjects: dict[str, str] = {}

    async def find_by_email_with_hash(self, email: str) -> tuple[User, str | None] | None:
        return self._entries.get(email)

    async def find_by_id(self, user_id: UUID) -> User | None:
        return next((user for user, _ in self._entries.values() if user.id == user_id), None)

    async def find_by_google_subject(self, subject: str) -> User | None:
        email = self._google_subjects.get(subject)
        return None if email is None else self._entries[email][0]

    async def create(
        self,
        *,
        display_name: str,
        email: str,
        password_hash: str,
    ) -> User:
        user = User(
            id=uuid4(),
            display_name=display_name,
            email=email,
            is_active=True,
            roles=frozenset({RoleCode.CUSTOMER}),
            created_at=NOW,
        )
        self._entries[email] = (user, password_hash)
        return user

    async def create_from_google(
        self,
        *,
        display_name: str,
        email: str,
        google_subject: str,
        avatar_url: str | None,
    ) -> User:
        if email in self._entries:
            raise EmailAlreadyRegisteredError(email)
        user = User(
            id=uuid4(),
            display_name=display_name,
            email=email,
            is_active=True,
            roles=frozenset({RoleCode.CUSTOMER}),
            created_at=NOW,
            avatar_url=avatar_url,
        )
        self._entries[email] = (user, None)
        self._google_subjects[google_subject] = email
        return user

    async def update_password(self, user_id: UUID, *, password_hash: str) -> None:
        user = await self.find_by_id(user_id)
        if user is None:
            raise AssertionError("test target must exist")
        self._entries[user.email] = (user, password_hash)

    async def assign_role(self, user_id: UUID, role_code: RoleCode) -> User:
        user = await self.find_by_id(user_id)
        if user is None:
            raise AssertionError("test target must exist")
        if role_code in user.roles:
            raise RoleAlreadyAssignedError(str(user_id), role_code.value)
        updated = replace(user, roles=user.roles | {role_code})
        self._entries[user.email] = (updated, self._entries[user.email][1])
        return updated

    async def update_profile(
        self,
        user_id: UUID,
        *,
        display_name: str | None = None,
        phone: str | None = None,
        avatar_url: str | None = None,
        saved_cards: list[dict] | None = None,
        saved_addresses: list[dict] | None = None,
    ) -> User:
        user = await self.find_by_id(user_id)
        if user is None:
            raise AssertionError("test target must exist")
        updated = replace(
            user,
            display_name=display_name if display_name is not None else user.display_name,
            phone=phone if phone is not None else user.phone,
            avatar_url=avatar_url if avatar_url is not None else user.avatar_url,
            saved_cards=tuple(saved_cards) if saved_cards is not None else user.saved_cards,
            saved_addresses=tuple(saved_addresses)
            if saved_addresses is not None
            else user.saved_addresses,
        )
        self._entries[user.email] = (updated, self._entries[user.email][1])
        return updated


class FakeSessionRepository:
    def __init__(self) -> None:
        self.sessions: dict[UUID, AuthSession] = {}

    async def create_user_session(
        self,
        *,
        session_id: UUID,
        user_id: UUID,
        renewal_token_hash: str,
        created_at: datetime,
        expires_at: datetime,
    ) -> AuthSession:
        session = AuthSession(
            id=session_id,
            kind=SessionKind.USER,
            user_id=user_id,
            renewal_token_hash=renewal_token_hash,
            created_at=created_at,
            expires_at=expires_at,
            revoked_at=None,
        )
        self.sessions[session.id] = session
        return session

    async def create_guest_session(
        self,
        *,
        session_id: UUID,
        created_at: datetime,
        expires_at: datetime,
    ) -> AuthSession:
        session = AuthSession(
            id=session_id,
            kind=SessionKind.GUEST,
            user_id=None,
            renewal_token_hash=None,
            created_at=created_at,
            expires_at=expires_at,
            revoked_at=None,
        )
        self.sessions[session.id] = session
        return session

    async def find_by_id(self, session_id: UUID) -> AuthSession | None:
        return self.sessions.get(session_id)

    async def rotate_renewal_token(
        self,
        *,
        session_id: UUID,
        expected_hash: str,
        replacement_hash: str,
    ) -> bool:
        session = self.sessions.get(session_id)
        if session is None or session.renewal_token_hash != expected_hash:
            return False
        self.sessions[session_id] = replace(session, renewal_token_hash=replacement_hash)
        return True

    async def revoke(self, session_id: UUID, *, revoked_at: datetime) -> bool:
        session = self.sessions.get(session_id)
        if session is None or session.revoked_at is not None:
            return False
        self.sessions[session_id] = replace(session, revoked_at=revoked_at)
        return True

    async def revoke_all_for_user(self, user_id: UUID, *, revoked_at: datetime) -> int:
        count = 0
        for session_id, session in list(self.sessions.items()):
            if session.user_id == user_id and session.revoked_at is None:
                self.sessions[session_id] = replace(session, revoked_at=revoked_at)
                count += 1
        return count


class FakeTokenProvider:
    def __init__(self) -> None:
        self._counter = 0
        self.access_payloads: dict[str, TokenPayload] = {}
        self.refresh_sessions: dict[str, UUID] = {}

    def create_access_token(
        self,
        *,
        user_id: UUID | None,
        session_id: UUID,
        roles: frozenset[RoleCode],
        kind: SessionKind,
    ) -> str:
        self._counter += 1
        token = f"access-{self._counter}"
        self.access_payloads[token] = TokenPayload(
            user_id=user_id,
            session_id=session_id,
            roles=roles,
            kind=kind,
        )
        return token

    def create_refresh_token(self, *, session_id: UUID) -> str:
        self._counter += 1
        token = f"refresh-{session_id}-{self._counter}"
        self.refresh_sessions[token] = session_id
        return token

    def decode_access_token(self, token: str) -> TokenPayload:
        try:
            return self.access_payloads[token]
        except KeyError as error:
            raise InvalidTokenError from error

    def decode_refresh_token(self, token: str) -> UUID:
        try:
            return self.refresh_sessions[token]
        except KeyError as error:
            raise InvalidTokenError from error

    def hash_token(self, token: str) -> str:
        return f"digest::{token}"

    def token_matches_hash(self, token: str, token_hash: str) -> bool:
        return self.hash_token(token) == token_hash


class FakeGoogleVerifier:
    async def verify(self, id_token: str) -> GoogleIdentity:
        assert id_token == "valid-google-token"
        return GoogleIdentity(
            subject="google-subject-123",
            email="google@example.test",
            display_name="Google Customer",
            avatar_url="https://example.test/avatar.png",
        )


class FakePasswordResetRepository:
    def __init__(self) -> None:
        self.user_id: UUID | None = None
        self.token_hash: str | None = None
        self.expires_at: datetime | None = None
        self.used = False

    async def replace_active_token(
        self,
        *,
        user_id: UUID,
        token_hash: str,
        created_at: datetime,
        expires_at: datetime,
    ) -> None:
        assert created_at == NOW
        self.user_id = user_id
        self.token_hash = token_hash
        self.expires_at = expires_at
        self.used = False

    async def consume(self, *, token_hash: str, now: datetime) -> UUID | None:
        if self.used or token_hash != self.token_hash or now >= (self.expires_at or NOW):
            return None
        self.used = True
        return self.user_id


class FakePasswordResetMessenger:
    def __init__(self) -> None:
        self.token: str | None = None

    async def send_password_reset(self, *, email: str, display_name: str, token: str) -> None:
        assert email == "client@example.test"
        assert display_name == "Client"
        self.token = token


async def test_register_normalizes_email_hashes_password_and_assigns_customer() -> None:
    users = FakeUserRepository()
    hasher = FakePasswordHasher()

    user = await RegisterUser(users, hasher)(
        RegisterUserCommand(
            display_name="  María  ",
            email="  MARIA@Example.Test ",
            password="safe-password",
        )
    )

    assert user.display_name == "María"
    assert user.email == "maria@example.test"
    assert user.roles == {RoleCode.CUSTOMER}
    stored = await users.find_by_email_with_hash(user.email)
    assert stored is not None and stored[1] == "argon::safe-password"


async def test_register_rejects_case_insensitive_duplicate() -> None:
    user = make_user(email="client@example.test")
    users = FakeUserRepository([(user, "argon::password")])

    with pytest.raises(EmailAlreadyRegisteredError):
        await RegisterUser(users, FakePasswordHasher())(
            RegisterUserCommand("Client", "CLIENT@example.test", "password")
        )


async def test_login_persists_digest_of_exact_refresh_token() -> None:
    user = make_user()
    users = FakeUserRepository([(user, "argon::correct")])
    sessions = FakeSessionRepository()
    tokens = FakeTokenProvider()

    result = await LoginUser(
        users,
        sessions,
        FakePasswordHasher(),
        tokens,
        refresh_ttl=timedelta(days=7),
        now=lambda: NOW,
    )(email="CLIENT@example.test", password="correct")

    assert result.user == user
    assert result.tokens.refresh_token is not None
    payload = tokens.decode_access_token(result.tokens.access_token)
    session = sessions.sessions[payload.session_id]
    assert session.renewal_token_hash == tokens.hash_token(result.tokens.refresh_token)
    assert session.renewal_token_hash != tokens.hash_token("pending")
    assert session.expires_at == NOW + timedelta(days=7)


async def test_login_rejects_unknown_and_wrong_password_with_same_error() -> None:
    user = make_user()
    hasher = FakePasswordHasher()
    login = LoginUser(
        FakeUserRepository([(user, "argon::correct")]),
        FakeSessionRepository(),
        hasher,
        FakeTokenProvider(),
        refresh_ttl=timedelta(days=7),
    )

    with pytest.raises(InvalidCredentialsError):
        await login(email="missing@example.test", password="wrong")
    with pytest.raises(InvalidCredentialsError):
        await login(email=user.email, password="wrong")

    assert hasher.dummy_verifications == 1


async def test_login_rejects_inactive_user() -> None:
    user = make_user(is_active=False)
    login = LoginUser(
        FakeUserRepository([(user, "argon::correct")]),
        FakeSessionRepository(),
        FakePasswordHasher(),
        FakeTokenProvider(),
        refresh_ttl=timedelta(days=7),
    )

    with pytest.raises(UserInactiveError):
        await login(email=user.email, password="correct")


async def test_google_login_registers_by_subject_and_issues_kairo_session() -> None:
    users = FakeUserRepository()
    sessions = FakeSessionRepository()
    tokens = FakeTokenProvider()

    result = await LoginWithGoogle(
        users,
        sessions,
        FakeGoogleVerifier(),
        tokens,
        refresh_ttl=timedelta(days=7),
        now=lambda: NOW,
    )("valid-google-token")

    assert result.user is not None
    assert result.user.email == "google@example.test"
    assert result.user.roles == {RoleCode.CUSTOMER}
    assert await users.find_by_google_subject("google-subject-123") == result.user
    assert result.tokens.refresh_token is not None


async def test_google_login_never_links_an_existing_account_by_email_alone() -> None:
    existing = make_user(email="google@example.test")
    login = LoginWithGoogle(
        FakeUserRepository([(existing, "argon::password")]),
        FakeSessionRepository(),
        FakeGoogleVerifier(),
        FakeTokenProvider(),
        refresh_ttl=timedelta(days=7),
    )

    with pytest.raises(ExternalAuthenticationError):
        await login("valid-google-token")


async def test_password_reset_uses_digest_once_and_revokes_existing_sessions() -> None:
    user = make_user()
    users = FakeUserRepository([(user, "argon::old-password")])
    sessions = FakeSessionRepository()
    await sessions.create_user_session(
        session_id=uuid4(),
        user_id=user.id,
        renewal_token_hash="old-refresh-digest",
        created_at=NOW,
        expires_at=NOW + timedelta(days=1),
    )
    resets = FakePasswordResetRepository()
    messenger = FakePasswordResetMessenger()
    await RequestPasswordReset(
        users,
        resets,
        messenger,
        token_ttl=timedelta(minutes=30),
        now=lambda: NOW,
        token_factory=lambda: "opaque-reset-token-with-enough-entropy",
    )(user.email)

    assert messenger.token == "opaque-reset-token-with-enough-entropy"
    assert resets.token_hash is not None
    assert messenger.token not in resets.token_hash

    await ResetPassword(
        users,
        sessions,
        resets,
        FakePasswordHasher(),
        now=lambda: NOW + timedelta(minutes=1),
    )(token=messenger.token, new_password="New-password-1")

    stored = await users.find_by_email_with_hash(user.email)
    assert stored is not None and stored[1] == "argon::New-password-1"
    assert all(session.revoked_at is not None for session in sessions.sessions.values())

    with pytest.raises(InvalidPasswordResetTokenError):
        await ResetPassword(
            users,
            sessions,
            resets,
            FakePasswordHasher(),
            now=lambda: NOW + timedelta(minutes=2),
        )(token=messenger.token, new_password="Another-password-2")


async def test_guest_session_has_no_user_role_or_refresh_token() -> None:
    sessions = FakeSessionRepository()
    tokens = FakeTokenProvider()

    result = await StartGuestSession(
        sessions,
        tokens,
        session_ttl=timedelta(hours=24),
        now=lambda: NOW,
    )()

    assert result.user is None
    assert result.tokens.refresh_token is None
    payload = tokens.decode_access_token(result.tokens.access_token)
    assert payload.kind is SessionKind.GUEST
    assert payload.user_id is None
    assert payload.roles == frozenset()
    assert sessions.sessions[payload.session_id].expires_at == NOW + timedelta(hours=24)


async def test_authenticate_request_reloads_current_roles_instead_of_trusting_claims() -> None:
    user = make_user(roles=frozenset({RoleCode.ADMIN, RoleCode.CASHIER}))
    users = FakeUserRepository([(user, "hash")])
    sessions = FakeSessionRepository()
    tokens = FakeTokenProvider()
    session_id = uuid4()
    await sessions.create_user_session(
        session_id=session_id,
        user_id=user.id,
        renewal_token_hash="digest",
        created_at=NOW,
        expires_at=NOW + timedelta(days=1),
    )
    token = tokens.create_access_token(
        user_id=user.id,
        session_id=session_id,
        roles=frozenset({RoleCode.CUSTOMER}),
        kind=SessionKind.USER,
    )

    principal = await AuthenticateRequest(users, sessions, tokens, now=lambda: NOW)(token)

    assert principal.roles == {RoleCode.ADMIN, RoleCode.CASHIER}


async def test_authenticate_request_rejects_revoked_or_expired_session() -> None:
    user = make_user()
    users = FakeUserRepository([(user, "hash")])
    sessions = FakeSessionRepository()
    tokens = FakeTokenProvider()
    session_id = uuid4()
    session = await sessions.create_user_session(
        session_id=session_id,
        user_id=user.id,
        renewal_token_hash="digest",
        created_at=NOW - timedelta(days=2),
        expires_at=NOW,
    )
    token = tokens.create_access_token(
        user_id=user.id,
        session_id=session.id,
        roles=user.roles,
        kind=SessionKind.USER,
    )

    with pytest.raises(SessionExpiredError):
        await AuthenticateRequest(users, sessions, tokens, now=lambda: NOW)(token)


async def test_refresh_rotates_digest_and_rejects_reuse() -> None:
    user = make_user()
    users = FakeUserRepository([(user, "hash")])
    sessions = FakeSessionRepository()
    tokens = FakeTokenProvider()
    session_id = uuid4()
    original = tokens.create_refresh_token(session_id=session_id)
    await sessions.create_user_session(
        session_id=session_id,
        user_id=user.id,
        renewal_token_hash=tokens.hash_token(original),
        created_at=NOW,
        expires_at=NOW + timedelta(days=1),
    )
    refresh = RefreshSession(users, sessions, tokens, now=lambda: NOW)

    result = await refresh(original)

    assert result.tokens.refresh_token not in {None, original}
    assert sessions.sessions[session_id].renewal_token_hash == tokens.hash_token(
        result.tokens.refresh_token
    )
    with pytest.raises(InvalidTokenError):
        await refresh(original)


async def test_revoke_session_marks_current_session_revoked() -> None:
    sessions = FakeSessionRepository()
    session_id = uuid4()
    await sessions.create_guest_session(
        session_id=session_id,
        created_at=NOW,
        expires_at=NOW + timedelta(hours=1),
    )
    principal = Principal(None, session_id, frozenset(), SessionKind.GUEST)

    await RevokeSession(sessions, now=lambda: NOW)(principal)

    assert sessions.sessions[session_id].revoked_at == NOW


def test_role_policy_supports_waiter_union_superadmin_and_guest_limits() -> None:
    waiter = Principal(uuid4(), uuid4(), frozenset({RoleCode.WAITER}), SessionKind.USER)
    combined = Principal(
        uuid4(),
        uuid4(),
        frozenset({RoleCode.ADMIN, RoleCode.CASHIER}),
        SessionKind.USER,
    )
    cashier = Principal(uuid4(), uuid4(), frozenset({RoleCode.CASHIER}), SessionKind.USER)
    super_admin = Principal(uuid4(), uuid4(), frozenset({RoleCode.SUPER_ADMIN}), SessionKind.USER)
    guest = Principal(None, uuid4(), frozenset(), SessionKind.GUEST)

    AuthorizeRoles(RoleCode.WAITER)(waiter)
    AuthorizeRoles(RoleCode.ADMIN)(combined)
    AuthorizeRoles(RoleCode.CASHIER)(combined)
    AuthorizeRoles(RoleCode.KITCHEN)(super_admin)
    with pytest.raises(AuthorizationError):
        AuthorizeRoles(RoleCode.WAITER, RoleCode.ADMIN)(cashier)
    with pytest.raises(AuthorizationError):
        AuthorizeRoles(RoleCode.CUSTOMER)(guest)


async def test_assign_role_checks_handler_authorization_and_accumulates_roles() -> None:
    target = make_user()
    users = FakeUserRepository([(target, "hash")])
    admin = Principal(uuid4(), uuid4(), frozenset({RoleCode.ADMIN}), SessionKind.USER)
    cashier = Principal(uuid4(), uuid4(), frozenset({RoleCode.CASHIER}), SessionKind.USER)

    updated = await AssignUserRole(users)(
        actor=admin,
        user_id=target.id,
        role=RoleCode.CASHIER,
    )

    assert updated.roles == {RoleCode.CUSTOMER, RoleCode.CASHIER}
    with pytest.raises(AuthorizationError):
        await AssignUserRole(users)(
            actor=cashier,
            user_id=target.id,
            role=RoleCode.WAITER,
        )
    with pytest.raises(AuthorizationError):
        await AssignUserRole(users)(
            actor=admin,
            user_id=target.id,
            role=RoleCode.SUPER_ADMIN,
        )


async def test_update_user_profile_persists_phone_avatar_cards_and_addresses() -> None:
    target = make_user()
    users = FakeUserRepository([(target, "hash")])

    updated = await UpdateUserProfile(users)(
        user_id=target.id,
        phone="902875868",
        avatar_url="https://images.unsplash.com/photo-1507003211169?w=300",
        saved_cards=[
            {
                "id": "card-1",
                "card_number_masked": "•••• •••• •••• 4242",
                "card_holder": "Heizen",
                "expiry": "12/28",
                "brand": "Visa",
            }
        ],
        saved_addresses=[
            {
                "id": "addr-1",
                "label": "Casa",
                "address": "Av. Las Begonias 123",
                "is_default": True,
            }
        ],
    )

    assert updated.phone == "902875868"
    assert updated.avatar_url == "https://images.unsplash.com/photo-1507003211169?w=300"
    assert len(updated.saved_cards) == 1
    assert updated.saved_cards[0]["brand"] == "Visa"
    assert len(updated.saved_addresses) == 1
    assert updated.saved_addresses[0]["label"] == "Casa"
