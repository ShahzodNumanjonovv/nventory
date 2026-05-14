from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield


app = FastAPI(
    title="Wholesale Inventory API",
    version="0.1.0",
    description=(
        "Manage purchases from providers, storage, sales to clients, and refunds. "
        "Orders FIFO-allocate from the oldest available batch."
    ),
    lifespan=lifespan,
)

register_exception_handlers(app)
app.include_router(api_router, prefix="/api/v1")


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok", "env": settings.app_env}
