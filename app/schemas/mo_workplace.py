"""Response schemas for MO workplace hierarchy endpoints."""

from pydantic import BaseModel, ConfigDict


class DivisionResponse(BaseModel):
    division_id: int
    division_name: str
    department_id: int

    model_config = ConfigDict(from_attributes=True)


class DepartmentResponse(BaseModel):
    department_id: int
    department_name: str
    field_id: int

    model_config = ConfigDict(from_attributes=True)
