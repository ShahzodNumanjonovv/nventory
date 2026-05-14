from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import InsufficientStockError, NotFoundError, ValidationError
from app.models import Batch, BatchItem, ClientRefund, OrderItem, ProviderRefund
from app.schemas.refund import ClientRefundCreate, ProviderRefundCreate
from app.services.stock import batch_item_available_select, order_item_net_qty_select


async def refund_to_provider(
    session: AsyncSession, payload: ProviderRefundCreate
) -> list[ProviderRefund]:
    batch = (
        await session.execute(
            select(Batch)
            .where(Batch.id == payload.batch_id)
            .options(selectinload(Batch.items))
        )
    ).scalar_one_or_none()
    if batch is None:
        raise NotFoundError(f"Batch {payload.batch_id} not found")

    items_by_product = {item.product_id: item for item in batch.items}

    # Snapshot available qty for these batch_items.
    available_select = batch_item_available_select().where(
        BatchItem.id.in_([i.id for i in batch.items])
    )
    available_rows = (await session.execute(available_select)).all()
    available_by_bi: dict[int, int] = {row.batch_item_id: row.available for row in available_rows}

    refunds: list[ProviderRefund] = []
    seen_products: set[int] = set()
    for item in payload.items:
        if item.product_id in seen_products:
            raise ValidationError(f"Duplicate product {item.product_id} in refund")
        seen_products.add(item.product_id)

        batch_item = items_by_product.get(item.product_id)
        if batch_item is None:
            raise ValidationError(
                f"Product {item.product_id} is not part of batch {payload.batch_id}"
            )

        available = available_by_bi.get(batch_item.id, 0)
        if item.qty > available:
            raise InsufficientStockError(
                f"Cannot refund {item.qty} of product {item.product_id}: only "
                f"{available} available in batch {payload.batch_id}"
            )

        refund = ProviderRefund(
            batch_item_id=batch_item.id,
            qty=item.qty,
            refund_amount=batch_item.purchase_price * item.qty,
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

    order_items_rows = await session.execute(
        select(OrderItem).where(OrderItem.id.in_(order_item_ids))
    )
    order_items = {oi.id: oi for oi in order_items_rows.scalars()}
    missing = set(order_item_ids) - order_items.keys()
    if missing:
        raise NotFoundError(f"Order items not found: {sorted(missing)}")

    # Net qty already sold (sold − previously refunded) per order_item.
    net_select = order_item_net_qty_select().where(OrderItem.id.in_(order_item_ids))
    net_rows = (await session.execute(net_select)).all()
    net_by_oi = {row.order_item_id: row.net_qty for row in net_rows}

    refunds: list[ClientRefund] = []
    for item in payload.items:
        order_item = order_items[item.order_item_id]
        refundable = net_by_oi.get(order_item.id, 0)
        if item.qty > refundable:
            raise InsufficientStockError(
                f"Cannot refund {item.qty} from order_item {order_item.id}: only "
                f"{refundable} refundable"
            )
        refund = ClientRefund(
            order_item_id=order_item.id,
            qty=item.qty,
            refund_amount=order_item.sell_price * item.qty,
            **({"refund_date": payload.refund_date} if payload.refund_date else {}),
        )
        session.add(refund)
        refunds.append(refund)

    await session.flush()
    return refunds
