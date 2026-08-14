from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from sqlalchemy.orm import Session


class MoReportPdfBuildError(Exception):
    """The MO PDF could not be generated."""


class MoReportPdfCancelledError(Exception):
    """The MO PDF job was cancelled while generating."""


class MoReportPdfNoDataError(Exception):
    """No MO report data matched the selected filters."""


@dataclass(frozen=True)
class MoReportPdfBuildResult:
    download_filename: str
    file_size_bytes: int
    report_row_count: int


ProgressCallback = Callable[[int, int], None]
CancelledCallback = Callable[[], bool]


EMOJI_FONT_NAME = "NotoEmoji"
EMOJI_FONT_FILE = "NotoEmoji-Regular.ttf"

_emoji_font_available = False

# Emoji base characters (from the Unicode emoji-data property list).
# Multi-codepoint emoji — base + optional variation selector + optional
# skin tone, chained ZWJ sequences, and keycaps — are matched as a single
# run so the whole emoji stays inside one <font> tag. Variation selectors
# and ZWJ are never matched standalone, which keeps them from being split
# into a separate (broken) font run.
_EMOJI_BASE = (
    r"\u00a9\u00ae"
    r"\u203c\u2049"
    r"\u2122\u2139"
    r"\u2194-\u2199"
    r"\u21a9-\u21aa"
    r"\u231a-\u231b"
    r"\u2328\u23cf"
    r"\u23e9-\u23f3"
    r"\u23f8-\u23fa"
    r"\u24c2"
    r"\u25aa-\u25ab"
    r"\u25b6\u25c0"
    r"\u25fb-\u25fe"
    r"\u2600-\u27bf"
    r"\u2934-\u2935"
    r"\u2b05-\u2b07"
    r"\u2b1b-\u2b1c"
    r"\u2b50\u2b55"
    r"\u3030\u303d"
    r"\u3297\u3299"
    r"\U0001f000-\U0001faff"
)

_EMOJI_RUN = re.compile(
    rf"(?:"
    rf"[{_EMOJI_BASE}]"
    rf"[\ufe0e\ufe0f]?"
    rf"[\U0001f3fb-\U0001f3ff]?"
    rf"(?:"
    rf"\u200d"
    rf"[{_EMOJI_BASE}]"
    rf"[\ufe0e\ufe0f]?"
    rf"[\U0001f3fb-\U0001f3ff]?"
    rf")*"
    rf"|"
    rf"[0-9#*]\ufe0f?\u20e3"
    rf")"
)


def register_emoji_font() -> bool:
    """Register the monochrome emoji font used by ReportLab.

    ReportLab cannot render colour emoji fonts (Apple Color Emoji, Noto
    Color Emoji). A monochrome outline font (NotoEmoji-Regular, Symbola)
    provides the glyphs instead. A missing or unreadable font file raises
    MoReportPdfBuildError so the failure is visible instead of silently
    producing PDFs without emoji.
    """

    global _emoji_font_available
    if _emoji_font_available:
        return True

    font_path = (
        Path(__file__).resolve().parents[2]
        / "resources"
        / "fonts"
        / EMOJI_FONT_FILE
    )
    if not font_path.is_file():
        raise MoReportPdfBuildError(
            f"Emoji font was not found: {font_path}"
        )

    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    try:
        pdfmetrics.registerFont(
            TTFont(EMOJI_FONT_NAME, str(font_path), shapable=True)
        )
    except Exception as exc:
        raise MoReportPdfBuildError(
            f"Could not register emoji font: {font_path}"
        ) from exc

    _emoji_font_available = True
    return True


def emoji_font_markup(text: str) -> str:
    """Wrap emoji runs in <font> tags so they render with the emoji font.

    Call on already HTML-escaped text. No-op when the emoji font was not
    registered, so the PDF still builds without it.
    """

    if not _emoji_font_available:
        return text

    return _EMOJI_RUN.sub(
        lambda match: (
            f'<font name="{EMOJI_FONT_NAME}">{match.group(0)}</font>'
        ),
        text,
    )


class MoReportPdfBuilder:
    REPORT_TYPE_SUMMARY = "mo_summary_report"
    REPORT_TYPE_DIVISION = "mo_division_report"

    @staticmethod
    def build_mo_report_pdf(
        *,
        db: Session,
        filters: dict,
        output_path: Path,
        report_type: str,
        progress_callback: ProgressCallback | None = None,
        is_cancelled: CancelledCallback | None = None,
    ) -> MoReportPdfBuildResult:
        """
        Select the correct PDF builder according to report_type.

        Imports are inside this method to prevent circular imports because
        the summary and division builders import shared types from this file.
        """

        if report_type == MoReportPdfBuilder.REPORT_TYPE_SUMMARY:
            from app.services.newpdf.mo_summary_report_pdf_builder import (
                MoSummaryReportPdfBuilder,
            )

            return MoSummaryReportPdfBuilder.build_pdf(
                db=db,
                filters=filters,
                output_path=output_path,
                progress_callback=progress_callback,
                is_cancelled=is_cancelled,
            )

        if report_type == MoReportPdfBuilder.REPORT_TYPE_DIVISION:
            from app.services.newpdf.mo_division_report_pdf_builder import (
                MoDivisionReportPdfBuilder,
            )

            return MoDivisionReportPdfBuilder.build_pdf(
                db=db,
                filters=filters,
                output_path=output_path,
                progress_callback=progress_callback,
                is_cancelled=is_cancelled,
            )

        raise MoReportPdfBuildError(
            f"Unsupported MO report type: {report_type}"
        )

    @staticmethod
    def raise_if_cancelled(
        is_cancelled: CancelledCallback | None,
    ) -> None:
        """Raise the cancellation exception when cancellation was requested."""

        if is_cancelled is not None and is_cancelled():
            raise MoReportPdfCancelledError(
                "The MO PDF generation job was cancelled."
            )

    @staticmethod
    def remove_partial_file(output_path: Path) -> None:
        """Remove an incomplete PDF after cancellation or generation failure."""

        path = Path(output_path)

        try:
            if path.is_file():
                path.unlink()
        except OSError:
            # Do not hide the original PDF generation exception merely
            # because cleanup failed.
            pass
