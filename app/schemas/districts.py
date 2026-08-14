from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class DistrictBase(BaseModel):
    district_name: str = Field(..., max_length=255)
    province_id: int
    created_by: str = Field(..., max_length=6)


class DistrictCreate(DistrictBase):
    pass


class DistrictUpdate(BaseModel):
    district_name: Optional[str] = Field(None, max_length=255)
    province_id: Optional[int] = None
    updated_by: str = Field(..., max_length=6)


class DistrictResponse(DistrictBase):
    district_id: int
    created_at: datetime
    updated_at: datetime
    updated_by: Optional[str]

    model_config = ConfigDict(from_attributes=True)
