"""Stable HTTP mapping for expected M03 errors."""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from restaurant_app.modules.m03_tables.domain.errors import (
    InvalidTableValueError,
    TableCodeConflictError,
    TableError,
    TableNotFoundError,
    TableOccupancyConflictError,
)


def install_table_error_handlers(application: FastAPI) -> None:
    @application.exception_handler(TableError)
    async def table_error_handler(request: Request, error: TableError) -> JSONResponse:
        del request
        if isinstance(error, TableNotFoundError):
            code = status.HTTP_404_NOT_FOUND
            detail = "Table not found"
        elif isinstance(error, TableCodeConflictError):
            code = status.HTTP_409_CONFLICT
            detail = "Table code already exists"
        elif isinstance(error, TableOccupancyConflictError):
            code = status.HTTP_409_CONFLICT
            detail = str(error) or "Cannot release table with unpaid active orders"
        elif isinstance(error, InvalidTableValueError):
            code = status.HTTP_422_UNPROCESSABLE_CONTENT
            detail = str(error)
        else:  # pragma: no cover - new TableError subclasses default safely
            code = status.HTTP_400_BAD_REQUEST
            detail = "Table request could not be processed"
        return JSONResponse(status_code=code, content={"detail": detail})
