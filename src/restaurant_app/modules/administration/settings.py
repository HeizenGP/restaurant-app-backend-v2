"""Read operational configuration inside the calling transaction."""

from collections.abc import Mapping
from typing import Any

from sqlalchemy import String, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from restaurant_app.core.database import Base


class RestaurantSetting(Base):
    __tablename__ = "restaurant_settings"
    __table_args__ = {"schema": "public"}

    section: Mapped[str] = mapped_column(String(32), primary_key=True)
    configuration: Mapped[dict[str, Any]] = mapped_column(JSONB)


async def get_setting(
    session: AsyncSession, section: str, *, share_lock: bool = False
) -> Mapping[str, Any]:
    statement = select(RestaurantSetting.configuration).where(RestaurantSetting.section == section)
    if share_lock:
        statement = statement.with_for_update(read=True)
    return (await session.execute(statement)).scalar_one()


async def enabled_staff_payment_methods(session: AsyncSession) -> list[str]:
    data = await get_setting(session, "payment-methods", share_lock=True)
    return list(data["enabled"])
