from fastapi import APIRouter, status

from app.api.deps import DBSession
from app.schemas.purchase import BatchRead, PurchaseCreate
from app.services.purchase import create_purchase

router = APIRouter(prefix="/purchases", tags=["purchases"])


@router.post(
    "",
    response_model=BatchRead,
    status_code=status.HTTP_201_CREATED,
    summary="Purchase products and add to storage",
)
async def purchase_products(payload: PurchaseCreate, db: DBSession) -> BatchRead:
    batch = await create_purchase(db, payload)
    return BatchRead.model_validate(batch)
