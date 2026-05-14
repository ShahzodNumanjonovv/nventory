from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import InsufficientStockError, NotFoundError, ValidationError
from app.models import Batch, BatchItem, Category, Client, Order, OrderItem, Product
from app.schemas.order import AvailableProduct, OrderCreate
from app.services.stock import batch_item_available_select


async def list_available_products(session: AsyncSession) -> list[AvailableProduct]:
    """
    For each product with any available stock, return:
      - total available qty across all batches
      - price = sell_price of the *oldest* batch with available stock (the FIFO next-up)
    """
    available = batch_item_available_select().subquery("avail")

    stmt = (
        select(
            Product.id.label("product_id"),
            Product.name.label("product_name"),
            Category.name.label("category_name"),
            BatchItem.id.label("batch_item_id"),
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

    grouped: dict[int, dict] = {}
    for row in rows:
        entry = grouped.setdefault(
            row.product_id,
            {
                "id": row.product_id,
                "name": row.product_name,
                "category_name": row.category_name,
                "price": row.sell_price,  # first row = oldest batch (FIFO next-up)
                "qty": 0,
            },
        )
        entry["qty"] += row.available
    return [AvailableProduct(**v) for v in grouped.values()]


async def create_order(session: AsyncSession, payload: OrderCreate) -> Order:
    client = await session.get(Client, payload.client_id)
    if client is None:
        raise NotFoundError(f"Client {payload.client_id} not found")

    # Aggregate requested qty per product (in case caller sent duplicates).
    requested: dict[int, int] = defaultdict(int)
    for line in payload.products:
        requested[line.id] += line.qty
    if not requested:
        raise ValidationError("Order has no products")

    # Verify all products exist.
    products_rows = await session.execute(
        select(Product).where(Product.id.in_(requested.keys()))
    )
    products = {p.id: p for p in products_rows.scalars()}
    missing = set(requested.keys()) - products.keys()
    if missing:
        raise NotFoundError(f"Products not found: {sorted(missing)}")

    # Fetch available batch_items for the requested products, ordered FIFO.
    available = batch_item_available_select().subquery("avail")
    stmt = (
        select(BatchItem, available.c.available, Batch.purchase_date)
        .select_from(BatchItem)
        .join(Batch, Batch.id == BatchItem.batch_id)
        .join(available, available.c.batch_item_id == BatchItem.id)
        .where(BatchItem.product_id.in_(requested.keys()))
        .where(available.c.available > 0)
        .order_by(BatchItem.product_id, Batch.purchase_date.asc(), BatchItem.id.asc())
    )
    rows = (await session.execute(stmt)).all()

    by_product: dict[int, list[tuple[BatchItem, int]]] = defaultdict(list)
    for row in rows:
        by_product[row[0].product_id].append((row[0], row.available))

    order = Order(client_id=payload.client_id)
    session.add(order)

    for product_id, qty_needed in requested.items():
        candidates = by_product.get(product_id, [])
        total_available = sum(avail for _, avail in candidates)
        if qty_needed > total_available:
            raise InsufficientStockError(
                f"Product {product_id}: requested {qty_needed}, "
                f"only {total_available} available"
            )
        remaining = qty_needed
        for batch_item, avail in candidates:
            if remaining == 0:
                break
            take = min(remaining, avail)
            order.items.append(
                OrderItem(
                    batch_item_id=batch_item.id,
                    qty=take,
                    sell_price=batch_item.sell_price,
                )
            )
            remaining -= take

    await session.flush()

    result = await session.execute(
        select(Order).where(Order.id == order.id).options(selectinload(Order.items))
    )
    return result.scalar_one()
