from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import InsufficientStockError, NotFoundError, ValidationError
from app.models import Batch, BatchItem, Category, Client, Order, OrderItem, Product
from app.schemas.order import AvailableProduct, OrderCreate
from app.services.stock import batch_item_available_select


async def list_available_products(
    session: AsyncSession, *, limit: int = 200, offset: int = 0
) -> list[AvailableProduct]:
    """
    For each product with any available stock, return:
      - total available qty across all batches
      - price = sell_price of the *oldest* batch with available stock (FIFO next-up)
    """
    available = batch_item_available_select().subquery("avail")

    stmt = (
        select(
            Product.id.label("product_id"),
            Product.name.label("product_name"),
            Category.name.label("category_name"),
            BatchItem.sell_price.label("sell_price"),
            Batch.purchase_date.label("purchase_date"),
            available.c.available.label("available"),
        )
        .select_from(BatchItem)
        .join(Batch, Batch.id == BatchItem.batch_id)
        .join(Product, Product.id == BatchItem.product_id)
        .join(Category, Category.id == Product.category_id)
        .join(available, available.c.batch_item_id == BatchItem.id)
        .where(available.c.available > 0)
        .order_by(Product.id, Batch.purchase_date.asc(), BatchItem.id.asc())
    )
    rows = (await session.execute(stmt)).all()

    grouped: dict[int, AvailableProduct] = {}
    for row in rows:
        existing = grouped.get(row.product_id)
        if existing is None:
            grouped[row.product_id] = AvailableProduct(
                id=row.product_id,
                name=row.product_name,
                category_name=row.category_name,
                price=row.sell_price,  # FIFO next-up
                qty=row.available,
            )
        else:
            existing.qty += row.available

    ordered = sorted(grouped.values(), key=lambda p: p.id)
    return ordered[offset : offset + limit]


async def create_order(session: AsyncSession, payload: OrderCreate) -> Order:
    client = await session.get(Client, payload.client_id)
    if client is None:
        raise NotFoundError(f"Client {payload.client_id} not found")

    requested: dict[int, int] = defaultdict(int)
    for line in payload.products:
        requested[line.id] += line.qty
    if not requested:
        raise ValidationError("Order has no products")

    products_rows = await session.execute(
        select(Product.id).where(Product.id.in_(requested.keys()))
    )
    found = {pid for (pid,) in products_rows.all()}
    missing = set(requested.keys()) - found
    if missing:
        raise NotFoundError(f"Products not found: {sorted(missing)}")

    # ----- concurrency guard ---------------------------------------------------
    # Lock all batch_items for the requested products for the duration of this
    # transaction. Any concurrent transaction trying to allocate the same stock
    # waits at this SELECT. SQLite ignores FOR UPDATE silently (fine for tests).
    candidates_stmt = (
        select(
            BatchItem.id,
            BatchItem.product_id,
            BatchItem.sell_price,
            Batch.purchase_date,
        )
        .join(Batch, Batch.id == BatchItem.batch_id)
        .where(BatchItem.product_id.in_(requested.keys()))
        .order_by(BatchItem.product_id, Batch.purchase_date.asc(), BatchItem.id.asc())
        .with_for_update(of=BatchItem)
    )
    candidates = (await session.execute(candidates_stmt)).all()
    if not candidates:
        first_missing = next(iter(requested))
        raise InsufficientStockError(f"Product {first_missing}: no stock")

    candidate_ids = [c.id for c in candidates]
    avail_stmt = batch_item_available_select().where(BatchItem.id.in_(candidate_ids))
    avail_rows = (await session.execute(avail_stmt)).all()
    avail_by_bi = {r.batch_item_id: r.available for r in avail_rows}

    # FIFO buckets per product, already ordered by purchase_date asc.
    by_product: dict[int, list] = defaultdict(list)
    for c in candidates:
        if avail_by_bi.get(c.id, 0) > 0:
            by_product[c.product_id].append(c)

    order = Order(client_id=payload.client_id)
    session.add(order)

    for product_id, qty_needed in requested.items():
        bucket = by_product.get(product_id, [])
        total_available = sum(avail_by_bi[c.id] for c in bucket)
        if qty_needed > total_available:
            raise InsufficientStockError(
                f"Product {product_id}: requested {qty_needed}, "
                f"only {total_available} available"
            )
        remaining = qty_needed
        for c in bucket:
            if remaining == 0:
                break
            take = min(remaining, avail_by_bi[c.id])
            order.items.append(
                OrderItem(
                    batch_item_id=c.id,
                    qty=take,
                    sell_price=c.sell_price,
                )
            )
            remaining -= take

    await session.flush()

    result = await session.execute(
        select(Order).where(Order.id == order.id).options(selectinload(Order.items))
    )
    return result.scalar_one()
