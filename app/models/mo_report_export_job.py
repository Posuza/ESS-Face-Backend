from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.orm import Base


class MoReportExportJob(Base):
    """Queue and history table for MO report PDF export jobs."""

    __tablename__ = "mo_report_export_job"

    __table_args__ = (
        CheckConstraint(
            """
            report_type IN (
                'mo_summary_report',
                'mo_division_report'
            )
            """,
            name="ck_mo_report_export_job_type",
        ),
        CheckConstraint(
            """
            job_status IN (
                'queued',
                'processing',
                'completed',
                'failed',
                'cancelled',
                'expired'
            )
            """,
            name="ck_mo_report_export_job_status",
        ),
        CheckConstraint(
            "progress_current >= 0",
            name="ck_mo_report_export_job_progress_current",
        ),
        CheckConstraint(
            "progress_total >= 0",
            name="ck_mo_report_export_job_progress_total",
        ),
        CheckConstraint(
            "progress_total = 0 OR progress_current <= progress_total",
            name="ck_mo_report_export_job_progress_range",
        ),
        CheckConstraint(
            "file_size_bytes IS NULL OR file_size_bytes >= 0",
            name="ck_mo_report_export_job_file_size",
        ),
        Index(
            "ix_mo_report_export_job_worker_queue",
            "job_status",
            "mark_flag",
            "created_at",
        ),
        Index(
            "ix_mo_report_export_job_requested_by_history",
            "requested_by",
            "mark_flag",
            "created_at",
        ),
    )

    mo_report_export_job_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    report_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="mo_division_report",
        server_default=text("'mo_division_report'"),
    )

    filters_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
    )

    include_images: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("0"),
    )

    job_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="queued",
        server_default=text("'queued'"),
    )

    progress_current: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )

    progress_total: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )

    file_relative_path: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    download_filename: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    file_size_bytes: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        index=True,
    )

    requested_by: Mapped[str] = mapped_column(
        String(6),
        ForeignKey("employees.employee_code"),
        nullable=False,
        index=True,
    )

    updated_by: Mapped[str | None] = mapped_column(
        String(6),
        ForeignKey("employees.employee_code"),
        nullable=True,
        index=True,
    )

    mark_flag: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("0"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    )
