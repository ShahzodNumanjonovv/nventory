from fastapi import APIRouter, status

from app.api.deps import DBSession
from app.schemas.order import OrderCreate, OrderRead
from app.services.order import create_order

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post(
    "",
    response_model=OrderRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a client order (auto-assigns batches FIFO)",
)
async def create_client_order(payload: OrderCreate, db: DBSession) -> OrderRead:
    order = await create_order(db, payload)
    return OrderRead.model_validate(order)
