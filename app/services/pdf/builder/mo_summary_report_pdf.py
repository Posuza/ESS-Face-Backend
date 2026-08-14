from __future__ import annotations

import html
from pathlib import Path
from typing import Any, Mapping

from app.services.pdf.builder.util.mo_pdf_common import MoPdfCommon
from app.services.pdf.builder.util.mo_pdf_sections import MoPdfSections
from app.services.pdf.builder.util.mo_pdf_page_layout import MoPdfPageLayout


class MoSummaryReportPdf:
    TITLE = "รายงานประจำวันฝ่ายปฏิบัติการ"

    @classmethod
    def build_pdf(
        cls,
        *,
        output_path: Path,
        filters: Mapping[str, Any],
        rows: list[dict[str, Any]],
        progress_callback: Any = None,
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
        story.extend(cls.build_story(reportlab=reportlab, styles=styles, rows=rows))

        doc.build(story, canvasmaker=canvasmaker)
        if progress_callback:
            progress_callback(len(rows), len(rows))

    @classmethod
    def build_story(
        cls,
        *,
        reportlab: Mapping[str, Any],
        styles: Mapping[str, Any],
        rows: list[dict[str, Any]],
    ) -> list[Any]:
        approved_rows = [
            row for row in rows if str(row.get("approved_status") or row.get("status")) == "APPROVED"
        ]
        summary_rows = approved_rows or rows

        story: list[Any] = []
        story.extend(MoPdfSections.summary_section(reportlab, styles, summary_rows))
        story.append(reportlab["PageBreak"]())

        for index, row in enumerate(summary_rows, start=1):
            # Stamp this division's name onto the canvas so the page header
            # shows it on this division's pages (like the division PDF does).
            division_name = str(row.get("division_name") or "").strip()
            if division_name:
                story.append(MoPdfCommon.division_marker(reportlab, division_name))
            story.extend(MoPdfSections.division_section(reportlab, styles, row))
            detail_story = MoPdfSections.detail_section(reportlab, styles, row)
            if detail_story:
                story.append(reportlab["PageBreak"]())
                story.extend(detail_story)
            if index != len(summary_rows):
                story.append(reportlab["PageBreak"]())
        return story

    @staticmethod
    def scope_text(rows: list[dict[str, Any]]) -> str:
        first = rows[0] if rows else {}
        department_name = first.get("department_name") or "-"
        report_date = first.get("report_date") or "-"
        return f"หน่วยงาน: {html.escape(str(department_name))} | วันที่รายงาน: {html.escape(str(report_date))}"

    @staticmethod
    def header_subtitle(rows: list[dict[str, Any]]) -> str:
        first = rows[0] if rows else {}
        return str(first.get("department_name") or "")

    @staticmethod
    def header_date_suffix(rows: list[dict[str, Any]]) -> str:
        first = rows[0] if rows else {}
        return MoPdfCommon.format_report_round_date(first.get("report_date") or first.get("created_at"))
