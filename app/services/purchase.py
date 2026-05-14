from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError, ValidationError
from app.models import Batch, BatchItem, Category, Product, Provider, Storage
from app.schemas.purchase import PurchaseCreate


async def _root_category(session: AsyncSession, category_id: int) -> Category:
    """Walk up the parent chain to find the root category."""
    current = await session.get(Category, category_id)
    if current is None:
        raise NotFoundError(f"Category {category_id} not found")
    while current.parent_id is not None:
        parent = await session.get(Category, current.parent_id)
        if parent is None:
            raise ValidationError(f"Category {current.id} has dangling parent")
        current = parent
    return current


async def create_purchase(session: AsyncSession, payload: PurchaseCreate) -> Batch:
    provider = await session.get(Provider, payload.provider_id)
    if provider is None:
        raise NotFoundError(f"Provider {payload.provider_id} not found")

    storage = await session.get(Storage, payload.storage_id)
    if storage is None:
        raise NotFoundError(f"Storage {payload.storage_id} not found")

    product_ids = [item.product_id for item in payload.items]
    if len(set(product_ids)) != len(product_ids):
        raise ValidationError("Duplicate products in purchase items")

    products_rows = await session.execute(
        select(Product).where(Product.id.in_(product_ids))
    )
    products = {p.id: p for p in products_rows.scalars()}

    missing = set(product_ids) - products.keys()
    if missing:
        raise NotFoundError(f"Products not found: {sorted(missing)}")

    # Verify every product's root category belongs to this provider.
    for product in products.values():
        root = await _root_category(session, product.category_id)
        if root.provider_id != payload.provider_id:
            raise ValidationError(
                f"Product {product.id} ('{product.name}') belongs to provider "
                f"{root.provider_id}, not {payload.provider_id}"
            )

    batch = Batch(
        provider_id=payload.provider_id,
        storage_id=payload.storage_id,
        **({"purchase_date": payload.purchase_date} if payload.purchase_date else {}),
    )
    batch.items = [
        BatchItem(
            product_id=item.product_id,
            qty_purchased=item.qty,
            purchase_price=item.purchase_price,
            sell_price=item.sell_price,
        )
        for item in payload.items
    ]
    session.add(batch)
    await session.flush()

    # Reload with items eagerly to safely serialize.
    result = await session.execute(
        select(Batch).where(Batch.id == batch.id).options(selectinload(Batch.items))
    )
    return result.scalar_one()
