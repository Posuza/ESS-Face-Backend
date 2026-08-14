from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import exists, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.employees import Employee
from app.models.mo_report_export_job import MoReportExportJob
from app.schemas.mo_report_export import (
    MoReportExportCreate,
    MoReportExportJobStatus,
    MoReportExportResponse,
)


class MoReportPdfExport:
    """
    Manage MO report export jobs.

    This service queues jobs, reads status/history, soft-deletes jobs, and returns
    completed PDF files. The worker creates the actual PDF file separately.
    """

    REPORT_TYPE_SUMMARY = "mo_summary_report"
    REPORT_TYPE_DIVISION = "mo_division_report"

    STATUS_QUEUED = "queued"
    STATUS_PROCESSING = "processing"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CANCELLED = "cancelled"
    STATUS_EXPIRED = "expired"

    CANCELLABLE_STATUSES = {
        STATUS_QUEUED,
        STATUS_PROCESSING,
    }

    RETRYABLE_STATUSES = {
        STATUS_FAILED,
        STATUS_EXPIRED,
    }

    DELETABLE_STATUSES = {
        STATUS_COMPLETED,
        STATUS_FAILED,
        STATUS_CANCELLED,
        STATUS_EXPIRED,
    }

    REPORT_EXPORT_ROOT_ENV = "REPORT_EXPORT_ROOT"

    @staticmethod
    def queue_mo_report_export(
        *,
        db: Session,
        payload: MoReportExportCreate,
    ) -> MoReportExportResponse:
        MoReportPdfExport._ensure_employee_exists(
            db=db,
            employee_code=payload.requested_by,
        )

        export_job = MoReportExportJob(
            report_type=payload.report_type,
            filters_json=payload.filters.model_dump(mode="json", exclude_none=True),
            include_images=False,
            job_status=MoReportPdfExport.STATUS_QUEUED,
            progress_current=0,
            progress_total=0,
            requested_by=payload.requested_by,
            mark_flag=False,
        )

        try:
            db.add(export_job)
            db.commit()
            db.refresh(export_job)
        except SQLAlchemyError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error while creating MO report export job",
            ) from exc

        return MoReportExportResponse.model_validate(export_job)

    @staticmethod
    def get_mo_report_exports(
        *,
        db: Session,
        skip: int,
        limit: int,
        requested_by: str | None,
        job_status: MoReportExportJobStatus | None,
        report_type: str | None,
        include_deleted: bool,
    ) -> list[MoReportExportResponse]:
        statement = select(MoReportExportJob)

        if not include_deleted:
            statement = statement.where(MoReportExportJob.mark_flag.is_(False))

        if requested_by:
            statement = statement.where(MoReportExportJob.requested_by == requested_by)

        if job_status:
            statement = statement.where(MoReportExportJob.job_status == job_status)

        if report_type:
            statement = statement.where(MoReportExportJob.report_type == report_type)

        statement = (
            statement.order_by(MoReportExportJob.created_at.desc())
            .offset(skip)
            .limit(limit)
        )

        export_jobs = list(db.scalars(statement))
        return [MoReportExportResponse.model_validate(export_job) for export_job in export_jobs]

    @staticmethod
    def get_mo_report_export(
        *,
        db: Session,
        export_job_id: int,
        include_deleted: bool,
    ) -> MoReportExportResponse:
        export_job = MoReportPdfExport._get_export_job_or_404(
            db=db,
            export_job_id=export_job_id,
            include_deleted=include_deleted,
        )
        return MoReportExportResponse.model_validate(export_job)

    @staticmethod
    def download_mo_report_export(
        *,
        db: Session,
        export_job_id: int,
    ) -> FileResponse:
        export_job = MoReportPdfExport._get_export_job_or_404(
            db=db,
            export_job_id=export_job_id,
            include_deleted=False,
        )

        if export_job.job_status != MoReportPdfExport.STATUS_COMPLETED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="MO report export job is not ready for download",
            )

        if export_job.expires_at is not None and export_job.expires_at <= datetime.now():
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="MO report export file has expired",
            )

        if not export_job.file_relative_path or not export_job.download_filename:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="MO report export file was not found",
            )

        file_path = MoReportPdfExport._resolve_export_file_path(
            export_job.file_relative_path,
        )

        if not file_path.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="MO report export file was not found",
            )

        return FileResponse(
            path=file_path,
            media_type="application/pdf",
            filename=export_job.download_filename,
        )

    @staticmethod
    def cancel_mo_report_export(
        *,
        db: Session,
        export_job_id: int,
        updated_by: str,
    ) -> MoReportExportResponse:
        MoReportPdfExport._ensure_employee_exists(
            db=db,
            employee_code=updated_by,
        )

        export_job = MoReportPdfExport._get_export_job_or_404(
            db=db,
            export_job_id=export_job_id,
            include_deleted=False,
        )

        if export_job.job_status not in MoReportPdfExport.CANCELLABLE_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="MO report export job cannot be cancelled",
            )

        export_job.job_status = MoReportPdfExport.STATUS_CANCELLED
        export_job.updated_by = updated_by
        export_job.completed_at = datetime.now()
        export_job.error_message = None

        MoReportPdfExport._commit_and_refresh(db=db, export_job=export_job)
        return MoReportExportResponse.model_validate(export_job)

    @staticmethod
    def retry_mo_report_export(
        *,
        db: Session,
        export_job_id: int,
        updated_by: str,
    ) -> MoReportExportResponse:
        MoReportPdfExport._ensure_employee_exists(
            db=db,
            employee_code=updated_by,
        )

        export_job = MoReportPdfExport._get_export_job_or_404(
            db=db,
            export_job_id=export_job_id,
            include_deleted=False,
        )

        if export_job.job_status not in MoReportPdfExport.RETRYABLE_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="MO report export job cannot be retried",
            )

        export_job.job_status = MoReportPdfExport.STATUS_QUEUED
        export_job.progress_current = 0
        export_job.progress_total = 0
        export_job.file_relative_path = None
        export_job.download_filename = None
        export_job.file_size_bytes = None
        export_job.error_message = None
        export_job.started_at = None
        export_job.completed_at = None
        export_job.expires_at = None
        export_job.updated_by = updated_by

        MoReportPdfExport._commit_and_refresh(db=db, export_job=export_job)
        return MoReportExportResponse.model_validate(export_job)

    @staticmethod
    def delete_mo_report_export(
        *,
        db: Session,
        export_job_id: int,
        updated_by: str,
    ) -> None:
        MoReportPdfExport._ensure_employee_exists(
            db=db,
            employee_code=updated_by,
        )

        export_job = MoReportPdfExport._get_export_job_or_404(
            db=db,
            export_job_id=export_job_id,
            include_deleted=False,
        )

        if export_job.job_status not in MoReportPdfExport.DELETABLE_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="MO report export job cannot be deleted",
            )

        export_job.mark_flag = True
        export_job.updated_by = updated_by
        MoReportPdfExport._commit_and_refresh(db=db, export_job=export_job)

    @staticmethod
    def _get_export_job_or_404(
        *,
        db: Session,
        export_job_id: int,
        include_deleted: bool,
    ) -> MoReportExportJob:
        statement = select(MoReportExportJob).where(
            MoReportExportJob.mo_report_export_job_id == export_job_id,
        )

        if not include_deleted:
            statement = statement.where(MoReportExportJob.mark_flag.is_(False))

        export_job = db.scalar(statement)
        if export_job is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="MO report export job was not found",
            )
        return export_job

    @staticmethod
    def _ensure_employee_exists(
        *,
        db: Session,
        employee_code: str,
    ) -> None:
        employee_exists = db.scalar(
            select(
                exists().where(
                    Employee.employee_code == employee_code,
                ),
            ),
        )

        if not employee_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Employee not found",
            )

    @staticmethod
    def _commit_and_refresh(
        *,
        db: Session,
        export_job: MoReportExportJob,
    ) -> None:
        try:
            db.commit()
            db.refresh(export_job)
        except SQLAlchemyError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error while updating MO report export job",
            ) from exc

    @staticmethod
    def _resolve_export_file_path(file_relative_path: str) -> Path:
        export_root = MoReportPdfExport._get_export_root()
        candidate_path = (export_root / file_relative_path.lstrip("/\\")).resolve()

        try:
            candidate_path.relative_to(export_root)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="MO report export file was not found",
            ) from exc

        return candidate_path

    @staticmethod
    def _get_export_root() -> Path:
        configured_path = os.getenv(MoReportPdfExport.REPORT_EXPORT_ROOT_ENV, "").strip()
        if configured_path:
            return Path(configured_path).expanduser().resolve()

        return Path(__file__).resolve().parents[3] / "exports"
