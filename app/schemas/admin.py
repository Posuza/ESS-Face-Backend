from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class AdminEmployeeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    employee_code: str = Field(..., min_length=6, max_length=6, pattern=r"^[A-Za-z0-9]{6}$")
    password: str = Field(..., min_length=6, max_length=6)
    role_id: int
    name_prefix_id: int
    first_name: str = Field(..., min_length=1, max_length=150)
    last_name: str = Field(..., min_length=1, max_length=150)
    birth_date: date
    email: EmailStr | None = None
    phone_number: str | None = Field(None, max_length=10)
    address_id: int | None = None
    field_id: int | None = None
    department_id: int | None = None
    division_id: int | None = None
    position_id: int | None = None
    routes_id: int | None = None
    shift_id: int | None = None
    is_active: bool = True
    start_date: date | None = None
    leave_date: date | None = None


class AdminEmployeeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    role_id: int | None = None
    name_prefix_id: int | None = None
    first_name: str | None = Field(None, min_length=1, max_length=150)
    last_name: str | None = Field(None, min_length=1, max_length=150)
    birth_date: date | None = None
    email: EmailStr | None = None
    phone_number: str | None = Field(None, max_length=10)
    address_id: int | None = None
    field_id: int | None = None
    department_id: int | None = None
    division_id: int | None = None
    position_id: int | None = None
    routes_id: int | None = None
    shift_id: int | None = None
    is_active: bool | None = None
    start_date: date | None = None
    leave_date: date | None = None


class AdminPasswordReset(BaseModel):
    model_config = ConfigDict(extra="forbid")
    password: str = Field(..., min_length=6, max_length=6)


class AdminEmployeeResponse(BaseModel):
    employee_code: str
    role_id: int
    role_name: str | None = None
    name_prefix_id: int
    name_prefix: str | None = None
    first_name: str
    last_name: str
    birth_date: date
    email: str | None = None
    phone_number: str | None = None
    address_id: int | None = None
    field_id: int | None = None
    department_id: int | None = None
    division_id: int | None = None
    position_id: int | None = None
    routes_id: int | None = None
    shift_id: int | None = None
    is_active: bool
    start_date: date | None = None
    leave_date: date | None = None
    has_face_profile: bool
    profile_image_updated_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AdminEmployeeListResponse(BaseModel):
    items: list[AdminEmployeeResponse]
    total: int
    page: int
    page_size: int


class ModelSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    active: bool | None = None
    settings_values: dict[str, int | float] = Field(default_factory=dict)


class ModelSettingsReset(BaseModel):
    model_config = ConfigDict(extra="forbid")
    group: str | None = None
    model_key: str | None = None


class ModelSettingsDocument(BaseModel):
    model_config = ConfigDict(extra="allow")
    model_schemas: dict[str, list[dict[str, Any]]]
