from __future__ import annotations

from datetime import datetime

from ipaddress import ip_address

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.auth.auth import EmployeeInfo

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
    allowed_callback_origin: str = Field(..., min_length=8, max_length=2048)
    public_key: str | None = Field(
        default=None,
        pattern=CLIENT_PUBLIC_KEY_PATTERN,
    )
    private_key: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
        pattern=r"^[A-Za-z0-9_-]{64}$",
    )

    @model_validator(mode="after")
    def require_complete_key_pair(self) -> "AppRegistrationCreate":
        if (self.public_key is None) != (self.private_key is None):
            raise ValueError("Public and private keys must be provided together.")
        return self


class AppRegistrationCreated(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    app_registration_id: int
    app_name: str
    public_key: str
    allowed_callback_origin: str
    is_active: bool
    created_at: datetime


class AppRegistrationSummary(AppRegistrationCreated):
    updated_at: datetime
    created_by: str | None = None
    updated_by: str | None = None


class AppRegistrationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    app_name: str | None = Field(default=None, min_length=1, max_length=150)
    allowed_callback_origin: str | None = Field(
        default=None,
        min_length=8,
        max_length=2048,
    )
    is_active: bool | None = None
    public_key: str | None = Field(
        default=None,
        pattern=CLIENT_PUBLIC_KEY_PATTERN,
    )
    private_key: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
        pattern=r"^[A-Za-z0-9_-]{64}$",
    )

    @model_validator(mode="after")
    def require_change(self) -> "AppRegistrationUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one application setting is required.")
        if ("public_key" in self.model_fields_set) != ("private_key" in self.model_fields_set):
            raise ValueError("Public and private keys must be updated together.")
        return self


class AppSigningKeyRotated(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str
    updated_at: datetime


class AppSigningKeyReveal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    private_key: str


class AppKeyPair(BaseModel):
    model_config = ConfigDict(extra="forbid")

    public_key: str
    private_key: str


class ClientIpBlockCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    ip_address: str = Field(..., min_length=3, max_length=45)
    duration_minutes: int = Field(default=15, ge=1, le=1440)
    reason: str = Field(..., min_length=2, max_length=255)

    @field_validator("ip_address")
    @classmethod
    def validate_ip_address(cls, value: str) -> str:
        try:
            return str(ip_address(value))
        except ValueError as exc:
            raise ValueError("A valid IPv4 or IPv6 address is required.") from exc


class BlockedClientIpSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ip_address: str
    failure_count: int
    window_started_at: datetime
    blocked_until: datetime | None
    reason: str | None
    updated_at: datetime
    is_blocked: bool
    retry_after_seconds: int


class ClientPasswordTicketRequest(ClientPasswordLoginRequest):
    public_key: str = Field(
        ..., min_length=16, max_length=16, pattern=CLIENT_PUBLIC_KEY_PATTERN
    )
    return_to: str = Field(..., min_length=8, max_length=4096)


class ClientFaceTicketRequest(ClientFaceLoginRequest):
    public_key: str = Field(
        ..., min_length=16, max_length=16, pattern=CLIENT_PUBLIC_KEY_PATTERN
    )
    return_to: str = Field(..., min_length=8, max_length=4096)


class ClientCallbackValidationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    public_key: str = Field(
        ..., min_length=16, max_length=16, pattern=CLIENT_PUBLIC_KEY_PATTERN
    )
    return_to: str | None = Field(default=None, min_length=8, max_length=4096)


class ClientCallbackValidationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valid: bool
    return_to: str


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
