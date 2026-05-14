"""
Test fixtures.

We swap the production async engine for an in-memory SQLite (aiosqlite) instance
per test. Each test gets a fresh schema, so tests are isolated and order-independent.
SQLAlchemy `SELECT ... FOR UPDATE` is silently ignored by SQLite; that's fine for
behavioural tests. Race-condition coverage belongs in a Postgres integration suite.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

import app.api.deps as deps_mod  # noqa: E402
import app.core.database as db_mod  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(db_engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(db_engine, expire_on_commit=False, autoflush=False)


@pytest_asyncio.fixture
async def client(session_factory) -> AsyncIterator[AsyncClient]:
    # Re-point both deps and the (unused) global SessionLocal to our test factory.
    original_deps = deps_mod.SessionLocal
    original_global = db_mod.SessionLocal
    deps_mod.SessionLocal = session_factory
    db_mod.SessionLocal = session_factory
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac
    finally:
        deps_mod.SessionLocal = original_deps
        db_mod.SessionLocal = original_global


@pytest.fixture
def api():
    return "/api/v1"
