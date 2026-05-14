from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.order import OrderItem
    from app.models.product import Product
    from app.models.provider import Provider
    from app.models.refund import ProviderRefund
    from app.models.storage import Storage


class Batch(Base, TimestampMixin):
    """A purchase event: bought a set of products from a provider into a storage."""

    __tablename__ = "batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider_id: Mapped[int] = mapped_column(
        ForeignKey("providers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    storage_id: Mapped[int] = mapped_column(
        ForeignKey("storages.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    purchase_date: Mapped[date] = mapped_column(
        Date, nullable=False, server_default=func.current_date(), index=True
    )

    provider: Mapped["Provider"] = relationship(back_populates="batches")
    storage: Mapped["Storage"] = relationship(back_populates="batches")
    items: Mapped[list["BatchItem"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan"
    )


class BatchItem(Base, TimestampMixin):
    """One product line within a batch: qty bought, price paid, intended sell price."""

    __tablename__ = "batch_items"
    __table_args__ = (
        UniqueConstraint("batch_id", "product_id", name="uq_batch_item_product"),
        CheckConstraint("qty_purchased > 0", name="ck_batch_item_qty_positive"),
        CheckConstraint("purchase_price >= 0", name="ck_batch_item_purchase_price_nonneg"),
        CheckConstraint("sell_price >= 0", name="ck_batch_item_sell_price_nonneg"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("batches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    qty_purchased: Mapped[int] = mapped_column(nullable=False)
    purchase_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    sell_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    batch: Mapped["Batch"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship(back_populates="batch_items")
    order_items: Mapped[list["OrderItem"]] = relationship(back_populates="batch_item")
    provider_refunds: Mapped[list["ProviderRefund"]] = relationship(back_populates="batch_item")
