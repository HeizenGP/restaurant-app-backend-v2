"""SQLAlchemy Async persistence adapters for M01."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from restaurant_app.modules.m01_access.adapters.outbound.models import (
    AuthSessionModel,
    UserModel,
    UserRoleModel,
)
from restaurant_app.modules.m01_access.domain.entities import (
    AuthSession,
    RoleCode,
    SessionKind,
    User,
)
from restaurant_app.modules.m01_access.domain.errors import (
    EmailAlreadyRegisteredError,
    RoleAlreadyAssignedError,
    UserNotFoundError,
)


class SqlAlchemyUserRepository:
    """Persist users and cumulative roles within the caller-owned transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_user(model: UserModel, roles: frozenset[RoleCode]) -> User:
        return User(
            id=model.id,
            display_name=model.display_name,
            email=model.email,
            is_active=model.is_active,
            roles=roles,
            created_at=model.created_at,
            phone=model.phone,
            avatar_url=model.avatar_url,
            saved_cards=tuple(model.saved_cards or []),
            saved_addresses=tuple(model.saved_addresses or []),
        )

    async def _find_rows(
        self,
        criterion: ColumnElement[bool],
    ) -> list[tuple[UserModel, str | None]]:
        statement = (
            select(UserModel, UserRoleModel.role_code)
            .outerjoin(UserRoleModel, UserRoleModel.user_id == UserModel.id)
            .where(criterion)
            .order_by(UserRoleModel.role_code)
        )
        return [
            (model, role_code)
            for model, role_code in (await self._session.execute(statement)).all()
        ]

    def _map_rows(self, rows: list[tuple[UserModel, str | None]]) -> User | None:
        if not rows:
            return None
        model = rows[0][0]
        roles = frozenset(RoleCode(code) for _, code in rows if code is not None)
        return self._to_user(model, roles)

    async def find_by_email_with_hash(self, email: str) -> tuple[User, str] | None:
        rows = await self._find_rows(func.lower(UserModel.email) == email.casefold())
        user = self._map_rows(rows)
        if user is None:
            return None
        return user, rows[0][0].password_hash

    async def find_by_id(self, user_id: UUID) -> User | None:
        return self._map_rows(await self._find_rows(UserModel.id == user_id))

    async def create(
        self,
        *,
        display_name: str,
        email: str,
        password_hash: str,
    ) -> User:
        model = UserModel(
            display_name=display_name,
            email=email,
            password_hash=password_hash,
        )
        self._session.add(model)
        try:
            await self._session.flush()
            self._session.add(UserRoleModel(user_id=model.id, role_code=RoleCode.CUSTOMER.value))
            await self._session.flush()
        except IntegrityError as error:
            raise EmailAlreadyRegisteredError(email) from error

        user = await self.find_by_id(model.id)
        if user is None:  # pragma: no cover - database returned an inserted row above
            raise RuntimeError("created user could not be reloaded")
        return user

    async def assign_role(self, user_id: UUID, role_code: RoleCode) -> User:
        self._session.add(UserRoleModel(user_id=user_id, role_code=role_code.value))
        try:
            await self._session.flush()
        except IntegrityError as error:
            raise RoleAlreadyAssignedError(str(user_id), role_code.value) from error

        user = await self.find_by_id(user_id)
        if user is None:  # pragma: no cover - caller verifies existence first
            raise RuntimeError("role target disappeared")
        return user

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
        values: dict[str, object] = {}
        if display_name is not None:
            values["display_name"] = display_name
        if phone is not None:
            values["phone"] = phone
        if avatar_url is not None:
            values["avatar_url"] = avatar_url
        if saved_cards is not None:
            values["saved_cards"] = saved_cards
        if saved_addresses is not None:
            values["saved_addresses"] = saved_addresses

        if values:
            await self._session.execute(
                update(UserModel).where(UserModel.id == user_id).values(**values)
            )
            await self._session.flush()

        user = await self.find_by_id(user_id)
        if user is None:
            raise UserNotFoundError(str(user_id))
        return user


class SqlAlchemySessionRepository:
    """Persist revocable USER/GUEST sessions and one-time refresh digests."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_session(model: AuthSessionModel) -> AuthSession:
        return AuthSession(
            id=model.id,
            kind=SessionKind(model.kind),
            user_id=model.user_id,
            renewal_token_hash=model.renewal_token_hash,
            created_at=model.created_at,
            expires_at=model.expires_at,
            revoked_at=model.revoked_at,
        )

    async def create_user_session(
        self,
        *,
        session_id: UUID,
        user_id: UUID,
        renewal_token_hash: str,
        created_at: datetime,
        expires_at: datetime,
    ) -> AuthSession:
        model = AuthSessionModel(
            id=session_id,
            kind=SessionKind.USER.value,
            user_id=user_id,
            renewal_token_hash=renewal_token_hash,
            created_at=created_at,
            expires_at=expires_at,
        )
        self._session.add(model)
        await self._session.flush()
        return self._to_session(model)

    async def create_guest_session(
        self,
        *,
        session_id: UUID,
        created_at: datetime,
        expires_at: datetime,
    ) -> AuthSession:
        model = AuthSessionModel(
            id=session_id,
            kind=SessionKind.GUEST.value,
            user_id=None,
            renewal_token_hash=None,
            created_at=created_at,
            expires_at=expires_at,
        )
        self._session.add(model)
        await self._session.flush()
        return self._to_session(model)

    async def find_by_id(self, session_id: UUID) -> AuthSession | None:
        model = await self._session.get(AuthSessionModel, session_id)
        return None if model is None else self._to_session(model)

    async def rotate_renewal_token(
        self,
        *,
        session_id: UUID,
        expected_hash: str,
        replacement_hash: str,
    ) -> bool:
        statement = (
            update(AuthSessionModel)
            .where(
                AuthSessionModel.id == session_id,
                AuthSessionModel.renewal_token_hash == expected_hash,
                AuthSessionModel.revoked_at.is_(None),
            )
            .values(renewal_token_hash=replacement_hash)
            .returning(AuthSessionModel.id)
        )
        return (await self._session.execute(statement)).scalar_one_or_none() is not None

    async def revoke(self, session_id: UUID, *, revoked_at: datetime) -> bool:
        statement = (
            update(AuthSessionModel)
            .where(AuthSessionModel.id == session_id, AuthSessionModel.revoked_at.is_(None))
            .values(revoked_at=revoked_at)
            .returning(AuthSessionModel.id)
        )
        return (await self._session.execute(statement)).scalar_one_or_none() is not None
