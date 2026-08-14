from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class SubDistrictBase(BaseModel):
    sub_district_name: str = Field(..., max_length=225)
    province_id: int
    district_id: int
    created_by: Optional[str] = Field(None, max_length=6)


class SubDistrictCreate(SubDistrictBase):
    pass


class SubDistrictUpdate(BaseModel):
    sub_district_name: Optional[str] = Field(None, max_length=225)
    province_id: Optional[int] = None
    district_id: Optional[int] = None
    updated_by: Optional[str] = Field(None, max_length=6)


class SubDistrictResponse(SubDistrictBase):
    sub_district_id: int
    created_at: datetime
    updated_at: datetime
    updated_by: Optional[str]

    model_config = ConfigDict(from_attributes=True)
