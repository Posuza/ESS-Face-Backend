from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ProvinceBase(BaseModel):
    province_name: str = Field(..., max_length=225)
    created_by: str = Field(..., max_length=6)


class ProvinceCreate(ProvinceBase):
    pass


class ProvinceUpdate(BaseModel):
    province_name: Optional[str] = Field(None, max_length=225)
    updated_by: str = Field(..., max_length=6)


class ProvinceResponse(ProvinceBase):
    province_id: int
    created_at: datetime
    updated_at: datetime
    updated_by: Optional[str]

    model_config = ConfigDict(from_attributes=True)
