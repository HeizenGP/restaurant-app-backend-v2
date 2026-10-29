"""REST endpoints for the M01 access slice."""

from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

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
    UpdateProfileRequest,
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
    UpdateUserProfile,
)
from restaurant_app.modules.m01_access.domain.entities import SessionKind

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


@users_router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
)
async def get_current_user_profile(
    principal: CurrentPrincipal,
    session: DatabaseSession,
) -> UserResponse:
    if principal.kind is not SessionKind.USER or principal.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Guest sessions do not have a registered profile",
        )
    user = await SqlAlchemyUserRepository(session).find_by_id(principal.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return UserResponse.from_domain(user)


@users_router.patch(
    "/me/profile",
    response_model=UserResponse,
    summary="Update current user profile (photo, phone, addresses, cards)",
)
async def update_current_user_profile(
    payload: UpdateProfileRequest,
    principal: CurrentPrincipal,
    session: DatabaseSession,
) -> UserResponse:
    if principal.kind is not SessionKind.USER or principal.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Guest sessions cannot modify profile",
        )

    saved_cards_data = (
        [card.model_dump() for card in payload.saved_cards]
        if payload.saved_cards is not None
        else None
    )
    saved_addresses_data = (
        [addr.model_dump() for addr in payload.saved_addresses]
        if payload.saved_addresses is not None
        else None
    )

    user = await UpdateUserProfile(SqlAlchemyUserRepository(session))(
        principal.user_id,
        display_name=payload.display_name,
        phone=payload.phone,
        avatar_url=payload.avatar_url,
        saved_cards=saved_cards_data,
        saved_addresses=saved_addresses_data,
    )
    return UserResponse.from_domain(user)


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
