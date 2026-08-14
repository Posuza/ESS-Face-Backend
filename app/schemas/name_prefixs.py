from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class NamePrefixBase(BaseModel):
    prefix_name: str = Field(..., max_length=50)
    is_active: bool = True
    created_by: str = Field(..., max_length=6)


class NamePrefixCreate(NamePrefixBase):
    pass


class NamePrefixUpdate(BaseModel):
    prefix_name: Optional[str] = Field(None, max_length=50)
    is_active: Optional[bool] = None
    updated_by: str = Field(..., max_length=6)


class NamePrefixResponse(NamePrefixBase):
    prefix_id: int
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    updated_by: Optional[str]

    model_config = ConfigDict(from_attributes=True)
