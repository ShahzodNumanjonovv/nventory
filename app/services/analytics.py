from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Batch,
    BatchItem,
    ClientRefund,
    Order,
    OrderItem,
    Product,
    ProviderRefund,
    Storage,
)
from app.schemas.analytics import BatchProfit, StorageRemaining


async def storage_remaining_on(session: AsyncSession, as_of: date) -> list[StorageRemaining]:
    """
    Per (storage, product) remaining qty in storage as of the given date.

    Movements that happened *after* `as_of` are ignored. This computes:
        purchased_to_storage(<=date)
            - refunded_to_provider(<=date)
            - sold(<=date)
            + returned_by_client(<=date)
    grouped by storage (the storage of the batch the movement is tied to).
    """
    purchased = (
        select(
            Batch.storage_id.label("storage_id"),
            BatchItem.product_id.label("product_id"),
            func.coalesce(func.sum(BatchItem.qty_purchased), 0).label("qty"),
        )
        .select_from(BatchItem)
        .join(Batch, Batch.id == BatchItem.batch_id)
        .where(Batch.purchase_date <= as_of)
        .group_by(Batch.storage_id, BatchItem.product_id)
        .subquery("purchased")
    )
    refunded_provider = (
        select(
            Batch.storage_id.label("storage_id"),
            BatchItem.product_id.label("product_id"),
            func.coalesce(func.sum(ProviderRefund.qty), 0).label("qty"),
        )
        .select_from(ProviderRefund)
        .join(BatchItem, BatchItem.id == ProviderRefund.batch_item_id)
        .join(Batch, Batch.id == BatchItem.batch_id)
        .where(ProviderRefund.refund_date <= as_of)
        .group_by(Batch.storage_id, BatchItem.product_id)
        .subquery("refunded_provider")
    )
    sold = (
        select(
            Batch.storage_id.label("storage_id"),
            BatchItem.product_id.label("product_id"),
            func.coalesce(func.sum(OrderItem.qty), 0).label("qty"),
        )
        .select_from(OrderItem)
        .join(Order, Order.id == OrderItem.order_id)
        .join(BatchItem, BatchItem.id == OrderItem.batch_item_id)
        .join(Batch, Batch.id == BatchItem.batch_id)
        .where(Order.order_date <= as_of)
        .group_by(Batch.storage_id, BatchItem.product_id)
        .subquery("sold")
    )
    returned = (
        select(
            Batch.storage_id.label("storage_id"),
            BatchItem.product_id.label("product_id"),
            func.coalesce(func.sum(ClientRefund.qty), 0).label("qty"),
        )
        .select_from(ClientRefund)
        .join(OrderItem, OrderItem.id == ClientRefund.order_item_id)
        .join(BatchItem, BatchItem.id == OrderItem.batch_item_id)
        .join(Batch, Batch.id == BatchItem.batch_id)
        .where(ClientRefund.refund_date <= as_of)
        .group_by(Batch.storage_id, BatchItem.product_id)
        .subquery("returned")
    )

    # purchased is the spine — anything refunded/sold/returned implies a prior purchase.
    stmt = (
        select(
            purchased.c.storage_id,
            Storage.name.label("storage_name"),
            purchased.c.product_id,
            Product.name.label("product_name"),
            (
                purchased.c.qty
                - func.coalesce(refunded_provider.c.qty, 0)
                - func.coalesce(sold.c.qty, 0)
                + func.coalesce(returned.c.qty, 0)
            ).label("qty"),
        )
        .select_from(purchased)
        .join(Storage, Storage.id == purchased.c.storage_id)
        .join(Product, Product.id == purchased.c.product_id)
        .outerjoin(
            refunded_provider,
            (refunded_provider.c.storage_id == purchased.c.storage_id)
            & (refunded_provider.c.product_id == purchased.c.product_id),
        )
        .outerjoin(
            sold,
            (sold.c.storage_id == purchased.c.storage_id)
            & (sold.c.product_id == purchased.c.product_id),
        )
        .outerjoin(
            returned,
            (returned.c.storage_id == purchased.c.storage_id)
            & (returned.c.product_id == purchased.c.product_id),
        )
        .order_by(purchased.c.storage_id, purchased.c.product_id)
    )

    rows = (await session.execute(stmt)).all()
    return [
        StorageRemaining(
            storage_id=row.storage_id,
            storage_name=row.storage_name,
            product_id=row.product_id,
            product_name=row.product_name,
            qty=row.qty,
        )
        for row in rows
        if row.qty != 0
    ]


async def profit_per_batch(session: AsyncSession) -> list[BatchProfit]:
    """
    Per-batch profit = (revenue from sales − client refund payouts)
                       − (purchase cost − provider refund recoveries).
    """
    cost_purchase = (
        select(
            BatchItem.batch_id.label("batch_id"),
            func.coalesce(
                func.sum(BatchItem.qty_purchased * BatchItem.purchase_price), 0
            ).label("cost"),
        )
        .group_by(BatchItem.batch_id)
        .subquery("cost_purchase")
    )
    cost_recovered = (
        select(
            BatchItem.batch_id.label("batch_id"),
            func.coalesce(func.sum(ProviderRefund.refund_amount), 0).label("recovered"),
        )
        .select_from(ProviderRefund)
        .join(BatchItem, BatchItem.id == ProviderRefund.batch_item_id)
        .group_by(BatchItem.batch_id)
        .subquery("cost_recovered")
    )
    revenue_gross = (
        select(
            BatchItem.batch_id.label("batch_id"),
            func.coalesce(func.sum(OrderItem.qty * OrderItem.sell_price), 0).label("revenue"),
        )
        .select_from(OrderItem)
        .join(BatchItem, BatchItem.id == OrderItem.batch_item_id)
        .group_by(BatchItem.batch_id)
        .subquery("revenue_gross")
    )
    revenue_refunded = (
        select(
            BatchItem.batch_id.label("batch_id"),
            func.coalesce(func.sum(ClientRefund.refund_amount), 0).label("refunded"),
        )
        .select_from(ClientRefund)
        .join(OrderItem, OrderItem.id == ClientRefund.order_item_id)
        .join(BatchItem, BatchItem.id == OrderItem.batch_item_id)
        .group_by(BatchItem.batch_id)
        .subquery("revenue_refunded")
    )

    stmt = (
        select(
            Batch.id.label("batch_id"),
            Batch.provider_id.label("provider_id"),
            Batch.purchase_date.label("purchase_date"),
            func.coalesce(cost_purchase.c.cost, 0).label("cost_purchase"),
            func.coalesce(cost_recovered.c.recovered, 0).label("cost_recovered"),
            func.coalesce(revenue_gross.c.revenue, 0).label("revenue_gross"),
            func.coalesce(revenue_refunded.c.refunded, 0).label("revenue_refunded"),
        )
        .select_from(Batch)
        .outerjoin(cost_purchase, cost_purchase.c.batch_id == Batch.id)
        .outerjoin(cost_recovered, cost_recovered.c.batch_id == Batch.id)
        .outerjoin(revenue_gross, revenue_gross.c.batch_id == Batch.id)
        .outerjoin(revenue_refunded, revenue_refunded.c.batch_id == Batch.id)
        .order_by(Batch.id)
    )

    rows = (await session.execute(stmt)).all()
    result: list[BatchProfit] = []
    for row in rows:
        revenue = Decimal(row.revenue_gross) - Decimal(row.revenue_refunded)
        cost = Decimal(row.cost_purchase) - Decimal(row.cost_recovered)
        result.append(
            BatchProfit(
                batch_id=row.batch_id,
                provider_id=row.provider_id,
                purchase_date=row.purchase_date,
                revenue=revenue,
                cost=cost,
                profit=revenue - cost,
            )
        )
    return result
