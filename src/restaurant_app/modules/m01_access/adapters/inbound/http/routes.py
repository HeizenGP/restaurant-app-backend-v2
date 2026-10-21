"""REST endpoints for the M01 access slice."""

from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Response, status

from restaurant_app.core.dependencies import AppSettings, DatabaseSession
from restaurant_app.modules.m01_access.adapters.inbound.http.dependencies import (
    AdminPrincipal,
    CurrentPrincipal,
    build_token_provider,
    get_password_hasher,
)
from restaurant_app.modules.m01_access.adapters.inbound.http.schemas import (
    AuthenticationResponse,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    RoleAssignmentRequest,
    UserResponse,
)
from restaurant_app.modules.m01_access.adapters.outbound import (
    SqlAlchemySessionRepository,
    SqlAlchemyUserRepository,
)
from restaurant_app.modules.m01_access.application.use_cases import (
    AssignUserRole,
    LoginUser,
    RefreshSession,
    RegisterUser,
    RegisterUserCommand,
    RevokeSession,
    StartGuestSession,
)

auth_router = APIRouter(prefix="/auth", tags=["M01 access"])
users_router = APIRouter(prefix="/users", tags=["M01 users"])
router = APIRouter()


@auth_router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a customer account",
)
async def register_user(payload: RegisterRequest, session: DatabaseSession) -> UserResponse:
    user = await RegisterUser(SqlAlchemyUserRepository(session), get_password_hasher())(
        RegisterUserCommand(
            display_name=payload.display_name,
            email=payload.email,
            password=payload.password.get_secret_value(),
        )
    )
    return UserResponse.from_domain(user)


@auth_router.post(
    "/login",
    response_model=AuthenticationResponse,
    summary="Authenticate a registered user",
)
async def login_user(
    payload: LoginRequest,
    session: DatabaseSession,
    settings: AppSettings,
) -> AuthenticationResponse:
    result = await LoginUser(
        SqlAlchemyUserRepository(session),
        SqlAlchemySessionRepository(session),
        get_password_hasher(),
        build_token_provider(settings),
        refresh_ttl=timedelta(days=settings.jwt_refresh_ttl_days),
    )(
        email=payload.email,
        password=payload.password.get_secret_value(),
    )
    return AuthenticationResponse.from_result(result)


@auth_router.post(
    "/guest",
    response_model=AuthenticationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a limited guest session",
)
async def start_guest_session(
    session: DatabaseSession,
    settings: AppSettings,
) -> AuthenticationResponse:
    result = await StartGuestSession(
        SqlAlchemySessionRepository(session),
        build_token_provider(settings),
        session_ttl=timedelta(hours=settings.guest_session_ttl_hours),
    )()
    return AuthenticationResponse.from_result(result)


@auth_router.post(
    "/refresh",
    response_model=AuthenticationResponse,
    summary="Rotate a refresh token",
)
async def refresh_session(
    payload: RefreshRequest,
    session: DatabaseSession,
    settings: AppSettings,
) -> AuthenticationResponse:
    result = await RefreshSession(
        SqlAlchemyUserRepository(session),
        SqlAlchemySessionRepository(session),
        build_token_provider(settings),
    )(payload.refresh_token.get_secret_value())
    return AuthenticationResponse.from_result(result)


@auth_router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke the current session",
)
async def revoke_session(
    principal: CurrentPrincipal,
    session: DatabaseSession,
) -> Response:
    await RevokeSession(SqlAlchemySessionRepository(session))(principal)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@users_router.post(
    "/{user_id}/roles",
    response_model=UserResponse,
    summary="Assign one cumulative role",
)
async def assign_user_role(
    user_id: UUID,
    payload: RoleAssignmentRequest,
    actor: AdminPrincipal,
    session: DatabaseSession,
) -> UserResponse:
    user = await AssignUserRole(SqlAlchemyUserRepository(session))(
        actor=actor,
        user_id=user_id,
        role=payload.role,
    )
    return UserResponse.from_domain(user)


router.include_router(auth_router)
router.include_router(users_router)
