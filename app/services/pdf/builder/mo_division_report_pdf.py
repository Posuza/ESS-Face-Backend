from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.services.pdf.builder.util.mo_pdf_common import (
    MoPdfCommon,
    MoReportPdfCancelledError,
)
from app.services.pdf.builder.util.mo_pdf_sections import MoPdfSections
from app.services.pdf.builder.util.mo_pdf_page_layout import MoPdfPageLayout


class MoDivisionReportPdf:
    TITLE = "รายงานประจำวันฝ่ายปฏิบัติการ (รายละเอียดภาค)"

    @classmethod
    def build_pdf(
        cls,
        *,
        output_path: Path,
        filters: Mapping[str, Any],
        rows: list[dict[str, Any]],
        progress_callback: Any = None,
        is_cancelled: Any = None,
    ) -> None:
        reportlab = MoPdfCommon.import_reportlab()
        fonts = MoPdfCommon.register_fonts(reportlab)
        styles = MoPdfCommon.build_styles(reportlab, fonts)
        doc, canvasmaker = MoPdfPageLayout.make_document(
            reportlab=reportlab,
            output_path=output_path,
            fonts=fonts,
            header_title=cls.TITLE,
            header_subtitle=cls.header_subtitle(rows),
            first_page_suffix=cls.header_date_suffix(rows),
        )

        story: list[Any] = []
        story.extend(
            cls.build_story(
                reportlab=reportlab,
                styles=styles,
                rows=rows,
                progress_callback=progress_callback,
                is_cancelled=is_cancelled,
            )
        )

        doc.build(story, canvasmaker=canvasmaker)
        if progress_callback:
            progress_callback(len(rows), len(rows))

    @staticmethod
    def header_subtitle(rows: list[dict[str, Any]]) -> str:
        first = rows[0] if rows else {}
        parts = [
            str(first.get("department_name") or ""),
            str(first.get("division_name") or ""),
        ]
        return " | ".join(part for part in parts if part)

    @staticmethod
    def header_date_suffix(rows: list[dict[str, Any]]) -> str:
        first = rows[0] if rows else {}
        return MoPdfCommon.format_report_round_date(first.get("report_date") or first.get("created_at"))

    @staticmethod
    def build_story(
        *,
        reportlab: Mapping[str, Any],
        styles: Mapping[str, Any],
        rows: list[dict[str, Any]],
        progress_callback: Any = None,
        is_cancelled: Any = None,
    ) -> list[Any]:
        story: list[Any] = []
        total = len(rows)
        for index, row in enumerate(rows, start=1):
            if is_cancelled and is_cancelled():
                raise MoReportPdfCancelledError("MO report PDF export was cancelled.")
            if progress_callback:
                progress_callback(index - 1, total)

            story.extend(MoPdfSections.division_section(reportlab, styles, row))
            detail_story = MoPdfSections.detail_section(reportlab, styles, row)
            if detail_story:
                story.append(reportlab["PageBreak"]())
                story.extend(detail_story)
            if index != total:
                story.append(reportlab["PageBreak"]())
        return story
