from pydantic import BaseModel, Field

from app.schemas.common import TimestampedRead


class StorageCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    location: str | None = Field(default=None, max_length=255)


class StorageRead(TimestampedRead):
    name: str
    location: str | None
