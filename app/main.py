import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import engine
from app.core.exceptions import register_exception_handlers
from app.core.logging import RequestIDMiddleware, configure_logging

log = logging.getLogger("app")


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        log.info("Database connectivity OK (%s)", settings.app_env)
    except Exception:
        log.exception("Database connectivity check FAILED — startup aborted")
        raise
    yield
    await engine.dispose()


app = FastAPI(
    title="Wholesale Inventory API",
    version="0.1.0",
    description=(
        "Manage purchases from providers, storage, sales to clients, and refunds. "
        "Orders FIFO-allocate from the oldest available batch."
    ),
    lifespan=lifespan,
)

app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)
app.include_router(api_router, prefix="/api/v1")


@app.get("/health/live", tags=["meta"], summary="Liveness probe (process up)")
async def health_live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready", tags=["meta"], summary="Readiness probe (DB reachable)")
async def health_ready() -> dict[str, str]:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return {"status": "ok", "db": "ok", "env": settings.app_env}
