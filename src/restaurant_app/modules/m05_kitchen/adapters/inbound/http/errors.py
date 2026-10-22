"""Expected M05 errors at the HTTP boundary."""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from restaurant_app.modules.m05_kitchen.domain.errors import (
    KitchenError,
    KitchenTicketNotFound,
    KitchenTransitionConflict,
)


def install_kitchen_error_handlers(application: FastAPI) -> None:
    @application.exception_handler(KitchenError)
    async def kitchen_error_handler(request: Request, error: KitchenError) -> JSONResponse:
        del request
        if isinstance(error, KitchenTicketNotFound):
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND, content={"detail": "Ticket not found"}
            )
        if isinstance(error, KitchenTransitionConflict):
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT, content={"detail": str(error)}
            )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "Kitchen operation failed"},
        )
