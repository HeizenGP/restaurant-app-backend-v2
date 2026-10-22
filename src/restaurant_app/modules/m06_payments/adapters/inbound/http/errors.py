"""Expected M06 advance errors at the HTTP boundary."""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from restaurant_app.modules.m06_payments.domain.errors import (
    AdvanceConflictError,
    AdvanceError,
    AdvanceNotFoundError,
    InvalidAdvanceRequestError,
)


def install_advance_error_handlers(application: FastAPI) -> None:
    @application.exception_handler(AdvanceError)
    async def advance_error_handler(request: Request, error: AdvanceError) -> JSONResponse:
        del request
        if isinstance(error, AdvanceNotFoundError):
            code = status.HTTP_404_NOT_FOUND
            detail = "Order not found"
        elif isinstance(error, AdvanceConflictError):
            code = status.HTTP_409_CONFLICT
            detail = str(error)
        elif isinstance(error, InvalidAdvanceRequestError):
            code = status.HTTP_422_UNPROCESSABLE_CONTENT
            detail = str(error)
        else:  # pragma: no cover
            code = status.HTTP_400_BAD_REQUEST
            detail = "Advance could not be processed"
        return JSONResponse(status_code=code, content={"detail": detail})
