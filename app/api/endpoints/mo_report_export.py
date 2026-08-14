from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query, Response, status
from sqlalchemy.orm import Session

from app.core.db.session import get_db
from app.schemas.mo_report_export import (
    MoReportExportAction,
    MoReportExportCreate,
    MoReportExportJobStatus,
    MoReportExportResponse,
    MoReportExportType,
)
from app.services.pdf.mo_report_pdf_export import MoReportPdfExport

router = APIRouter()


@router.post(
    "/",
    response_model=MoReportExportResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def queue_mo_report_export(
    payload: MoReportExportCreate,
    db: Session = Depends(get_db),
) -> MoReportExportResponse:
    return MoReportPdfExport.queue_mo_report_export(
        db=db,
        payload=payload,
    )


@router.get(
    "/",
    response_model=list[MoReportExportResponse],
    status_code=status.HTTP_200_OK,
)
def get_mo_report_exports(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    requested_by: str | None = Query(default=None, min_length=1, max_length=6),
    job_status: MoReportExportJobStatus | None = Query(default=None),
    report_type: MoReportExportType | None = Query(default=None),
    include_deleted: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> list[MoReportExportResponse]:
    return MoReportPdfExport.get_mo_report_exports(
        db=db,
        skip=skip,
        limit=limit,
        requested_by=requested_by,
        job_status=job_status,
        report_type=report_type,
        include_deleted=include_deleted,
    )


@router.get(
    "/{export_job_id}",
    response_model=MoReportExportResponse,
    status_code=status.HTTP_200_OK,
)
def get_mo_report_export(
    export_job_id: int = Path(..., gt=0),
    include_deleted: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> MoReportExportResponse:
    return MoReportPdfExport.get_mo_report_export(
        db=db,
        export_job_id=export_job_id,
        include_deleted=include_deleted,
    )


@router.get(
    "/{export_job_id}/download",
    status_code=status.HTTP_200_OK,
)
def download_mo_report_export(
    export_job_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
) -> Response:
    return MoReportPdfExport.download_mo_report_export(
        db=db,
        export_job_id=export_job_id,
    )


@router.patch(
    "/{export_job_id}/cancel",
    response_model=MoReportExportResponse,
    status_code=status.HTTP_200_OK,
)
def cancel_mo_report_export(
    payload: MoReportExportAction,
    export_job_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
) -> MoReportExportResponse:
    return MoReportPdfExport.cancel_mo_report_export(
        db=db,
        export_job_id=export_job_id,
        updated_by=payload.updated_by,
    )


@router.post(
    "/{export_job_id}/retry",
    response_model=MoReportExportResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def retry_mo_report_export(
    payload: MoReportExportAction,
    export_job_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
) -> MoReportExportResponse:
    return MoReportPdfExport.retry_mo_report_export(
        db=db,
        export_job_id=export_job_id,
        updated_by=payload.updated_by,
    )


@router.patch(
    "/{export_job_id}/delete",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_mo_report_export(
    payload: MoReportExportAction,
    export_job_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
) -> None:
    MoReportPdfExport.delete_mo_report_export(
        db=db,
        export_job_id=export_job_id,
        updated_by=payload.updated_by,
    )
