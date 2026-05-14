import logging
import sys
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


class _RequestIDFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get()
        return True


def configure_logging() -> None:
    root = logging.getLogger()
    root.setLevel(settings.log_level.upper())

    for h in list(root.handlers):
        root.removeHandler(h)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s"
        )
    )
    handler.addFilter(_RequestIDFilter())
    root.addHandler(handler)

    # SQLAlchemy is noisy at INFO; keep it at WARNING regardless.
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Assign an X-Request-ID per request and echo it back in the response."""

    HEADER = "X-Request-ID"

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        rid = request.headers.get(self.HEADER) or uuid.uuid4().hex[:12]
        token = request_id_ctx.set(rid)
        try:
            response = await call_next(request)
        finally:
            request_id_ctx.reset(token)
        response.headers[self.HEADER] = rid
        return response
