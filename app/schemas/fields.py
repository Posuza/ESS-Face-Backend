from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class FieldBase(BaseModel):
    field_name: str = Field(..., max_length=150)
    is_active: bool = True
    created_by: str = Field(..., max_length=6)


class FieldCreate(FieldBase):
    pass


class FieldUpdate(BaseModel):
    field_name: Optional[str] = Field(None, max_length=150)
    is_active: Optional[bool] = None
    updated_by: str = Field(..., max_length=6)


class FieldResponse(FieldBase):
    field_id: int
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    updated_by: Optional[str]

    model_config = ConfigDict(from_attributes=True)
