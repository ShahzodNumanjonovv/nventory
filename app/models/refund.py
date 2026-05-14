from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.batch import BatchItem
    from app.models.order import OrderItem


class ProviderRefund(Base, TimestampMixin):
    """Stock returned to a provider — reduces availability of a batch_item."""

    __tablename__ = "provider_refunds"
    __table_args__ = (
        CheckConstraint("qty > 0", name="ck_provider_refund_qty_positive"),
        CheckConstraint("refund_amount >= 0", name="ck_provider_refund_amount_nonneg"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_item_id: Mapped[int] = mapped_column(
        ForeignKey("batch_items.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    qty: Mapped[int] = mapped_column(nullable=False)
    refund_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    refund_date: Mapped[date] = mapped_column(
        Date, nullable=False, server_default=func.current_date(), index=True
    )

    batch_item: Mapped["BatchItem"] = relationship(back_populates="provider_refunds")


class ClientRefund(Base, TimestampMixin):
    """Stock returned from a client — money refunded and stock back to storage."""

    __tablename__ = "client_refunds"
    __table_args__ = (
        CheckConstraint("qty > 0", name="ck_client_refund_qty_positive"),
        CheckConstraint("refund_amount >= 0", name="ck_client_refund_amount_nonneg"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    order_item_id: Mapped[int] = mapped_column(
        ForeignKey("order_items.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    qty: Mapped[int] = mapped_column(nullable=False)
    refund_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    refund_date: Mapped[date] = mapped_column(
        Date, nullable=False, server_default=func.current_date(), index=True
    )

    order_item: Mapped["OrderItem"] = relationship(back_populates="client_refunds")
