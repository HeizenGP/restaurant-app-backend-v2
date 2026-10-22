"""Translate expected M07 business failures at the HTTP boundary."""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from restaurant_app.modules.m07_fulfillment.domain.errors import (
    FulfillmentConflictError,
    FulfillmentError,
    FulfillmentNotFoundError,
    InvalidFulfillmentRequestError,
)


def install_fulfillment_error_handlers(application: FastAPI) -> None:
    @application.exception_handler(FulfillmentError)
    async def fulfillment_error_handler(request: Request, error: FulfillmentError) -> JSONResponse:
        del request
        if isinstance(error, FulfillmentNotFoundError):
            code = status.HTTP_404_NOT_FOUND
        elif isinstance(error, FulfillmentConflictError):
            code = status.HTTP_409_CONFLICT
        elif isinstance(error, InvalidFulfillmentRequestError):
            code = status.HTTP_422_UNPROCESSABLE_CONTENT
        else:  # pragma: no cover
            code = status.HTTP_400_BAD_REQUEST
        return JSONResponse(status_code=code, content={"detail": str(error)})
