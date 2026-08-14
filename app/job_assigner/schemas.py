from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

JobStatus = Literal[
    "NEW",
    "ASSIGNED",
    "ACCEPTED",
    "IN_PROGRESS",
    "ON_HOLD",
    "COMPLETED",
    "CLOSED",
    "REJECTED",
]
JobPriority = Literal["LOW", "MEDIUM", "HIGH", "URGENT"]
JobAction = Literal[
    "ASSIGN",
    "REASSIGN",
    "ACCEPT",
    "REJECT",
    "START",
    "HOLD",
    "RESUME",
    "COMPLETE",
    "CLOSE",
    "REOPEN",
]


class JobCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    assigned_to: str | None = Field(default=None, min_length=1, max_length=6)
    priority: JobPriority = "MEDIUM"
    due_date: datetime | None = None


class JobTransitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    action: JobAction
    assigned_to: str | None = Field(default=None, min_length=1, max_length=6)
    comment: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_assignment(self) -> "JobTransitionRequest":
        if self.action in {"ASSIGN", "REASSIGN"} and not self.assigned_to:
            raise ValueError("assigned_to is required for assignment actions")
        return self


class JobWorkflowHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    from_status: str | None
    to_status: str
    action: str
    changed_by: str
    assigned_from: str | None
    assigned_to: str | None
    comment: str | None
    created_at: datetime


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    assigned_to: str | None
    assigned_by: str | None
    workflow_status: str
    priority: str
    due_date: datetime | None
    created_by: str
    created_at: datetime
    updated_at: datetime


class JobDetailResponse(JobResponse):
    history: list[JobWorkflowHistoryResponse] = Field(default_factory=list)


class WorkflowDefinitionResponse(BaseModel):
    transitions: dict[str, dict[str, str]]
