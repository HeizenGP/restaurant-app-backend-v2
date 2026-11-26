"""Append-only audit event persistence."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, Identity, String, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from restaurant_app.core.database import Base


class AuditEvent(Base):
    __tablename__ = "admin_audit_events"
    __table_args__ = {"schema": "public"}

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    recorded_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("clock_timestamp()"))
    actor_id: Mapped[UUID | None]
    resource: Mapped[str] = mapped_column(String(32))
    resource_id: Mapped[str | None] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(32))
    outcome: Mapped[str] = mapped_column(String(12))
    before: Mapped[dict | None] = mapped_column(JSONB)
    after: Mapped[dict | None] = mapped_column(JSONB)


async def record_access(session: AsyncSession, *, action: str, actor_id: UUID | None, success: bool) -> None:
    session.add(AuditEvent(
        actor_id=actor_id, resource="access", action=action,
        outcome="SUCCESS" if success else "REJECTED",
    ))
    await session.flush()


