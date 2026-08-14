from __future__ import annotations

import html
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy import MetaData, Table as SATable, func, select
from sqlalchemy.orm import Session

from app.services.newpdf.mo_report_pdf_builder import (
    CancelledCallback,
    MoReportPdfBuildError,
    MoReportPdfBuilder,
    MoReportPdfBuildResult,
    MoReportPdfCancelledError,
    MoReportPdfNoDataError,
    ProgressCallback,
    emoji_font_markup,
    register_emoji_font,
)


class MoSummaryReportPdfBuilder:
    FONT_REGULAR = "Sarabun"
    FONT_BOLD = "Sarabun-SemiBold"

    FONT_REGULAR_FILE = "Sarabun-Regular.ttf"
    FONT_BOLD_FILE = "Sarabun-SemiBold.ttf"

    _fonts_registered = False

    @staticmethod
    def build_pdf(
        *,
        db: Session,
        filters: dict[str, Any],
        output_path: Path,
        progress_callback: ProgressCallback | None = None,
        is_cancelled: CancelledCallback | None = None,
    ) -> MoReportPdfBuildResult:
        output_path = Path(output_path)

        try:
            MoReportPdfBuilder.raise_if_cancelled(is_cancelled)
            MoSummaryReportPdfBuilder._register_fonts()

            rows = MoSummaryReportPdfBuilder._fetch_summary_rows(
                db=db,
                filters=filters,
            )

            if not rows:
                raise MoReportPdfNoDataError(
                    "ไม่พบข้อมูลรายงานสรุป MO ตามเงื่อนไขที่เลือก"
                )

            total_rows = len(rows)

            if progress_callback:
                progress_callback(0, total_rows)

            output_path.parent.mkdir(parents=True, exist_ok=True)

            document = SimpleDocTemplate(
                str(output_path),
                pagesize=A4,
                leftMargin=10 * mm,
                rightMargin=10 * mm,
                topMargin=10 * mm,
                bottomMargin=12 * mm,
                title="รายงานสรุปประจำวัน MO",
                author="GUTS-ESS",
            )

            story = MoSummaryReportPdfBuilder._build_story(
                rows=rows,
                filters=filters,
                progress_callback=progress_callback,
                is_cancelled=is_cancelled,
            )

            document.build(story)

            MoReportPdfBuilder.raise_if_cancelled(is_cancelled)

            if not output_path.is_file():
                raise MoReportPdfBuildError(
                    "ไม่พบไฟล์ PDF หลังจากสร้างรายงาน"
                )

            file_size = output_path.stat().st_size

            if file_size <= 0:
                raise MoReportPdfBuildError(
                    "ไฟล์ PDF ที่สร้างมีขนาด 0 byte"
                )

            generated_at = datetime.now()

            return MoReportPdfBuildResult(
                download_filename=(
                    f"รายงานสรุปประจำวัน_MO_"
                    f"{generated_at:%d%m%Y_%H%M%S}.pdf"
                ),
                file_size_bytes=file_size,
                report_row_count=total_rows,
            )

        except (
            MoReportPdfCancelledError,
            MoReportPdfNoDataError,
            MoReportPdfBuildError,
        ):
            MoReportPdfBuilder.remove_partial_file(output_path)
            raise

        except Exception as exc:
            MoReportPdfBuilder.remove_partial_file(output_path)
            raise MoReportPdfBuildError(
                "ไม่สามารถสร้างรายงานสรุป MO ได้"
            ) from exc

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        if value is None or value == "":
            return None

        if isinstance(value, datetime):
            return value

        try:
            return datetime.fromisoformat(str(value).strip())
        except ValueError:
            return None

    @staticmethod
    def _fetch_summary_rows(
        *,
        db: Session,
        filters: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Fetch summary rows using SQLAlchemy Core, without raw SQL."""

        bind = db.get_bind()
        metadata = MetaData()

        transaction = SATable(
            "mo_daily_transactions",
            metadata,
            autoload_with=bind,
        )
        detail = SATable(
            "mo_daily_transaction_details",
            metadata,
            autoload_with=bind,
        )

        department_id = filters.get("department_id")
        transaction_ids = filters.get("mo_daily_transaction_ids") or []
        start_date = filters.get("start_date")
        end_date = filters.get("end_date")
        status = filters.get("status")
        created_by = filters.get("created_by")

        statement = (
            select(
                transaction.c.mo_daily_transaction_id.label(
                    "mo_daily_transaction_id"
                ),
                transaction.c.department_id.label("department_id"),
                transaction.c.department_name.label("department_name"),
                transaction.c.division_id.label("division_id"),
                transaction.c.division_name.label("division_name"),
                func.date(transaction.c.created_at).label("report_date"),
                transaction.c.workflow_status.label("workflow_status"),
                func.coalesce(
                    detail.c.dept_guard_post_count,
                    0,
                ).label("dept_guard_post_count"),
                func.coalesce(
                    detail.c.dept_current_personnel_count,
                    0,
                ).label("dept_current_personnel_count"),
                func.coalesce(
                    detail.c.dept_missing_regular_count,
                    0,
                ).label("dept_missing_regular_count"),
                func.coalesce(
                    detail.c.dept_missing_personnel_count,
                    0,
                ).label("dept_missing_personnel_count"),
                func.coalesce(
                    detail.c.dept_supplement_count,
                    0,
                ).label("dept_supplement_count"),
                func.coalesce(
                    detail.c.dept_recruitment_count,
                    0,
                ).label("dept_recruitment_count"),
                func.coalesce(
                    detail.c.dept_reserve_units_count,
                    0,
                ).label("dept_reserve_units_count"),
                func.coalesce(
                    detail.c.dept_reserve_personnel_count,
                    0,
                ).label("dept_reserve_personnel_count"),
                func.coalesce(
                    detail.c.leave_personal_count,
                    0,
                ).label("leave_personal_count"),
                func.coalesce(
                    detail.c.leave_sick_count,
                    0,
                ).label("leave_sick_count"),
                func.coalesce(
                    detail.c.leave_absent_count,
                    0,
                ).label("leave_absent_count"),
                func.coalesce(
                    detail.c.leave_deserted_count,
                    0,
                ).label("leave_deserted_count"),
                func.coalesce(
                    detail.c.leave_resigned_count,
                    0,
                ).label("leave_resigned_count"),
                func.coalesce(
                    detail.c.leave_terminated_count,
                    0,
                ).label("leave_terminated_count"),
                func.coalesce(
                    detail.c.shift_18_count,
                    0,
                ).label("shift_18_count"),
                func.coalesce(
                    detail.c.shift_24_count,
                    0,
                ).label("shift_24_count"),
                func.coalesce(
                    detail.c.shift_36_count,
                    0,
                ).label("shift_36_count"),
                func.coalesce(
                    detail.c.training_shift_change_count,
                    0,
                ).label("training_shift_change_count"),
                func.coalesce(
                    detail.c.training_planned_count,
                    0,
                ).label("training_planned_count"),
                func.coalesce(
                    detail.c.training_supervise_onsite_count,
                    0,
                ).label("training_supervise_onsite_count"),
                func.coalesce(
                    detail.c.training_supervise_virtual_simulation_count,
                    0,
                ).label(
                    "training_supervise_virtual_simulation_count"
                ),
                func.coalesce(
                    detail.c.employer_number_count,
                    0,
                ).label("employer_number_count"),
                func.coalesce(
                    detail.c.employer_problem_count,
                    0,
                ).label("employer_problem_count"),
            )
            .select_from(
                transaction.outerjoin(
                    detail,
                    (
                        detail.c.mo_daily_transaction_id
                        == transaction.c.mo_daily_transaction_id
                    ),
                )
            )
        )

        if department_id not in (None, ""):
            statement = statement.where(
                transaction.c.department_id == int(department_id)
            )

        if transaction_ids:
            statement = statement.where(
                transaction.c.mo_daily_transaction_id.in_(transaction_ids)
            )

        start_dt = MoSummaryReportPdfBuilder._parse_datetime(start_date)
        end_dt = MoSummaryReportPdfBuilder._parse_datetime(end_date)

        if (
            end_dt is not None
            and end_dt.hour == 0
            and end_dt.minute == 0
            and end_dt.second == 0
        ):
            end_dt = end_dt.replace(
                hour=23,
                minute=59,
                second=59,
                microsecond=999999,
            )

        if start_dt is not None:
            statement = statement.where(
                transaction.c.created_at >= start_dt
            )

        if end_dt is not None:
            statement = statement.where(
                transaction.c.created_at <= end_dt
            )

        if status:
            statement = statement.where(
                transaction.c.approved_status == status
            )

        if created_by:
            statement = statement.where(
                transaction.c.created_by == created_by
            )

        statement = statement.order_by(
            transaction.c.department_name.asc(),
            transaction.c.division_name.asc(),
            transaction.c.mo_daily_transaction_id.asc(),
        )

        return [
            dict(row)
            for row in db.execute(statement).mappings().all()
        ]

    @staticmethod
    def _build_story(
        *,
        rows: list[dict[str, Any]],
        filters: dict[str, Any],
        progress_callback: ProgressCallback | None,
        is_cancelled: CancelledCallback | None,
    ) -> list[Any]:
        title_style = ParagraphStyle(
            name="SummaryTitle",
            fontName=MoSummaryReportPdfBuilder.FONT_BOLD,
            fontSize=15,
            leading=19,
            alignment=TA_CENTER,
        )

        subtitle_style = ParagraphStyle(
            name="SummarySubtitle",
            fontName=MoSummaryReportPdfBuilder.FONT_REGULAR,
            fontSize=9,
            leading=12,
            alignment=TA_CENTER,
        )

        header_style = ParagraphStyle(
            name="SummaryHeader",
            fontName=MoSummaryReportPdfBuilder.FONT_BOLD,
            fontSize=6.5,
            leading=8,
            alignment=TA_CENTER,
        )

        cell_style = ParagraphStyle(
            name="SummaryCell",
            fontName=MoSummaryReportPdfBuilder.FONT_REGULAR,
            fontSize=6.5,
            leading=8,
            alignment=TA_CENTER,
        )

        # Enable OpenType shaping for Thai text so vowels and tone marks
        # are positioned correctly relative to consonants.
        for style in (title_style, subtitle_style, header_style, cell_style):
            style.shaping = True

        story: list[Any] = [
            Paragraph("รายงานสรุปประจำวัน MO", title_style),
            Spacer(1, 2 * mm),
            Paragraph(
                MoSummaryReportPdfBuilder._summary_text(
                    rows=rows,
                    filters=filters,
                ),
                subtitle_style,
            ),
            Spacer(1, 5 * mm),
        ]

        headers = [
            "ลำดับ",
            "เขต/ฝ่าย",
            "จุด รปภ.",
            "กำลังพล<br/>ปัจจุบัน",
            "ขาดประจำ",
            "ขาดกำลังพล",
            "เสริม",
            "รับสมัคร",
            "ลาส่วนตัว",
            "ลาป่วย",
            "ขาดงาน",
            "ควง 18",
            "ควง 24",
            "ควง 36",
            "อบรม",
            "พบผู้ว่าจ้าง",
            "ปัญหา",
            "สถานะ",
        ]

        table_data: list[list[Any]] = [
            [Paragraph(value, header_style) for value in headers]
        ]

        total = {
            "dept_guard_post_count": 0,
            "dept_current_personnel_count": 0,
            "dept_missing_regular_count": 0,
            "dept_missing_personnel_count": 0,
            "dept_supplement_count": 0,
            "dept_recruitment_count": 0,
            "leave_personal_count": 0,
            "leave_sick_count": 0,
            "leave_absent_count": 0,
            "shift_18_count": 0,
            "shift_24_count": 0,
            "shift_36_count": 0,
            "training_total": 0,
            "employer_number_count": 0,
            "employer_problem_count": 0,
        }

        for index, row in enumerate(rows, start=1):
            MoReportPdfBuilder.raise_if_cancelled(is_cancelled)

            training_total = sum(
                MoSummaryReportPdfBuilder._number(row, field)
                for field in (
                    "training_shift_change_count",
                    "training_planned_count",
                    "training_supervise_onsite_count",
                    "training_supervise_virtual_simulation_count",
                )
            )

            for field in total:
                if field == "training_total":
                    total[field] += training_total
                else:
                    total[field] += MoSummaryReportPdfBuilder._number(
                        row,
                        field,
                    )

            values = [
                index,
                row.get("division_name") or "-",
                row.get("dept_guard_post_count", 0),
                row.get("dept_current_personnel_count", 0),
                row.get("dept_missing_regular_count", 0),
                row.get("dept_missing_personnel_count", 0),
                row.get("dept_supplement_count", 0),
                row.get("dept_recruitment_count", 0),
                row.get("leave_personal_count", 0),
                row.get("leave_sick_count", 0),
                row.get("leave_absent_count", 0),
                row.get("shift_18_count", 0),
                row.get("shift_24_count", 0),
                row.get("shift_36_count", 0),
                training_total,
                row.get("employer_number_count", 0),
                row.get("employer_problem_count", 0),
                row.get("workflow_status") or "-",
            ]

            table_data.append(
                [
                    Paragraph(
                        MoSummaryReportPdfBuilder._escape(value),
                        cell_style,
                    )
                    for value in values
                ]
            )

            if progress_callback:
                progress_callback(index, len(rows))

        total_values = [
            "",
            "รวมทั้งหมด",
            total["dept_guard_post_count"],
            total["dept_current_personnel_count"],
            total["dept_missing_regular_count"],
            total["dept_missing_personnel_count"],
            total["dept_supplement_count"],
            total["dept_recruitment_count"],
            total["leave_personal_count"],
            total["leave_sick_count"],
            total["leave_absent_count"],
            total["shift_18_count"],
            total["shift_24_count"],
            total["shift_36_count"],
            total["training_total"],
            total["employer_number_count"],
            total["employer_problem_count"],
            "",
        ]

        table_data.append(
            [
                Paragraph(
                    MoSummaryReportPdfBuilder._escape(value),
                    header_style,
                )
                for value in total_values
            ]
        )

        table = Table(
            table_data,
            repeatRows=1,
            colWidths=[
                6 * mm,
                22 * mm,
                9 * mm,
                12.5 * mm,
                10 * mm,
                11 * mm,
                8.5 * mm,
                9 * mm,
                9 * mm,
                9 * mm,
                8.5 * mm,
                8.5 * mm,
                8.5 * mm,
                8.5 * mm,
                9 * mm,
                11.5 * mm,
                8.5 * mm,
                19 * mm,
            ],
        )

        table.setStyle(
            TableStyle(
                [
                    (
                        "FONTNAME",
                        (0, 0),
                        (-1, -1),
                        MoSummaryReportPdfBuilder.FONT_REGULAR,
                    ),
                    (
                        "FONTNAME",
                        (0, 0),
                        (-1, 0),
                        MoSummaryReportPdfBuilder.FONT_BOLD,
                    ),
                    (
                        "FONTNAME",
                        (0, -1),
                        (-1, -1),
                        MoSummaryReportPdfBuilder.FONT_BOLD,
                    ),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
                    ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F1F5F9")),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#64748B")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 2),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )

        story.append(table)
        return story

    @staticmethod
    def _summary_text(
        *,
        rows: list[dict[str, Any]],
        filters: dict[str, Any],
    ) -> str:
        department_name = next(
            (
                str(row.get("department_name"))
                for row in rows
                if row.get("department_name")
            ),
            "ทุกฝ่าย/ภาค",
        )

        start_date = filters.get("start_date")
        end_date = filters.get("end_date")

        if start_date and end_date:
            start_text = MoSummaryReportPdfBuilder._format_date(start_date)
            end_text = MoSummaryReportPdfBuilder._format_date(end_date)
            report_date = (
                f"{start_text} - {end_text}"
                if start_text != end_text
                else start_text
            )
        elif start_date:
            report_date = start_date
        else:
            report_date = next(
                (
                    row.get("report_date")
                    for row in rows
                    if row.get("report_date") is not None
                ),
                None,
            )

        return emoji_font_markup(
            f"ฝ่าย/ภาค: {html.escape(department_name)}"
            f" &nbsp;&nbsp; วันที่: "
            f"{html.escape(MoSummaryReportPdfBuilder._format_date(report_date))}"
        )

    @staticmethod
    def _number(row: Mapping[str, Any], field: str) -> int:
        value = row.get(field, 0)

        if value is None:
            return 0

        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _escape(value: Any) -> str:
        return emoji_font_markup(
            html.escape(str(value if value is not None else ""))
        )

    @staticmethod
    def _format_date(value: Any) -> str:
        if value is None:
            return "-"

        if isinstance(value, datetime):
            return value.strftime("%d/%m/%Y")

        if isinstance(value, date):
            return value.strftime("%d/%m/%Y")

        text_value = str(value).strip()

        try:
            return datetime.fromisoformat(text_value).strftime("%d/%m/%Y")
        except ValueError:
            return text_value or "-"

    @staticmethod
    def _register_fonts() -> None:
        if MoSummaryReportPdfBuilder._fonts_registered:
            return

        resources = Path(__file__).resolve().parents[2] / "resources"
        font_directory = resources / "fonts"

        regular = font_directory / MoSummaryReportPdfBuilder.FONT_REGULAR_FILE
        bold = font_directory / MoSummaryReportPdfBuilder.FONT_BOLD_FILE

        if not regular.is_file() or not bold.is_file():
            raise MoReportPdfBuildError(
                f"Thai PDF fonts were not found in {font_directory}"
            )

        pdfmetrics.registerFont(
            TTFont(
                MoSummaryReportPdfBuilder.FONT_REGULAR,
                str(regular),
                shapable=True,
            )
        )
        pdfmetrics.registerFont(
            TTFont(
                MoSummaryReportPdfBuilder.FONT_BOLD,
                str(bold),
                shapable=True,
            )
        )

        register_emoji_font()

        MoSummaryReportPdfBuilder._fonts_registered = True
