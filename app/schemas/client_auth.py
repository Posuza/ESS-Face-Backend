from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.auth import EmployeeInfo

CLIENT_PUBLIC_KEY_PATTERN = r"^[A-Za-z0-9_-]{16}$"


class ClientPasswordLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    employee_code: str = Field(..., min_length=6, max_length=6)
    password: str = Field(..., min_length=6, max_length=6)


class ClientFaceLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    employee_code: str = Field(..., min_length=6, max_length=6)
    image_data_url: str = Field(..., min_length=100)


class ClientAuthProfile(EmployeeInfo):
    model_config = ConfigDict(extra="forbid")


class ClientPasswordLoginResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    employee: ClientAuthProfile
    message: str


class ClientFaceLoginResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    is_match: bool
    message: str
    employee: ClientAuthProfile | None = None
    score: float | None = None
    threshold: float | None = None


class ClientFacePasswordRecoveryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    is_match: bool
    message: str
    password: str | None = None
    score: float | None = None
    threshold: float | None = None


class AppRegistrationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    app_name: str = Field(..., min_length=1, max_length=150)


class AppRegistrationCreated(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    app_registration_id: int
    app_name: str
    public_key: str
    is_active: bool
    created_at: datetime


class ClientPasswordTicketRequest(ClientPasswordLoginRequest):
    public_key: str = Field(
        ..., min_length=16, max_length=16, pattern=CLIENT_PUBLIC_KEY_PATTERN
    )


class ClientFaceTicketRequest(ClientFaceLoginRequest):
    public_key: str = Field(
        ..., min_length=16, max_length=16, pattern=CLIENT_PUBLIC_KEY_PATTERN
    )


class ClientTicketIssued(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket: str


class ClientTicketVerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    public_key: str = Field(
        ..., min_length=16, max_length=16, pattern=CLIENT_PUBLIC_KEY_PATTERN
    )
    ticket: str = Field(..., min_length=32, max_length=4096)


class ClientTicketVerifyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    employee_id: str


class ClientLogoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    public_key: str = Field(
        ..., min_length=16, max_length=16, pattern=CLIENT_PUBLIC_KEY_PATTERN
    )
    employee_id: str = Field(..., min_length=6, max_length=6)


class ClientLogoutResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str
