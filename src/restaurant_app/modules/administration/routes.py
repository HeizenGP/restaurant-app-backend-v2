"""Administrative configuration and labor schedules."""

from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import AwareDatetime, BaseModel, Field, HttpUrl
from sqlalchemy import ForeignKey, select, text, update
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from restaurant_app.core.database import Base
from restaurant_app.core.dependencies import DatabaseSession
from restaurant_app.modules.administration.settings import RestaurantSetting, get_setting
from restaurant_app.modules.m01_access.adapters.inbound.http.dependencies import AdminPrincipal
from restaurant_app.modules.m01_access.adapters.outbound.models import UserModel, UserRoleModel

router = APIRouter(prefix="/administration", tags=["Administration"])

Section = Literal["restaurant", "payment-methods", "modalities"]


class RestaurantDetails(BaseModel):
    trade_name: str | None = Field(default=None, max_length=160)
    legal_name: str | None = Field(default=None, max_length=200)
    ruc: str | None = Field(default=None, pattern=r"^\d{11}$")
    address: str | None = Field(default=None, max_length=350)
    phone: str | None = Field(default=None, max_length=30)
    logo_url: HttpUrl | None = None
    opening_hours: str | None = Field(default=None, max_length=500)


class PaymentMethods(BaseModel):
    enabled: set[Literal["EFECTIVO", "YAPE", "PLIN", "TARJETA"]] = Field(min_length=1)


class Modalities(BaseModel):
    enabled: set[Literal["LOCAL", "PICKUP", "DELIVERY"]] = Field(min_length=1)
    conditions: str | None = Field(default=None, max_length=1000)


@router.get("/settings/{section}")
async def read_business_setting(section: Section, actor: AdminPrincipal, session: DatabaseSession) -> dict:
    return dict(await get_setting(session, section))


@router.get("/payment-methods")
async def read_payment_methods(session: DatabaseSession) -> PaymentMethods:
    return PaymentMethods.model_validate(await get_setting(session, "payment-methods"))


@router.put("/settings/restaurant")
async def put_restaurant(body: RestaurantDetails, actor: AdminPrincipal, session: DatabaseSession) -> RestaurantDetails:
    await _save_setting(session, "restaurant", body)
    return body


@router.put("/settings/payment-methods")
async def put_payment_methods(body: PaymentMethods, actor: AdminPrincipal, session: DatabaseSession) -> PaymentMethods:
    await _save_setting(session, "payment-methods", body)
    return body


@router.put("/settings/modalities")
async def put_modalities(body: Modalities, actor: AdminPrincipal, session: DatabaseSession) -> Modalities:
    await _save_setting(session, "modalities", body)
    return body


async def _save_setting(session: DatabaseSession, section: Section, body: BaseModel) -> None:
    configuration = body.model_dump(mode="json")
    if "enabled" in configuration:
        configuration["enabled"].sort()
    await session.execute(
        update(RestaurantSetting).where(RestaurantSetting.section == section).values(configuration=configuration)
    )


class WorkShift(Base):
    __tablename__ = "staff_work_shifts"
    __table_args__ = {"schema": "public"}

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("public.users.id", ondelete="RESTRICT"))
    starts_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))


class WorkShiftInput(BaseModel):
    user_id: UUID
    starts_at: AwareDatetime
    ends_at: AwareDatetime


class WorkShiftResponse(WorkShiftInput):
    id: UUID
    collaborator: str


@router.get("/work-shifts")
async def list_work_shifts(
    actor: AdminPrincipal, session: DatabaseSession,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    from_at: AwareDatetime | None = None,
    until_at: AwareDatetime | None = None,
) -> list[WorkShiftResponse]:
    statement = select(WorkShift, UserModel.display_name).join(UserModel, UserModel.id == WorkShift.user_id)
    if from_at is not None:
        statement = statement.where(WorkShift.ends_at > from_at)
    if until_at is not None:
        statement = statement.where(WorkShift.starts_at < until_at)
    rows = await session.execute(statement.order_by(WorkShift.starts_at.desc(), WorkShift.id).offset(offset).limit(limit))
    return [_work_shift(shift, name) for shift, name in rows]


@router.post("/work-shifts", status_code=201)
async def create_work_shift(body: WorkShiftInput, actor: AdminPrincipal, session: DatabaseSession) -> WorkShiftResponse:
    return await _save_work_shift(session, body)


@router.put("/work-shifts/{shift_id}")
async def update_work_shift(
    shift_id: UUID, body: WorkShiftInput, actor: AdminPrincipal, session: DatabaseSession
) -> WorkShiftResponse:
    return await _save_work_shift(session, body, shift_id)


async def _save_work_shift(
    session: DatabaseSession, body: WorkShiftInput, shift_id: UUID | None = None
) -> WorkShiftResponse:
    if not timedelta(0) < body.ends_at - body.starts_at <= timedelta(days=1):
        raise HTTPException(422, "La jornada debe durar más de cero y hasta 24 horas")
    await session.execute(text("SELECT pg_advisory_xact_lock(101, 1)"))
    name = await session.scalar(select(UserModel.display_name).where(
        UserModel.id == body.user_id, UserModel.is_active.is_(True),
        select(UserRoleModel.user_id).where(
            UserRoleModel.user_id == body.user_id, UserRoleModel.role_code != "CUSTOMER",
        ).exists(),
    ))
    if name is None:
        raise HTTPException(422, "Selecciona un colaborador activo")
    shift = await session.get(WorkShift, shift_id) if shift_id else WorkShift()
    if shift is None:
        raise HTTPException(404, "No se encontró el turno")
    overlap = select(WorkShift.id).where(
        WorkShift.user_id == body.user_id, WorkShift.starts_at < body.ends_at,
        WorkShift.ends_at > body.starts_at,
    )
    if shift_id:
        overlap = overlap.where(WorkShift.id != shift_id)
    if await session.scalar(overlap.limit(1)) is not None:
        raise HTTPException(409, "El colaborador ya tiene un turno que coincide con esta jornada")
    shift.user_id = body.user_id
    shift.starts_at = body.starts_at.astimezone(UTC)
    shift.ends_at = body.ends_at.astimezone(UTC)
    session.add(shift)
    await session.flush()
    return _work_shift(shift, name)


def _work_shift(shift: WorkShift, name: str) -> WorkShiftResponse:
    return WorkShiftResponse(
        id=shift.id, user_id=shift.user_id, starts_at=shift.starts_at,
        ends_at=shift.ends_at, collaborator=name,
    )
