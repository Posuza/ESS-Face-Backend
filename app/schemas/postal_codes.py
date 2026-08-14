from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class PostalCodeBase(BaseModel):
    postal_code: str = Field(..., max_length=6)
    sub_district_id: int
    created_by: str = Field(..., max_length=6)


class PostalCodeCreate(PostalCodeBase):
    pass


class PostalCodeUpdate(BaseModel):
    postal_code: Optional[str] = Field(None, max_length=6)
    sub_district_id: Optional[int] = None
    updated_by: str = Field(..., max_length=6)


class PostalCodeResponse(PostalCodeBase):
    postal_code_id: int
    created_at: datetime
    updated_at: datetime
    updated_by: Optional[str]

    model_config = ConfigDict(from_attributes=True)
