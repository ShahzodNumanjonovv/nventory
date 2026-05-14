"""
Stock accounting helpers.

A batch_item's "available" qty in storage at any moment is:

    qty_purchased
        - sum(provider_refunds.qty)         # returned to provider
        - sum(order_items.qty)              # sold to clients
        + sum(client_refunds.qty)           # returned by clients

These helpers build that expression as reusable SQL subqueries so the same
accounting is applied consistently across every service.
"""

from datetime import date

from sqlalchemy import func, select

from app.models import BatchItem, ClientRefund, Order, OrderItem, ProviderRefund


def _provider_refunded(as_of: date | None = None):
    q = select(
        ProviderRefund.batch_item_id.label("batch_item_id"),
        func.coalesce(func.sum(ProviderRefund.qty), 0).label("qty"),
    )
    if as_of is not None:
        q = q.where(ProviderRefund.refund_date <= as_of)
    return q.group_by(ProviderRefund.batch_item_id).subquery("provider_refunded")


def _sold(as_of: date | None = None):
    q = select(
        OrderItem.batch_item_id.label("batch_item_id"),
        func.coalesce(func.sum(OrderItem.qty), 0).label("qty"),
    ).join(Order, Order.id == OrderItem.order_id)
    if as_of is not None:
        q = q.where(Order.order_date <= as_of)
    return q.group_by(OrderItem.batch_item_id).subquery("sold")


def _client_returned(as_of: date | None = None):
    q = select(
        OrderItem.batch_item_id.label("batch_item_id"),
        func.coalesce(func.sum(ClientRefund.qty), 0).label("qty"),
    ).join(ClientRefund, ClientRefund.order_item_id == OrderItem.id)
    if as_of is not None:
        q = q.where(ClientRefund.refund_date <= as_of)
    return q.group_by(OrderItem.batch_item_id).subquery("client_returned")


def batch_item_available_select(as_of: date | None = None):
    """
    Returns a SELECT yielding (batch_item_id, available_qty) for every batch_item.

    Pass `as_of` to constrain refunds/sales/returns to events on or before that date
    (used for historical stock snapshots).
    """
    refunded = _provider_refunded(as_of)
    sold = _sold(as_of)
    returned = _client_returned(as_of)

    return (
        select(
            BatchItem.id.label("batch_item_id"),
            (
                BatchItem.qty_purchased
                - func.coalesce(refunded.c.qty, 0)
                - func.coalesce(sold.c.qty, 0)
                + func.coalesce(returned.c.qty, 0)
            ).label("available"),
        )
        .select_from(BatchItem)
        .outerjoin(refunded, refunded.c.batch_item_id == BatchItem.id)
        .outerjoin(sold, sold.c.batch_item_id == BatchItem.id)
        .outerjoin(returned, returned.c.batch_item_id == BatchItem.id)
    )


def order_item_net_qty_select():
    """(order_item_id, net_qty) where net_qty = sold qty minus client refunds."""
    refunds = (
        select(
            ClientRefund.order_item_id.label("order_item_id"),
            func.coalesce(func.sum(ClientRefund.qty), 0).label("qty"),
        )
        .group_by(ClientRefund.order_item_id)
        .subquery("client_refunded_per_oi")
    )
    return (
        select(
            OrderItem.id.label("order_item_id"),
            (OrderItem.qty - func.coalesce(refunds.c.qty, 0)).label("net_qty"),
        )
        .select_from(OrderItem)
        .outerjoin(refunds, refunds.c.order_item_id == OrderItem.id)
    )


__all__ = [
    "batch_item_available_select",
    "order_item_net_qty_select",
]
