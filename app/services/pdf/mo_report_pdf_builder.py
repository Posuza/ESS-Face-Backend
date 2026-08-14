from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping

from sqlalchemy.orm import Session

from app.services.pdf.builder.mo_division_report_pdf import MoDivisionReportPdf
from app.services.pdf.builder.mo_summary_report_pdf import MoSummaryReportPdf
from app.services.pdf.builder.util.mo_pdf_common import (
    MoReportPdfBuildError,
    MoReportPdfCancelledError,
    MoReportPdfNoDataError,
)
from app.services.pdf.builder.util.mo_pdf_data_loader import MoPdfDataLoader


@dataclass(frozen=True)
class MoReportPdfBuildResult:
    """Metadata the worker stores after a successful PDF build."""

    download_filename: str
    file_size_bytes: int
    report_row_count: int


ProgressCallback = Callable[[int, int], None]
CancelledCallback = Callable[[], bool]


class MoReportPdfBuilder:
    """
    Stable facade for MO PDF generation.

    Layout-specific logic lives in app/services/pdf/builder so summary and
    division PDFs can evolve independently while workers keep one import path.
    """

    REPORT_TYPE_SUMMARY = "mo_summary_report"
    REPORT_TYPE_DIVISION = "mo_division_report"

    @classmethod
    def build_mo_report_pdf(
        cls,
        *,
        db: Session,
        filters: Mapping[str, Any] | None,
        output_path: Path,
        report_type: str = REPORT_TYPE_DIVISION,
        progress_callback: ProgressCallback | None = None,
        is_cancelled: CancelledCallback | None = None,
    ) -> MoReportPdfBuildResult:
        if report_type not in {cls.REPORT_TYPE_SUMMARY, cls.REPORT_TYPE_DIVISION}:
            raise MoReportPdfBuildError(f"Unsupported MO report type: {report_type}")

        if is_cancelled and is_cancelled():
            raise MoReportPdfCancelledError("MO report PDF export was cancelled.")

        filters_data = filters or {}
        rows = MoPdfDataLoader.load_rows(db=db, filters=filters_data)
        if not rows:
            raise MoReportPdfNoDataError("No MO reports matched the export filters.")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        if report_type == cls.REPORT_TYPE_SUMMARY:
            MoSummaryReportPdf.build_pdf(
                output_path=output_path,
                filters=filters_data,
                rows=rows,
                progress_callback=progress_callback,
            )
        else:
            MoDivisionReportPdf.build_pdf(
                output_path=output_path,
                filters=filters_data,
                rows=rows,
                progress_callback=progress_callback,
                is_cancelled=is_cancelled,
            )

        return MoReportPdfBuildResult(
            download_filename=cls._build_download_filename(rows, report_type),
            file_size_bytes=output_path.stat().st_size,
            report_row_count=len(rows),
        )

    @classmethod
    def _build_download_filename(
        cls,
        rows: list[dict[str, Any]],
        report_type: str,
    ) -> str:
        first = rows[0] if rows else {}
        raw_date = first.get("report_date") or first.get("created_at")
        date_text = cls._filename_date(raw_date) or datetime.now().strftime("%d%m%y")
        scope_text = cls._filename_scope(rows=rows, report_type=report_type)
        return f"รายงานประจำวันฝ่ายปฏิบัติการ_{scope_text}_{date_text}.pdf"

    @staticmethod
    def _filename_scope(
        *,
        rows: list[dict[str, Any]],
        report_type: str,
    ) -> str:
        # Same name for both report types as the frontend (PdfViewer.tsx):
        # รายงานประจำวันฝ่ายปฏิบัติการ_{sector}_{ddMMyy}.pdf — sector only,
        # no division name. Kept as a separate helper in case a report type
        # ever needs its own scope in the filename.
        first = rows[0] if rows else {}
        department_name = str(
            first.get("department_name") or first.get("department_id") or "MO",
        ).strip()
        return MoReportPdfBuilder._filename_part(department_name)

    @staticmethod
    def _filename_date(value: Any) -> str:
        if value in (None, ""):
            return ""
        if isinstance(value, datetime):
            parsed = value
        else:
            raw_text = str(value)
            try:
                parsed = datetime.fromisoformat(raw_text.replace("Z", "+00:00"))
            except ValueError:
                try:
                    parsed = datetime.strptime(raw_text[:10], "%Y-%m-%d")
                except ValueError:
                    return ""
        return f"{parsed.day:02d}{parsed.month:02d}{str(parsed.year)[-2:]}"

    @staticmethod
    def _filename_part(value: str) -> str:
        normalized = "_".join(str(value).strip().split())
        return "".join(ch for ch in normalized if ch not in '/\\:*?"<>|') or "MO"
