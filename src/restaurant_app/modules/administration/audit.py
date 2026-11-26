"""Admin-only audit queries and minimal access-event writes."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import select

from restaurant_app.modules.administration.audit_store import AuditEvent
from restaurant_app.core.dependencies import DatabaseSession
from restaurant_app.modules.m01_access.adapters.inbound.http.dependencies import AdminPrincipal
from restaurant_app.modules.m01_access.adapters.outbound.models import UserModel

router = APIRouter(prefix="/audit", tags=["Audit"])


class AuditEventResponse(BaseModel):
    id: int
    recorded_at: datetime
    actor_id: UUID | None
    actor: str | None
    resource: str
    resource_id: str | None
    action: str
    outcome: str
    before: dict | None
    after: dict | None


@router.get("/{view}")
async def list_audit_events(
    view: Literal["activity", "access"], actor: AdminPrincipal, session: DatabaseSession,
    before_id: Annotated[int | None, Query(ge=1)] = None,
    resource: Annotated[str | None, Query(max_length=32)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> list[AuditEventResponse]:
    statement = select(AuditEvent, UserModel.display_name).outerjoin(UserModel, UserModel.id == AuditEvent.actor_id)
    statement = statement.where(AuditEvent.resource == "access" if view == "access" else AuditEvent.resource != "access")
    if before_id is not None:
        statement = statement.where(AuditEvent.id < before_id)
    if resource is not None:
        statement = statement.where(AuditEvent.resource == resource)
    rows = await session.execute(statement.order_by(AuditEvent.id.desc()).limit(limit))
    return [
        AuditEventResponse(
            id=entry.id, recorded_at=entry.recorded_at, actor_id=entry.actor_id, actor=name,
            resource=entry.resource, resource_id=entry.resource_id, action=entry.action,
            outcome=entry.outcome, before=entry.before, after=entry.after,
        )
        for entry, name in rows
    ]
