from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class StorageRemaining(BaseModel):
    storage_id: int
    storage_name: str
    product_id: int
    product_name: str
    qty: int


class BatchProfit(BaseModel):
    batch_id: int
    provider_id: int
    purchase_date: date
    revenue: Decimal
    cost: Decimal
    profit: Decimal
