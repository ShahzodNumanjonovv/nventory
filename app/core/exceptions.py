import logging

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import request_id_ctx

log = logging.getLogger(__name__)


class DomainError(Exception):
    """Base class for domain/business-rule errors."""

    status_code: int = status.HTTP_400_BAD_REQUEST

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND


class ConflictError(DomainError):
    status_code = status.HTTP_409_CONFLICT


class ValidationError(DomainError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY


class InsufficientStockError(DomainError):
    status_code = status.HTTP_409_CONFLICT


def _envelope(detail, type_: str, request_id: str) -> dict:
    return {"detail": detail, "type": type_, "request_id": request_id}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def domain_error_handler(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(exc.message, exc.__class__.__name__, request_id_ctx.get()),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_envelope(
                jsonable_encoder(exc.errors()),
                "RequestValidationError",
                request_id_ctx.get(),
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        log.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_envelope("Internal server error", "ServerError", request_id_ctx.get()),
        )
