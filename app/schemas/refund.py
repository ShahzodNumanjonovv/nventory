from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel, validate_business_date


class ProviderRefundItemIn(BaseModel):
    product_id: int
    qty: int = Field(gt=0)


class ProviderRefundCreate(BaseModel):
    batch_id: int
    refund_date: date | None = None
    items: list[ProviderRefundItemIn] = Field(min_length=1)

    @field_validator("refund_date")
    @classmethod
    def _check_date(cls, v: date | None) -> date | None:
        return validate_business_date(v)


class ProviderRefundRead(ORMModel):
    id: int
    batch_item_id: int
    qty: int
    refund_amount: Decimal
    refund_date: date


class ClientRefundItemIn(BaseModel):
    order_item_id: int
    qty: int = Field(gt=0)


class ClientRefundCreate(BaseModel):
    refund_date: date | None = None
    items: list[ClientRefundItemIn] = Field(min_length=1)

    @field_validator("refund_date")
    @classmethod
    def _check_date(cls, v: date | None) -> date | None:
        return validate_business_date(v)


class ClientRefundRead(ORMModel):
    id: int
    order_item_id: int
    qty: int
    refund_amount: Decimal
    refund_date: date
