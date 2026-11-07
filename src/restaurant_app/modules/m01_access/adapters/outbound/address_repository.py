"""SQLAlchemy Async persistence adapter for User Addresses."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from restaurant_app.modules.m01_access.adapters.outbound.models import (
    UserAddressModel,
    UserModel,
)
from restaurant_app.modules.m01_access.domain.entities import UserAddress
from restaurant_app.modules.m01_access.domain.errors import UserNotFoundError


class SqlAlchemyUserAddressRepository:
    """Manage customer delivery addresses in PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_entity(model: UserAddressModel) -> UserAddress:
        return UserAddress(
            id=model.id,
            user_id=model.user_id,
            label=model.label,
            address=model.address,
            department=model.department,
            reference=model.reference,
            recipient_phone=model.recipient_phone,
            latitude=model.latitude,
            longitude=model.longitude,
            is_default=model.is_default,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def list_by_user(self, user_id: UUID) -> list[UserAddress]:
        statement = (
            select(UserAddressModel)
            .where(UserAddressModel.user_id == user_id)
            .order_by(UserAddressModel.is_default.desc(), UserAddressModel.created_at.desc())
        )
        rows = (await self._session.execute(statement)).scalars().all()
        return [self._to_entity(row) for row in rows]

    async def find_by_id(self, address_id: UUID, user_id: UUID) -> UserAddress | None:
        statement = select(UserAddressModel).where(
            UserAddressModel.id == address_id,
            UserAddressModel.user_id == user_id,
        )
        row = (await self._session.execute(statement)).scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def create(
        self,
        *,
        user_id: UUID,
        label: str,
        address: str,
        latitude: Decimal,
        longitude: Decimal,
        department: str | None = None,
        reference: str | None = None,
        recipient_phone: str | None = None,
        is_default: bool = False,
    ) -> UserAddress:
        # Check if user exists
        user_exists = await self._session.execute(
            select(UserModel.id).where(UserModel.id == user_id)
        )
        if user_exists.scalar_one_or_none() is None:
            raise UserNotFoundError(str(user_id))

        # Check existing count
        existing = await self.list_by_user(user_id)
        first_address = len(existing) == 0
        should_be_default = is_default or first_address

        if should_be_default and existing:
            await self._session.execute(
                update(UserAddressModel)
                .where(UserAddressModel.user_id == user_id)
                .values(is_default=False)
            )

        now = datetime.now(UTC)
        model = UserAddressModel(
            user_id=user_id,
            label=label.strip(),
            address=address.strip(),
            department=department.strip() if department and department.strip() else None,
            reference=reference.strip() if reference and reference.strip() else None,
            recipient_phone=recipient_phone.strip()
            if recipient_phone and recipient_phone.strip()
            else None,
            latitude=latitude,
            longitude=longitude,
            is_default=should_be_default,
            created_at=now,
            updated_at=now,
        )
        self._session.add(model)
        await self._session.flush()
        await self._sync_user_saved_addresses(user_id)
        return self._to_entity(model)

    async def update(
        self,
        address_id: UUID,
        user_id: UUID,
        *,
        label: str | None = None,
        address: str | None = None,
        department: str | None = None,
        reference: str | None = None,
        recipient_phone: str | None = None,
        latitude: Decimal | None = None,
        longitude: Decimal | None = None,
        is_default: bool | None = None,
    ) -> UserAddress | None:
        target = await self.find_by_id(address_id, user_id)
        if target is None:
            return None

        if is_default is True:
            await self._session.execute(
                update(UserAddressModel)
                .where(UserAddressModel.user_id == user_id)
                .values(is_default=False)
            )

        values: dict[str, object] = {"updated_at": datetime.now(UTC)}
        if label is not None:
            values["label"] = label.strip()
        if address is not None:
            values["address"] = address.strip()
        if department is not None:
            values["department"] = department.strip() if department.strip() else None
        if reference is not None:
            values["reference"] = reference.strip() if reference.strip() else None
        if recipient_phone is not None:
            values["recipient_phone"] = recipient_phone.strip() if recipient_phone.strip() else None
        if latitude is not None:
            values["latitude"] = latitude
        if longitude is not None:
            values["longitude"] = longitude
        if is_default is not None:
            values["is_default"] = is_default

        await self._session.execute(
            update(UserAddressModel)
            .where(UserAddressModel.id == address_id, UserAddressModel.user_id == user_id)
            .values(**values)
        )
        await self._session.flush()
        await self._sync_user_saved_addresses(user_id)
        return await self.find_by_id(address_id, user_id)

    async def delete(self, address_id: UUID, user_id: UUID) -> bool:
        target = await self.find_by_id(address_id, user_id)
        if target is None:
            return False

        was_default = target.is_default
        await self._session.execute(
            delete(UserAddressModel).where(
                UserAddressModel.id == address_id,
                UserAddressModel.user_id == user_id,
            )
        )
        await self._session.flush()

        if was_default:
            # Promote most recent address to default
            remaining = await self.list_by_user(user_id)
            if remaining:
                await self._session.execute(
                    update(UserAddressModel)
                    .where(UserAddressModel.id == remaining[0].id)
                    .values(is_default=True)
                )
                await self._session.flush()

        await self._sync_user_saved_addresses(user_id)
        return True

    async def set_default(self, address_id: UUID, user_id: UUID) -> UserAddress | None:
        target = await self.find_by_id(address_id, user_id)
        if target is None:
            return None

        await self._session.execute(
            update(UserAddressModel)
            .where(UserAddressModel.user_id == user_id)
            .values(is_default=False)
        )
        await self._session.execute(
            update(UserAddressModel)
            .where(UserAddressModel.id == address_id, UserAddressModel.user_id == user_id)
            .values(is_default=True, updated_at=datetime.now(UTC))
        )
        await self._session.flush()
        await self._sync_user_saved_addresses(user_id)
        return await self.find_by_id(address_id, user_id)

    async def _sync_user_saved_addresses(self, user_id: UUID) -> None:
        addresses = await self.list_by_user(user_id)
        serialized = [
            {
                "id": str(addr.id),
                "label": addr.label,
                "address": addr.address,
                "department": addr.department,
                "reference": addr.reference,
                "recipient_phone": addr.recipient_phone,
                "latitude": float(addr.latitude),
                "longitude": float(addr.longitude),
                "is_default": addr.is_default,
            }
            for addr in addresses
        ]
        await self._session.execute(
            update(UserModel).where(UserModel.id == user_id).values(saved_addresses=serialized)
        )
        await self._session.flush()
