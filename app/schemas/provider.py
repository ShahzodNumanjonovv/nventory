from pydantic import BaseModel, Field

from app.schemas.common import TimestampedRead


class ProviderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class ProviderRead(TimestampedRead):
    name: str
