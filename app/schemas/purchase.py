from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel, validate_business_date


class PurchaseItemIn(BaseModel):
    product_id: int
    qty: int = Field(gt=0)
    purchase_price: Decimal = Field(ge=0, decimal_places=2)
    sell_price: Decimal = Field(ge=0, decimal_places=2)


class PurchaseCreate(BaseModel):
    provider_id: int
    storage_id: int
    purchase_date: date | None = None
    items: list[PurchaseItemIn] = Field(min_length=1)

    @field_validator("purchase_date")
    @classmethod
    def _check_date(cls, v: date | None) -> date | None:
        return validate_business_date(v)


class BatchItemRead(ORMModel):
    id: int
    product_id: int
    qty_purchased: int
    purchase_price: Decimal
    sell_price: Decimal


class BatchRead(ORMModel):
    id: int
    provider_id: int
    storage_id: int
    purchase_date: date
    items: list[BatchItemRead]
