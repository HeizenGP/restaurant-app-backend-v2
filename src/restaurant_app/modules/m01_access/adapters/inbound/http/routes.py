"""REST endpoints for the M01 access slice."""

from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from restaurant_app.core.dependencies import AppSettings, DatabaseSession
from restaurant_app.modules.m01_access.adapters.inbound.http.dependencies import (
    AdminPrincipal,
    CurrentPrincipal,
    build_password_reset_messenger,
    build_token_provider,
    get_password_hasher,
)
from restaurant_app.modules.m01_access.adapters.inbound.http.schemas import (
    AddressResponse,
    AuthenticationResponse,
    CreateAddressRequest,
    GoogleLoginRequest,
    LoginRequest,
    MessageResponse,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    RefreshRequest,
    RegisterRequest,
    RoleAssignmentRequest,
    UpdateAddressRequest,
    UpdateProfileRequest,
    UserResponse,
)
from restaurant_app.modules.m01_access.adapters.outbound import (
    GoogleIdTokenVerifier,
    SqlAlchemyPasswordResetRepository,
    SqlAlchemySessionRepository,
    SqlAlchemyUserAddressRepository,
    SqlAlchemyUserRepository,
)
from restaurant_app.modules.m01_access.application.use_cases import (
    AssignUserRole,
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
from restaurant_app.modules.m01_access.domain.entities import SessionKind
from restaurant_app.modules.m01_access.domain.errors import (
    AuthenticationProviderUnavailableError,
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
    "/google",
    response_model=AuthenticationResponse,
    summary="Authenticate or register a customer with Google",
)
async def login_with_google(
    payload: GoogleLoginRequest,
    session: DatabaseSession,
    settings: AppSettings,
) -> AuthenticationResponse:
    if settings.google_oauth_client_id is None:
        raise AuthenticationProviderUnavailableError("Google")
    result = await LoginWithGoogle(
        SqlAlchemyUserRepository(session),
        SqlAlchemySessionRepository(session),
        GoogleIdTokenVerifier(client_id=settings.google_oauth_client_id),
        build_token_provider(settings),
        refresh_ttl=timedelta(days=settings.jwt_refresh_ttl_days),
    )(payload.id_token.get_secret_value())
    return AuthenticationResponse.from_result(result)


@auth_router.post(
    "/password-reset/request",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Request a password recovery message",
)
async def request_password_reset(
    payload: PasswordResetRequest,
    session: DatabaseSession,
    settings: AppSettings,
) -> MessageResponse:
    await RequestPasswordReset(
        SqlAlchemyUserRepository(session),
        SqlAlchemyPasswordResetRepository(session),
        build_password_reset_messenger(settings),
        token_ttl=timedelta(minutes=settings.password_reset_ttl_minutes),
    )(payload.email)
    return MessageResponse(
        message="If the account exists, KAIRO will send password reset instructions."
    )


@auth_router.post(
    "/password-reset/confirm",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Set a new password with a one-time recovery token",
)
async def reset_password(
    payload: PasswordResetConfirmRequest,
    session: DatabaseSession,
) -> Response:
    await ResetPassword(
        SqlAlchemyUserRepository(session),
        SqlAlchemySessionRepository(session),
        SqlAlchemyPasswordResetRepository(session),
        get_password_hasher(),
    )(
        token=payload.token.get_secret_value(),
        new_password=payload.new_password.get_secret_value(),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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


@users_router.get(
    "/me/addresses",
    response_model=list[AddressResponse],
    summary="List saved delivery addresses for current user",
)
async def list_user_addresses(
    principal: CurrentPrincipal,
    session: DatabaseSession,
) -> list[AddressResponse]:
    if principal.kind is not SessionKind.USER or principal.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Guest sessions do not have saved addresses",
        )
    repo = SqlAlchemyUserAddressRepository(session)
    entities = await repo.list_by_user(principal.user_id)
    return [
        AddressResponse(
            id=addr.id,
            user_id=addr.user_id,
            label=addr.label,
            address=addr.address,
            department=addr.department,
            reference=addr.reference,
            delivery_instructions=addr.delivery_instructions,
            recipient_phone=addr.recipient_phone,
            latitude=float(addr.latitude),
            longitude=float(addr.longitude),
            is_default=addr.is_default,
            created_at=addr.created_at,
            updated_at=addr.updated_at,
        )
        for addr in entities
    ]


@users_router.post(
    "/me/addresses",
    response_model=AddressResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new saved delivery address",
)
async def create_user_address(
    payload: CreateAddressRequest,
    principal: CurrentPrincipal,
    session: DatabaseSession,
) -> AddressResponse:
    if principal.kind is not SessionKind.USER or principal.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Guest sessions cannot save addresses",
        )
    repo = SqlAlchemyUserAddressRepository(session)
    entity = await repo.create(
        user_id=principal.user_id,
        label=payload.label,
        address=payload.address,
        latitude=payload.latitude,
        longitude=payload.longitude,
        department=payload.department,
        reference=payload.reference,
        delivery_instructions=payload.delivery_instructions,
        recipient_phone=payload.recipient_phone,
        is_default=payload.is_default,
    )
    return AddressResponse(
        id=entity.id,
        user_id=entity.user_id,
        label=entity.label,
        address=entity.address,
        department=entity.department,
        reference=entity.reference,
        delivery_instructions=entity.delivery_instructions,
        recipient_phone=entity.recipient_phone,
        latitude=float(entity.latitude),
        longitude=float(entity.longitude),
        is_default=entity.is_default,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


@users_router.put(
    "/me/addresses/{address_id}",
    response_model=AddressResponse,
    summary="Update an existing delivery address",
)
async def update_user_address(
    address_id: UUID,
    payload: UpdateAddressRequest,
    principal: CurrentPrincipal,
    session: DatabaseSession,
) -> AddressResponse:
    if principal.kind is not SessionKind.USER or principal.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Guest sessions cannot modify addresses",
        )
    repo = SqlAlchemyUserAddressRepository(session)
    entity = await repo.update(
        address_id=address_id,
        user_id=principal.user_id,
        label=payload.label,
        address=payload.address,
        department=payload.department,
        reference=payload.reference,
        delivery_instructions=payload.delivery_instructions,
        recipient_phone=payload.recipient_phone,
        latitude=payload.latitude,
        longitude=payload.longitude,
        is_default=payload.is_default,
    )
    if entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Address not found",
        )
    return AddressResponse(
        id=entity.id,
        user_id=entity.user_id,
        label=entity.label,
        address=entity.address,
        department=entity.department,
        reference=entity.reference,
        delivery_instructions=entity.delivery_instructions,
        recipient_phone=entity.recipient_phone,
        latitude=float(entity.latitude),
        longitude=float(entity.longitude),
        is_default=entity.is_default,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


@users_router.delete(
    "/me/addresses/{address_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a saved delivery address",
)
async def delete_user_address(
    address_id: UUID,
    principal: CurrentPrincipal,
    session: DatabaseSession,
) -> Response:
    if principal.kind is not SessionKind.USER or principal.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Guest sessions cannot delete addresses",
        )
    repo = SqlAlchemyUserAddressRepository(session)
    deleted = await repo.delete(address_id=address_id, user_id=principal.user_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Address not found",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@users_router.post(
    "/me/addresses/{address_id}/set-default",
    response_model=AddressResponse,
    summary="Mark an address as default delivery destination",
)
async def set_default_user_address(
    address_id: UUID,
    principal: CurrentPrincipal,
    session: DatabaseSession,
) -> AddressResponse:
    if principal.kind is not SessionKind.USER or principal.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Guest sessions cannot set default address",
        )
    repo = SqlAlchemyUserAddressRepository(session)
    entity = await repo.set_default(address_id=address_id, user_id=principal.user_id)
    if entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Address not found",
        )
    return AddressResponse(
        id=entity.id,
        user_id=entity.user_id,
        label=entity.label,
        address=entity.address,
        department=entity.department,
        reference=entity.reference,
        delivery_instructions=entity.delivery_instructions,
        recipient_phone=entity.recipient_phone,
        latitude=float(entity.latitude),
        longitude=float(entity.longitude),
        is_default=entity.is_default,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


router.include_router(auth_router)
router.include_router(users_router)
