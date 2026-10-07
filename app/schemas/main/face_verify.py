from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FaceEnrollRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    employee_code: str = Field(..., min_length=6, max_length=6)
    image_data_url: str = Field(..., min_length=100)
    created_by: str | None = Field(default=None, max_length=6)


class FaceEnrollResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    employee_code: str
    profile_image_path: str
    profile_image_updated_at: datetime | None = None


class EmployeeLookupResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    employee_code: str
    first_name: str
    last_name: str
    email: str | None = None
    role_name: str
    name_prefix: str
    field_id: int | None = None
    field_name: str | None = None
    position_id: int | None = None
    position_name: str
    department_id: int | None = None
    department_name: str | None = None
    division_id: int | None = None
    division_name: str | None = None
    route_id: int | None = None
    route_name: str | None = None
    has_face_profile: bool

class FaceVerifyRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    employee_code: str = Field(..., min_length=6, max_length=6)
    image_data_url: str = Field(..., min_length=100)


class FaceVerifyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    is_match: bool
    message: str
    score: float | None = None
    threshold: float | None = None
