from pydantic import BaseModel, Field

from app.schemas.common import TimestampedRead


class ClientCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class ClientRead(TimestampedRead):
    name: str
