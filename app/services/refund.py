from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InsufficientStockError, NotFoundError, ValidationError
from app.models import Batch, BatchItem, ClientRefund, OrderItem, ProviderRefund
from app.schemas.refund import ClientRefundCreate, ProviderRefundCreate
from app.services.stock import batch_item_available_select, order_item_net_qty_select


async def refund_to_provider(
    session: AsyncSession, payload: ProviderRefundCreate
) -> list[ProviderRefund]:
    batch = await session.get(Batch, payload.batch_id)
    if batch is None:
        raise NotFoundError(f"Batch {payload.batch_id} not found")

    # Lock the batch's items for the duration of this transaction so a concurrent
    # order or refund cannot race the availability check.
    items_stmt = (
        select(BatchItem)
        .where(BatchItem.batch_id == payload.batch_id)
        .with_for_update()
    )
    items = list((await session.execute(items_stmt)).scalars())
    items_by_product = {item.product_id: item for item in items}

    avail_rows = (
        await session.execute(
            batch_item_available_select().where(
                BatchItem.id.in_([i.id for i in items])
            )
        )
    ).all()
    available_by_bi = {row.batch_item_id: row.available for row in avail_rows}

    refunds: list[ProviderRefund] = []
    seen_products: set[int] = set()
    for line in payload.items:
        if line.product_id in seen_products:
            raise ValidationError(f"Duplicate product {line.product_id} in refund")
        seen_products.add(line.product_id)

        batch_item = items_by_product.get(line.product_id)
        if batch_item is None:
            raise ValidationError(
                f"Product {line.product_id} is not part of batch {payload.batch_id}"
            )

        available = available_by_bi.get(batch_item.id, 0)
        if line.qty > available:
            raise InsufficientStockError(
                f"Cannot refund {line.qty} of product {line.product_id}: only "
                f"{available} available in batch {payload.batch_id}"
            )

        refund = ProviderRefund(
            batch_item_id=batch_item.id,
            qty=line.qty,
            refund_amount=batch_item.purchase_price * line.qty,
            **({"refund_date": payload.refund_date} if payload.refund_date else {}),
        )
        session.add(refund)
        refunds.append(refund)

    await session.flush()
    return refunds


async def refund_from_client(
    session: AsyncSession, payload: ClientRefundCreate
) -> list[ClientRefund]:
    order_item_ids = [item.order_item_id for item in payload.items]
    if len(set(order_item_ids)) != len(order_item_ids):
        raise ValidationError("Duplicate order_item_id in refund")

    # Lock the order_items being refunded.
    locked_stmt = (
        select(OrderItem)
        .where(OrderItem.id.in_(order_item_ids))
        .with_for_update()
    )
    order_items = {oi.id: oi for oi in (await session.execute(locked_stmt)).scalars()}
    missing = set(order_item_ids) - order_items.keys()
    if missing:
        raise NotFoundError(f"Order items not found: {sorted(missing)}")

    net_rows = (
        await session.execute(
            order_item_net_qty_select().where(OrderItem.id.in_(order_item_ids))
        )
    ).all()
    net_by_oi = {row.order_item_id: row.net_qty for row in net_rows}

    refunds: list[ClientRefund] = []
    for line in payload.items:
        order_item = order_items[line.order_item_id]
        refundable = net_by_oi.get(order_item.id, 0)
        if line.qty > refundable:
            raise InsufficientStockError(
                f"Cannot refund {line.qty} from order_item {order_item.id}: "
                f"only {refundable} refundable"
            )
        refund = ClientRefund(
            order_item_id=order_item.id,
            qty=line.qty,
            refund_amount=order_item.sell_price * line.qty,
            **({"refund_date": payload.refund_date} if payload.refund_date else {}),
        )
        session.add(refund)
        refunds.append(refund)

    await session.flush()
    return refunds
