from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.services.pdf.builder.util.mo_pdf_common import MoPdfCommon, MoReportNumberedCanvas


class MoPdfPageLayout:
    """Shared page-level layout for MO PDFs."""

    @staticmethod
    def make_document(
        *,
        reportlab: Mapping[str, Any],
        output_path: Path,
        fonts: Mapping[str, str],
        header_title: str,
        header_subtitle: str = "",
        first_page_suffix: str = "",
    ) -> tuple[Any, Any]:
        doc = reportlab["BaseDocTemplate"](
            str(output_path),
            pagesize=reportlab["A4"],
        )
        body_bottom_mm = MoPdfCommon.PAGE_HEIGHT_MM - MoPdfCommon.HEADER_HEIGHT_MM - MoPdfCommon.BODY_HEIGHT_MM
        frame = reportlab["Frame"](
            MoPdfCommon.PAGE_PADDING_X_MM * reportlab["mm"],
            body_bottom_mm * reportlab["mm"],
            MoPdfCommon.BODY_WIDTH_MM * reportlab["mm"],
            MoPdfCommon.BODY_HEIGHT_MM * reportlab["mm"],
            leftPadding=0,
            rightPadding=0,
            topPadding=0,
            bottomPadding=0,
            id="mo_pdf_body",
        )
        doc.addPageTemplates([reportlab["PageTemplate"](id="mo_pdf_page", frames=[frame])])

        def canvasmaker(*args: Any, **kwargs: Any) -> Any:
            return MoReportNumberedCanvas(
                *args,
                font_name=fonts["regular"],
                font_bold_name=fonts["bold"],
                font_size=MoPdfCommon.FONT_SIZE_HEADER_INFO,
                footer_font_size=MoPdfCommon.FONT_SIZE_FOOTER,
                footer_right_margin=MoPdfCommon.PAGE_PADDING_X_MM * reportlab["mm"],
                footer_y=5 * reportlab["mm"],
                header_title=header_title,
                header_subtitle=header_subtitle,
                first_page_suffix=first_page_suffix,
                logo_path=MoPdfCommon.logo_path(),
                **kwargs,
        )

        return doc, canvasmaker
