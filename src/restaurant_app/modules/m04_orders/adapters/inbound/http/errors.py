"""Expected request errors at the M04 HTTP boundary."""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from restaurant_app.modules.m04_orders.domain.errors import (
    InvalidOrderError,
    OrderConflictError,
    OrderError,
    OrderNotFoundError,
    ProductUnavailableError,
)


def install_order_error_handlers(application: FastAPI) -> None:
    @application.exception_handler(OrderError)
    async def order_error_handler(request: Request, error: OrderError) -> JSONResponse:
        del request
        if isinstance(error, OrderNotFoundError):
            code = status.HTTP_404_NOT_FOUND
            detail = "Order not found"
        elif isinstance(error, (ProductUnavailableError, OrderConflictError)):
            code = status.HTTP_409_CONFLICT
            detail = str(error)
        elif isinstance(error, InvalidOrderError):
            code = status.HTTP_422_UNPROCESSABLE_CONTENT
            detail = str(error)
        else:  # pragma: no cover
            code = status.HTTP_400_BAD_REQUEST
            detail = "Order request could not be processed"
        return JSONResponse(status_code=code, content={"detail": detail})
