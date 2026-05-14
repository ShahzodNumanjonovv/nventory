from fastapi import APIRouter, status

from app.api.deps import DBSession
from app.schemas.refund import (
    ClientRefundCreate,
    ClientRefundRead,
    ProviderRefundCreate,
    ProviderRefundRead,
)
from app.services.refund import refund_from_client, refund_to_provider

router = APIRouter(prefix="/refunds", tags=["refunds"])


@router.post(
    "/providers",
    response_model=list[ProviderRefundRead],
    status_code=status.HTTP_201_CREATED,
    summary="Refund purchased products to provider (full or partial)",
)
async def refund_purchase(
    payload: ProviderRefundCreate, db: DBSession
) -> list[ProviderRefundRead]:
    refunds = await refund_to_provider(db, payload)
    return [ProviderRefundRead.model_validate(r) for r in refunds]


@router.post(
    "/clients",
    response_model=list[ClientRefundRead],
    status_code=status.HTTP_201_CREATED,
    summary="Refund sold products from a client (full or partial)",
)
async def refund_sale(
    payload: ClientRefundCreate, db: DBSession
) -> list[ClientRefundRead]:
    refunds = await refund_from_client(db, payload)
    return [ClientRefundRead.model_validate(r) for r in refunds]
