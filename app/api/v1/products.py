from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import DBSession
from app.schemas.order import AvailableProduct
from app.services.order import list_available_products

router = APIRouter(prefix="/products", tags=["products"])


@router.get(
    "/available",
    response_model=list[AvailableProduct],
    summary="Fetch available products for ordering",
)
async def fetch_available(
    db: DBSession,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[AvailableProduct]:
    return await list_available_products(db, limit=limit, offset=offset)
