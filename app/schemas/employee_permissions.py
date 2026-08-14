from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class EmployeePermissionBase(BaseModel):
    is_active: bool = True


class EmployeePermissionCreate(EmployeePermissionBase):
    employee_code: str = Field(..., max_length=6)
    permissions_name: str = Field(..., max_length=255)
    created_by: Optional[str] = Field(None, max_length=6)


class EmployeePermissionUpdate(BaseModel):
    is_active: Optional[bool] = None
    updated_by: Optional[str] = Field(None, max_length=6)


class EmployeePermissionResponse(EmployeePermissionBase):
    employee_code: str
    permissions_name: str
    created_by: Optional[str]
    updated_by: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
