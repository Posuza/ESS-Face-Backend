from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class AddressBase(BaseModel):
    address_detail: str = Field(..., max_length=225)
    sub_district_id: int
    district_id: int
    province_id: int
    postal_code_id: int
    is_active: bool = True
    created_by: str = Field(..., max_length=6)


class AddressCreate(AddressBase):
    pass


class AddressUpdate(BaseModel):
    address_detail: Optional[str] = Field(None, max_length=225)
    sub_district_id: Optional[int] = None
    district_id: Optional[int] = None
    province_id: Optional[int] = None
    postal_code_id: Optional[int] = None
    is_active: Optional[bool] = None
    updated_by: str = Field(..., max_length=6)


class AddressResponse(AddressBase):
    address_id: int
    created_at: datetime
    updated_at: datetime
    updated_by: Optional[str]

    model_config = ConfigDict(from_attributes=True)
