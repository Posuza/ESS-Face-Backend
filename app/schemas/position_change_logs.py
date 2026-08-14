from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class PositionChangeLogBase(BaseModel):
    employee_code: str = Field(..., max_length=6)
    
    from_field: str = Field(..., max_length=50)
    from_department: str = Field(..., max_length=50)
    from_division: str = Field(..., max_length=50)
    from_route: str = Field(..., max_length=50)
    from_position: str = Field(..., max_length=50)
    from_shift: str = Field(..., max_length=50)

    to_field: str = Field(..., max_length=50)
    to_department: str = Field(..., max_length=50)
    to_division: str = Field(..., max_length=50)
    to_route: str = Field(..., max_length=50)
    to_position: str = Field(..., max_length=50)
    to_shift: str = Field(..., max_length=50)

    transition_type: str = Field(..., max_length=50)
    effective_date: date
    detail: Optional[str] = None
    created_by: str = Field(..., max_length=10)


class PositionChangeLogCreate(PositionChangeLogBase):
    pass


class PositionChangeLogUpdate(BaseModel):
    employee_code: Optional[str] = Field(None, max_length=6)
    
    from_field: Optional[str] = Field(None, max_length=50)
    from_department: Optional[str] = Field(None, max_length=50)
    from_division: Optional[str] = Field(None, max_length=50)
    from_route: Optional[str] = Field(None, max_length=50)
    from_position: Optional[str] = Field(None, max_length=50)
    from_shift: Optional[str] = Field(None, max_length=50)

    to_field: Optional[str] = Field(None, max_length=50)
    to_department: Optional[str] = Field(None, max_length=50)
    to_division: Optional[str] = Field(None, max_length=50)
    to_route: Optional[str] = Field(None, max_length=50)
    to_position: Optional[str] = Field(None, max_length=50)
    to_shift: Optional[str] = Field(None, max_length=50)

    transition_type: Optional[str] = Field(None, max_length=50)
    effective_date: Optional[date] = None
    detail: Optional[str] = None
    created_by: Optional[str] = Field(None, max_length=10)


class PositionChangeLogResponse(PositionChangeLogBase):
    position_log_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
