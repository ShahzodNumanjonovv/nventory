from datetime import date, datetime, timedelta
from typing import Annotated, Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TimestampedRead(ORMModel):
    id: int
    created_at: datetime
    updated_at: datetime


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class PageParams(BaseModel):
    limit: Annotated[int, Query(ge=1, le=500)] = 50
    offset: Annotated[int, Query(ge=0)] = 0


_MIN_BUSINESS_DATE = date(2000, 1, 1)


def validate_business_date(value: date | None) -> date | None:
    """Reject implausible dates — defends against typos like 1900 or 9999."""
    if value is None:
        return None
    today = date.today()
    if value < _MIN_BUSINESS_DATE:
        raise ValueError(f"date {value} is before {_MIN_BUSINESS_DATE}")
    if value > today + timedelta(days=1):
        raise ValueError(f"date {value} is in the future")
    return value
