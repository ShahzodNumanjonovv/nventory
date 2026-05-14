from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class OrderProductIn(BaseModel):
    id: int = Field(description="Product ID")
    qty: int = Field(gt=0, description="Quantity ordered")


class OrderCreate(BaseModel):
    client_id: int
    products: list[OrderProductIn] = Field(min_length=1)


class OrderItemRead(ORMModel):
    id: int
    batch_item_id: int
    qty: int
    sell_price: Decimal


class OrderRead(ORMModel):
    id: int
    client_id: int
    order_date: date
    items: list[OrderItemRead]


class AvailableProduct(BaseModel):
    id: int
    name: str
    category_name: str
    price: Decimal
    qty: int
