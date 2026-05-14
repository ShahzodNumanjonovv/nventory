from sqlalchemy import literal, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError, ValidationError
from app.models import Batch, BatchItem, Category, Product, Provider, Storage
from app.schemas.purchase import PurchaseCreate

_MAX_CATEGORY_DEPTH = 32


async def _resolve_root_providers(
    session: AsyncSession, category_ids: list[int]
) -> dict[int, int]:
    """
    Map each `category_id` to its root category's `provider_id` in a single
    recursive CTE. Depth-bounded to protect against accidental parent-cycles.
    """
    if not category_ids:
        return {}
    anchor = select(
        Category.id.label("start_id"),
        Category.id.label("id"),
        Category.parent_id.label("parent_id"),
        Category.provider_id.label("provider_id"),
        literal(0).label("depth"),
    ).where(Category.id.in_(category_ids))

    walk = anchor.cte("category_walk", recursive=True)
    parent = Category.__table__.alias("parent_cat")
    recursive = (
        select(
            walk.c.start_id,
            parent.c.id,
            parent.c.parent_id,
            parent.c.provider_id,
            (walk.c.depth + 1).label("depth"),
        )
        .select_from(walk)
        .join(parent, parent.c.id == walk.c.parent_id)
        .where(walk.c.depth < _MAX_CATEGORY_DEPTH)
    )
    walk = walk.union_all(recursive)

    rows = (
        await session.execute(
            select(walk.c.start_id, walk.c.provider_id).where(walk.c.parent_id.is_(None))
        )
    ).all()
    return {row.start_id: row.provider_id for row in rows}


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
        select(Product.id, Product.name, Product.category_id).where(
            Product.id.in_(product_ids)
        )
    )
    products = {row.id: row for row in products_rows.all()}
    missing = set(product_ids) - products.keys()
    if missing:
        raise NotFoundError(f"Products not found: {sorted(missing)}")

    category_ids = list({p.category_id for p in products.values()})
    root_providers = await _resolve_root_providers(session, category_ids)
    unresolved = set(category_ids) - root_providers.keys()
    if unresolved:
        raise ValidationError(
            f"Categories without a resolvable root provider (cycle or missing parent): "
            f"{sorted(unresolved)}"
        )

    for product in products.values():
        root_provider_id = root_providers[product.category_id]
        if root_provider_id != payload.provider_id:
            raise ValidationError(
                f"Product {product.id} ('{product.name}') belongs to provider "
                f"{root_provider_id}, not {payload.provider_id}"
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

    result = await session.execute(
        select(Batch).where(Batch.id == batch.id).options(selectinload(Batch.items))
    )
    return result.scalar_one()
