from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class AuditLogCreate(BaseModel):
    employee_code: Optional[str] = Field(None, max_length=6)
    user_name: str = Field(..., max_length=150)
    ip_address: str = Field(..., max_length=512)
    action: str


class AuditLogRead(AuditLogCreate):
    model_config = ConfigDict(from_attributes=True)

    log_id: int
    timestamp: datetime


class AuditLogListResponse(BaseModel):
    total: int
    items: list[AuditLogRead]
