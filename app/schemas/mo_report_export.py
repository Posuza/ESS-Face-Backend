from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator


MoReportExportType = Literal[
    "mo_summary_report",
    "mo_division_report",
]

MoReportExportJobStatus = Literal[
    "queued",
    "processing",
    "completed",
    "failed",
    "cancelled",
    "expired",
]


class MoReportExportFilter(BaseModel):
    """
    Filters captured when the user queues an MO PDF export.

    The worker uses these filters to read fresh MO data from the database.
    Frontend should not send full report rows into the export job.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    mo_daily_transaction_ids: list[int] = Field(default_factory=list)
    department_id: int | None = Field(default=None, gt=0)
    division_id: int | None = Field(default=None, gt=0)
    start_date: datetime | None = None
    end_date: datetime | None = None
    status: str | None = None
    created_by: str | None = Field(default=None, min_length=1, max_length=6)

    @model_validator(mode="after")
    def validate_filter_shape(self) -> "MoReportExportFilter":
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be greater than or equal to start_date")
        return self


class MoReportExportCreate(BaseModel):
    """Request for POST /mo-report-exports/."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    report_type: MoReportExportType = "mo_division_report"
    filters: MoReportExportFilter
    requested_by: str = Field(..., min_length=1, max_length=6)


class MoReportExportAction(BaseModel):
    """Request body for cancel / retry / delete actions."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    updated_by: str = Field(..., min_length=1, max_length=6)


class MoReportExportResponse(BaseModel):
    """Response for queue, poll, history, cancel, retry, and delete actions."""

    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
        str_strip_whitespace=True,
    )

    mo_report_export_job_id: int
    report_type: MoReportExportType

    filters_json: dict[str, Any]

    include_images: bool
    job_status: MoReportExportJobStatus

    progress_current: int = Field(ge=0)
    progress_total: int = Field(ge=0)

    file_relative_path: str | None = None
    download_filename: str | None = None
    file_size_bytes: int | None = Field(default=None, ge=0)

    error_message: str | None = None

    started_at: datetime | None = None
    completed_at: datetime | None = None
    expires_at: datetime | None = None

    requested_by: str
    updated_by: str | None = None

    mark_flag: bool

    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def progress_percent(self) -> int:
        if self.job_status == "completed":
            return 100

        if self.progress_total <= 0:
            return 0

        return min(100, max(0, int((self.progress_current / self.progress_total) * 100)))

    @computed_field
    @property
    def download_ready(self) -> bool:
        return (
            self.job_status == "completed"
            and bool(self.file_relative_path)
            and bool(self.download_filename)
        )
