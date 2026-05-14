from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.provider import Provider


class Category(Base, TimestampMixin):
    """
    Hierarchical category. Root categories (parent_id IS NULL) belong to a Provider.
    Subcategories inherit the provider via their root ancestor and must have parent_id NOT NULL.
    """

    __tablename__ = "categories"
    __table_args__ = (
        CheckConstraint(
            "(parent_id IS NULL AND provider_id IS NOT NULL) OR "
            "(parent_id IS NOT NULL AND provider_id IS NULL)",
            name="ck_category_root_has_provider",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    provider_id: Mapped[int | None] = mapped_column(
        ForeignKey("providers.id", ondelete="RESTRICT"), nullable=True, index=True
    )

    parent: Mapped["Category | None"] = relationship(
        "Category", remote_side="Category.id", back_populates="children"
    )
    children: Mapped[list["Category"]] = relationship(
        "Category", back_populates="parent"
    )
    provider: Mapped["Provider | None"] = relationship(back_populates="root_categories")
    products: Mapped[list["Product"]] = relationship(back_populates="category")
