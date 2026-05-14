from pydantic import BaseModel, Field

from app.schemas.common import TimestampedRead


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    category_id: int


class ProductRead(TimestampedRead):
    name: str
    category_id: int
