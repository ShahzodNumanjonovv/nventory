from datetime import date

from fastapi import APIRouter, Query

from app.api.deps import DBSession
from app.schemas.analytics import BatchProfit, StorageRemaining
from app.schemas.common import validate_business_date
from app.services.analytics import profit_per_batch, storage_remaining_on

router = APIRouter(tags=["analytics"])


@router.get(
    "/storage/remaining",
    response_model=list[StorageRemaining],
    summary="Remaining quantities in storage as of the given date",
)
async def remaining_storage(
    db: DBSession,
    on_date: date = Query(alias="date", description="Snapshot date (YYYY-MM-DD)"),
) -> list[StorageRemaining]:
    validate_business_date(on_date)
    return await storage_remaining_on(db, on_date)


@router.get(
    "/analytics/profit-per-batch",
    response_model=list[BatchProfit],
    summary="Profit per batch (revenue − cost, net of refunds)",
)
async def batch_profit(db: DBSession) -> list[BatchProfit]:
    return await profit_per_batch(db)
