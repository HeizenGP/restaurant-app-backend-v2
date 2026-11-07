"""Safe HTTP error mapping for M01 and request validation."""

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from restaurant_app.modules.m01_access.domain.errors import (
    AccessError,
    AuthenticationProviderUnavailableError,
    AuthorizationError,
    EmailAlreadyRegisteredError,
    ExternalAuthenticationError,
    InvalidCredentialsError,
    InvalidPasswordResetTokenError,
    InvalidTokenError,
    RoleAlreadyAssignedError,
    SessionExpiredError,
    UserInactiveError,
    UserNotFoundError,
)


def _sanitized_validation_errors(error: RequestValidationError) -> list[dict[str, Any]]:
    sanitized: list[dict[str, Any]] = []
    for item in error.errors():
        safe_item = dict(item)
        safe_item.pop("input", None)
        context = safe_item.get("ctx")
        if isinstance(context, dict) and "error" in context:
            safe_item["ctx"] = {"error": str(context["error"])}
        sanitized.append(jsonable_encoder(safe_item))
    return sanitized


def install_access_error_handlers(application: FastAPI) -> None:
    """Install non-sensitive, stable error responses for this authentication boundary."""

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request,
        error: RequestValidationError,
    ) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"detail": _sanitized_validation_errors(error)},
        )

    @application.exception_handler(AccessError)
    async def access_error_handler(request: Request, error: AccessError) -> JSONResponse:
        del request
        headers: dict[str, str] | None = None
        if isinstance(error, EmailAlreadyRegisteredError):
            status_code = status.HTTP_409_CONFLICT
            detail = "Email already registered"
        elif isinstance(error, AuthenticationProviderUnavailableError):
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            detail = "Authentication provider is not configured"
        elif isinstance(error, ExternalAuthenticationError):
            status_code = status.HTTP_401_UNAUTHORIZED
            detail = "Google authentication could not be completed"
        elif isinstance(error, InvalidPasswordResetTokenError):
            status_code = status.HTTP_400_BAD_REQUEST
            detail = "Invalid or expired password reset token"
        elif isinstance(error, RoleAlreadyAssignedError):
            status_code = status.HTTP_409_CONFLICT
            detail = "Role already assigned"
        elif isinstance(error, UserNotFoundError):
            status_code = status.HTTP_404_NOT_FOUND
            detail = "User not found"
        elif isinstance(error, AuthorizationError):
            status_code = status.HTTP_403_FORBIDDEN
            detail = str(error)
        elif isinstance(
            error,
            (InvalidCredentialsError, UserInactiveError),
        ):
            status_code = status.HTTP_401_UNAUTHORIZED
            detail = "Invalid email or password"
            headers = {"WWW-Authenticate": "Bearer"}
        elif isinstance(error, (InvalidTokenError, SessionExpiredError)):
            status_code = status.HTTP_401_UNAUTHORIZED
            detail = "Invalid or expired authentication"
            headers = {"WWW-Authenticate": "Bearer"}
        else:  # pragma: no cover - future AccessError subclasses default safely
            status_code = status.HTTP_400_BAD_REQUEST
            detail = "Access request could not be processed"
        return JSONResponse(status_code=status_code, content={"detail": detail}, headers=headers)
