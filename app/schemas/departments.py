from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class DepartmentBase(BaseModel):
    department_name: str = Field(..., max_length=150)
    field_id: int
    is_active: bool = True
    created_by: str = Field(..., max_length=6)


class DepartmentCreate(DepartmentBase):
    pass


class DepartmentUpdate(BaseModel):
    department_name: Optional[str] = Field(None, max_length=150)
    field_id: Optional[int] = None
    is_active: Optional[bool] = None
    updated_by: str = Field(..., max_length=6)


class DepartmentResponse(DepartmentBase):
    department_id: int
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    updated_by: Optional[str]

    model_config = ConfigDict(from_attributes=True)
