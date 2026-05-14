"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _timestamp_cols() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def upgrade() -> None:
    op.create_table(
        "providers",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        *_timestamp_cols(),
    )

    op.create_table(
        "categories",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "parent_id",
            sa.Integer,
            sa.ForeignKey("categories.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "provider_id",
            sa.Integer,
            sa.ForeignKey("providers.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.CheckConstraint(
            "(parent_id IS NULL AND provider_id IS NOT NULL) OR "
            "(parent_id IS NOT NULL AND provider_id IS NULL)",
            name="ck_category_root_has_provider",
        ),
        *_timestamp_cols(),
    )
    op.create_index("ix_categories_parent_id", "categories", ["parent_id"])
    op.create_index("ix_categories_provider_id", "categories", ["provider_id"])

    op.create_table(
        "products",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "category_id",
            sa.Integer,
            sa.ForeignKey("categories.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        *_timestamp_cols(),
    )
    op.create_index("ix_products_category_id", "products", ["category_id"])

    op.create_table(
        "storages",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("location", sa.String(255), nullable=True),
        *_timestamp_cols(),
    )

    op.create_table(
        "clients",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        *_timestamp_cols(),
    )

    op.create_table(
        "batches",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "provider_id",
            sa.Integer,
            sa.ForeignKey("providers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "storage_id",
            sa.Integer,
            sa.ForeignKey("storages.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "purchase_date",
            sa.Date,
            nullable=False,
            server_default=sa.func.current_date(),
        ),
        *_timestamp_cols(),
    )
    op.create_index("ix_batches_provider_id", "batches", ["provider_id"])
    op.create_index("ix_batches_storage_id", "batches", ["storage_id"])
    op.create_index("ix_batches_purchase_date", "batches", ["purchase_date"])

    op.create_table(
        "batch_items",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "batch_id",
            sa.Integer,
            sa.ForeignKey("batches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            sa.Integer,
            sa.ForeignKey("products.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("qty_purchased", sa.Integer, nullable=False),
        sa.Column("purchase_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("sell_price", sa.Numeric(12, 2), nullable=False),
        sa.UniqueConstraint("batch_id", "product_id", name="uq_batch_item_product"),
        sa.CheckConstraint("qty_purchased > 0", name="ck_batch_item_qty_positive"),
        sa.CheckConstraint("purchase_price >= 0", name="ck_batch_item_purchase_price_nonneg"),
        sa.CheckConstraint("sell_price >= 0", name="ck_batch_item_sell_price_nonneg"),
        *_timestamp_cols(),
    )
    op.create_index("ix_batch_items_batch_id", "batch_items", ["batch_id"])
    op.create_index("ix_batch_items_product_id", "batch_items", ["product_id"])
    # Composite index supporting the FIFO query: for a product, get its batch_items
    # joined to batches ordered by purchase_date asc. This index keeps
    # (product_id, batch_id) co-located so the planner can do an index scan.
    op.create_index(
        "ix_batch_items_product_batch", "batch_items", ["product_id", "batch_id"]
    )

    op.create_table(
        "orders",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "client_id",
            sa.Integer,
            sa.ForeignKey("clients.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "order_date",
            sa.Date,
            nullable=False,
            server_default=sa.func.current_date(),
        ),
        *_timestamp_cols(),
    )
    op.create_index("ix_orders_client_id", "orders", ["client_id"])
    op.create_index("ix_orders_order_date", "orders", ["order_date"])

    op.create_table(
        "order_items",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "order_id",
            sa.Integer,
            sa.ForeignKey("orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "batch_item_id",
            sa.Integer,
            sa.ForeignKey("batch_items.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("qty", sa.Integer, nullable=False),
        sa.Column("sell_price", sa.Numeric(12, 2), nullable=False),
        sa.CheckConstraint("qty > 0", name="ck_order_item_qty_positive"),
        sa.CheckConstraint("sell_price >= 0", name="ck_order_item_sell_price_nonneg"),
        *_timestamp_cols(),
    )
    op.create_index("ix_order_items_order_id", "order_items", ["order_id"])
    op.create_index("ix_order_items_batch_item_id", "order_items", ["batch_item_id"])

    op.create_table(
        "provider_refunds",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "batch_item_id",
            sa.Integer,
            sa.ForeignKey("batch_items.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("qty", sa.Integer, nullable=False),
        sa.Column("refund_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "refund_date",
            sa.Date,
            nullable=False,
            server_default=sa.func.current_date(),
        ),
        sa.CheckConstraint("qty > 0", name="ck_provider_refund_qty_positive"),
        sa.CheckConstraint("refund_amount >= 0", name="ck_provider_refund_amount_nonneg"),
        *_timestamp_cols(),
    )
    op.create_index("ix_provider_refunds_batch_item_id", "provider_refunds", ["batch_item_id"])
    op.create_index("ix_provider_refunds_refund_date", "provider_refunds", ["refund_date"])

    op.create_table(
        "client_refunds",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "order_item_id",
            sa.Integer,
            sa.ForeignKey("order_items.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("qty", sa.Integer, nullable=False),
        sa.Column("refund_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "refund_date",
            sa.Date,
            nullable=False,
            server_default=sa.func.current_date(),
        ),
        sa.CheckConstraint("qty > 0", name="ck_client_refund_qty_positive"),
        sa.CheckConstraint("refund_amount >= 0", name="ck_client_refund_amount_nonneg"),
        *_timestamp_cols(),
    )
    op.create_index("ix_client_refunds_order_item_id", "client_refunds", ["order_item_id"])
    op.create_index("ix_client_refunds_refund_date", "client_refunds", ["refund_date"])


def downgrade() -> None:
    op.drop_table("client_refunds")
    op.drop_table("provider_refunds")
    op.drop_table("order_items")
    op.drop_table("orders")
    op.drop_table("batch_items")
    op.drop_table("batches")
    op.drop_table("clients")
    op.drop_table("storages")
    op.drop_table("products")
    op.drop_table("categories")
    op.drop_table("providers")
