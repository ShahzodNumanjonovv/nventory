from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal


async def get_db() -> AsyncIterator[AsyncSession]:
    """
    Per-request session.

    Wraps the request in a single transaction: commit on clean exit, rollback
    on any exception. Services should NOT call `commit()` themselves — they
    call `flush()` to materialize PKs and let the dependency commit at the end.
    """
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()


DBSession = Annotated[AsyncSession, Depends(get_db)]
