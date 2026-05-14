from pydantic import BaseModel, Field, model_validator

from app.schemas.common import TimestampedRead


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    parent_id: int | None = None
    provider_id: int | None = None

    @model_validator(mode="after")
    def validate_root_xor_child(self) -> "CategoryCreate":
        is_root = self.parent_id is None
        has_provider = self.provider_id is not None
        if is_root and not has_provider:
            raise ValueError("Root category (no parent) must have a provider_id")
        if not is_root and has_provider:
            raise ValueError("Subcategory must not have provider_id (inherited from root)")
        return self


class CategoryRead(TimestampedRead):
    name: str
    parent_id: int | None
    provider_id: int | None
