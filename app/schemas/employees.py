from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class EmployeeBase(BaseModel):
    password: str = Field(..., max_length=6)
    role_id: int
    name_prefix_id: int
    first_name: str = Field(..., max_length=150)
    last_name: str = Field(..., max_length=150)
    profile_image_path: Optional[str] = None
    birth_date: date
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = Field(None, max_length=10)
    address_id: Optional[int] = None
    field_id: Optional[int] = None
    department_id: Optional[int] = None
    division_id: Optional[int] = None
    position_id: Optional[int] = None
    routes_id: Optional[int] = None
    shift_id: Optional[int] = None
    is_active: bool = True
    start_date: Optional[date] = None
    leave_date: Optional[date] = None
    created_by: str = Field(..., max_length=6)


class EmployeeCreate(EmployeeBase):
    employee_code: str = Field(..., max_length=6)


class EmployeeUpdate(BaseModel):
    password: Optional[str] = Field(None, max_length=6)
    role_id: Optional[int] = None
    name_prefix_id: Optional[int] = None
    first_name: Optional[str] = Field(None, max_length=150)
    last_name: Optional[str] = Field(None, max_length=150)
    profile_image_path: Optional[str] = None
    birth_date: Optional[date] = None
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = Field(None, max_length=10)
    address_id: Optional[int] = None
    field_id: Optional[int] = None
    department_id: Optional[int] = None
    division_id: Optional[int] = None
    position_id: Optional[int] = None
    routes_id: Optional[int] = None
    shift_id: Optional[int] = None
    is_active: Optional[bool] = None
    start_date: Optional[date] = None
    leave_date: Optional[date] = None
    updated_by: Optional[str] = Field(None, max_length=6)


class EmployeeResponse(EmployeeBase):
    employee_code: str
    profile_image_updated_at: Optional[datetime]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    updated_by: Optional[str]

    model_config = ConfigDict(from_attributes=True)
