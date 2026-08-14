from __future__ import annotations

import html
from datetime import date, datetime
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy import MetaData, Table as SATable, select
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


class MoDivisionReportPdfBuilder:
    """Generate the complete PDF for one MO division."""

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
            MoDivisionReportPdfBuilder._register_fonts()

            report = MoDivisionReportPdfBuilder._fetch_report(
                db=db,
                filters=filters,
            )

            if report is None:
                raise MoReportPdfNoDataError(
                    "ไม่พบรายงานของเขตตามเงื่อนไขที่เลือก"
                )

            transaction_id = int(
                report["mo_daily_transaction_id"]
            )

            projects = MoDivisionReportPdfBuilder._fetch_projects(
                db=db,
                transaction_id=transaction_id,
            )

            disciplines = (
                MoDivisionReportPdfBuilder._fetch_disciplines(
                    db=db,
                    transaction_id=transaction_id,
                )
            )

            movements = (
                MoDivisionReportPdfBuilder._fetch_guard_post_movements(
                    db=db,
                    transaction_id=transaction_id,
                )
            )

            sections_total = 8

            if progress_callback:
                progress_callback(0, sections_total)

            output_path.parent.mkdir(parents=True, exist_ok=True)

            story = MoDivisionReportPdfBuilder._build_story(
                report=report,
                projects=projects,
                disciplines=disciplines,
                movements=movements,
                progress_callback=progress_callback,
                is_cancelled=is_cancelled,
                progress_total=sections_total,
            )

            document = SimpleDocTemplate(
                str(output_path),
                pagesize=A4,
                leftMargin=12 * mm,
                rightMargin=12 * mm,
                topMargin=10 * mm,
                bottomMargin=12 * mm,
                title="รายงานประจำวัน MO แยกตามเขต",
                author="GUTS-ESS",
            )

            MoReportPdfBuilder.raise_if_cancelled(is_cancelled)
            document.build(story)
            MoReportPdfBuilder.raise_if_cancelled(is_cancelled)

            if not output_path.is_file():
                raise MoReportPdfBuildError(
                    "The division PDF file was not created."
                )

            file_size = output_path.stat().st_size

            if file_size <= 0:
                raise MoReportPdfBuildError(
                    "The division PDF file is empty."
                )

            generated_at = datetime.now()
            division_name = (
                MoDivisionReportPdfBuilder._safe_filename(
                    str(report.get("division_name") or "MO")
                )
            )

            filename = (
                f"รายงานประจำวัน_{division_name}_"
                f"{generated_at:%d%m%Y_%H%M%S}.pdf"
            )

            return MoReportPdfBuildResult(
                download_filename=filename,
                file_size_bytes=file_size,
                report_row_count=1,
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
                "Could not generate the MO division PDF."
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
    def _fetch_report(
        *,
        db: Session,
        filters: dict[str, Any],
    ) -> dict[str, Any] | None:
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

        division_id = MoDivisionReportPdfBuilder._positive_int(
            filters.get("division_id")
            or filters.get("divisionId")
        )

        transaction_ids = filters.get("mo_daily_transaction_ids") or []

        if division_id is None and transaction_ids:
            division_id = MoDivisionReportPdfBuilder._positive_int(
                db.execute(
                    select(transaction.c.division_id)
                    .where(
                        transaction.c.mo_daily_transaction_id.in_(
                            transaction_ids
                        )
                    )
                    .limit(1)
                ).scalar_one_or_none()
            )

        if division_id is None:
            raise MoReportPdfBuildError(
                "division_id is required for a division PDF."
            )

        department_id = MoDivisionReportPdfBuilder._positive_int(
            filters.get("department_id")
            or filters.get("departmentId")
        )

        start_date = filters.get("start_date")
        end_date = filters.get("end_date")

        transaction_columns = [
            column.label(column.name)
            for column in transaction.c
        ]

        transaction_column_names = {
            column.name for column in transaction.c
        }

        detail_columns = [
            column.label(column.name)
            for column in detail.c
            if column.name not in transaction_column_names
        ]

        statement = (
            select(*transaction_columns, *detail_columns)
            .select_from(
                transaction.outerjoin(
                    detail,
                    (
                        detail.c.mo_daily_transaction_id
                        == transaction.c.mo_daily_transaction_id
                    ),
                )
            )
            .where(
                transaction.c.division_id == division_id,
            )
        )

        if department_id is not None:
            statement = statement.where(
                transaction.c.department_id == department_id
            )

        if transaction_ids:
            statement = statement.where(
                transaction.c.mo_daily_transaction_id.in_(transaction_ids)
            )

        start_dt = MoDivisionReportPdfBuilder._parse_datetime(start_date)
        end_dt = MoDivisionReportPdfBuilder._parse_datetime(end_date)

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

        statement = statement.order_by(
            transaction.c.created_at.desc()
        ).limit(1)

        row = db.execute(statement).mappings().one_or_none()
        if row is None:
            return None

        result = dict(row)

        created_at = result.get("created_at")
        if isinstance(created_at, datetime):
            result["report_date"] = created_at.date().isoformat()
        elif created_at is not None:
            result["report_date"] = str(created_at)[:10]
        else:
            result["report_date"] = None

        return result

    @staticmethod
    def _fetch_projects(
        *,
        db: Session,
        transaction_id: int,
    ) -> list[dict[str, Any]]:
        bind = db.get_bind()
        metadata = MetaData()

        project = SATable(
            "mo_daily_transaction_projects",
            metadata,
            autoload_with=bind,
        )

        statement = (
            select(
                project.c.project_name.label("name"),
                project.c.detail,
                project.c.status,
                project.c.note,
            )
            .where(
                project.c.mo_daily_transaction_id == transaction_id,
                project.c.status.in_(["normal", "warning", "danger"]),
            )
            .order_by(
                project.c.created_at.asc(),
                project.c.id.asc(),
            )
        )

        return [
            dict(row)
            for row in db.execute(statement).mappings().all()
        ]

    @staticmethod
    def _fetch_disciplines(
        *,
        db: Session,
        transaction_id: int,
    ) -> list[dict[str, Any]]:
        bind = db.get_bind()
        metadata = MetaData()

        discipline = SATable(
            "mo_daily_transaction_discipline_warnings",
            metadata,
            autoload_with=bind,
        )

        statement = (
            select(
                discipline.c.key,
                discipline.c.label,
                discipline.c.value,
            )
            .where(
                discipline.c.mo_daily_transaction_id == transaction_id,
            )
            .order_by(
                discipline.c.id.asc()
            )
        )

        return [
            dict(row)
            for row in db.execute(statement).mappings().all()
        ]

    @staticmethod
    def _fetch_guard_post_movements(
        *,
        db: Session,
        transaction_id: int,
    ) -> list[dict[str, Any]]:
        bind = db.get_bind()
        metadata = MetaData()

        movement = SATable(
            "mo_daily_transaction_projects",
            metadata,
            autoload_with=bind,
        )

        statement = (
            select(
                movement.c.project_name.label("name"),
                movement.c.detail,
                movement.c.status,
                movement.c.note,
            )
            .where(
                movement.c.mo_daily_transaction_id == transaction_id,
                movement.c.status.notin_(["normal", "warning", "danger"]),
            )
            .order_by(
                movement.c.created_at.asc(),
                movement.c.id.asc(),
            )
        )

        return [
            dict(row)
            for row in db.execute(statement).mappings().all()
        ]

    @staticmethod
    def _build_story(
        *,
        report: dict[str, Any],
        projects: list[dict[str, Any]],
        disciplines: list[dict[str, Any]],
        movements: list[dict[str, Any]],
        progress_callback: ProgressCallback | None,
        is_cancelled: CancelledCallback | None,
        progress_total: int,
    ) -> list[Any]:
        styles = MoDivisionReportPdfBuilder._styles()
        story: list[Any] = []

        current_progress = 0

        def progress() -> None:
            nonlocal current_progress
            current_progress += 1

            MoReportPdfBuilder.raise_if_cancelled(is_cancelled)

            if progress_callback:
                progress_callback(
                    current_progress,
                    progress_total,
                )

        story.append(
            Paragraph(
                "รายงานประจำวันฝ่ายปฏิบัติการ",
                styles["title"],
            )
        )

        story.append(
            Paragraph(
                (
                    f"ฝ่าย/ภาค: "
                    f"{MoDivisionReportPdfBuilder._escape(report.get('department_name') or '-')}"
                    f"<br/>"
                    f"เขต/ส่วนงาน: "
                    f"{MoDivisionReportPdfBuilder._escape(report.get('division_name') or '-')}"
                    f"<br/>"
                    f"วันที่: "
                    f"{MoDivisionReportPdfBuilder._escape(MoDivisionReportPdfBuilder._format_date(report.get('report_date')))}"
                ),
                styles["subtitle"],
            )
        )
        story.append(Spacer(1, 5 * mm))

        story.extend(
            MoDivisionReportPdfBuilder._section_table(
                title="1. หน่วยงานและกำลังพลที่รับผิดชอบ",
                rows=[
                    (
                        "จำนวนจุดรักษาการณ์",
                        report.get("dept_guard_post_count", 0),
                    ),
                    (
                        "จำนวนกำลังพลปัจจุบัน",
                        report.get(
                            "dept_current_personnel_count",
                            0,
                        ),
                    ),
                    (
                        "ขาดอัตรากำลังประจำ",
                        report.get(
                            "dept_missing_regular_count",
                            0,
                        ),
                    ),
                    (
                        "ขาดกำลังพล",
                        report.get(
                            "dept_missing_personnel_count",
                            0,
                        ),
                    ),
                    (
                        "จัดกำลังเสริม",
                        report.get("dept_supplement_count", 0),
                    ),
                    (
                        "รับสมัคร",
                        report.get("dept_recruitment_count", 0),
                    ),
                    (
                        "หน่วยสำรอง",
                        report.get(
                            "dept_reserve_units_count",
                            0,
                        ),
                    ),
                    (
                        "กำลังพลสำรอง",
                        report.get(
                            "dept_reserve_personnel_count",
                            0,
                        ),
                    ),
                ],
                styles=styles,
            )
        )
        progress()

        story.extend(
            MoDivisionReportPdfBuilder._section_table(
                title="2. การลาและสถานะกำลังพล",
                rows=[
                    ("ลากิจ", report.get("leave_personal_count", 0)),
                    ("ลาป่วย", report.get("leave_sick_count", 0)),
                    ("ขาดงาน", report.get("leave_absent_count", 0)),
                    ("หนีงาน", report.get("leave_deserted_count", 0)),
                    ("ลาออก", report.get("leave_resigned_count", 0)),
                    ("เลิกจ้าง", report.get("leave_terminated_count", 0)),
                    ("เพิ่มเติม 1", report.get("leave_extra_1", 0)),
                    ("เพิ่มเติม 2", report.get("leave_extra_2", 0)),
                    ("เพิ่มเติม 3", report.get("leave_extra_3", 0)),
                    ("เพิ่มเติม 4", report.get("leave_extra_4", 0)),
                    ("เพิ่มเติม 5", report.get("leave_extra_5", 0)),
                ],
                styles=styles,
            )
        )
        progress()

        story.extend(
            MoDivisionReportPdfBuilder._section_table(
                title="3. การบริหารการควงเวร",
                rows=[
                    ("ควงเวร 18 ชั่วโมง", report.get("shift_18_count", 0)),
                    ("ควงเวร 24 ชั่วโมง", report.get("shift_24_count", 0)),
                    ("ควงเวร 36 ชั่วโมง", report.get("shift_36_count", 0)),
                ],
                styles=styles,
            )
        )
        progress()

        story.extend(
            MoDivisionReportPdfBuilder._section_table(
                title="4. การอบรม",
                rows=[
                    (
                        "อบรมก่อนเปลี่ยนผลัด",
                        report.get(
                            "training_shift_change_count",
                            0,
                        ),
                    ),
                    (
                        "อบรมตามแผน",
                        report.get(
                            "training_planned_count",
                            0,
                        ),
                    ),
                    (
                        "กำกับดูแลหน้างาน",
                        report.get(
                            "training_supervise_onsite_count",
                            0,
                        ),
                    ),
                    (
                        "กำกับดูแลผ่านระบบ/สถานการณ์จำลอง",
                        report.get(
                            "training_supervise_virtual_simulation_count",
                            0,
                        ),
                    ),
                ],
                styles=styles,
            )
        )
        progress()

        story.extend(
            MoDivisionReportPdfBuilder._section_table(
                title="5. การเข้าพบผู้ว่าจ้าง",
                rows=[
                    (
                        "จำนวนครั้งเข้าพบผู้ว่าจ้าง",
                        report.get("employer_number_count", 0),
                    ),
                    (
                        "จำนวนปัญหาที่พบ",
                        report.get("employer_problem_count", 0),
                    ),
                ],
                styles=styles,
            )
        )
        progress()

        story.extend(
            MoDivisionReportPdfBuilder._list_section(
                title="6. รายละเอียดโครงการ/การเข้าพบ",
                items=projects,
                styles=styles,
            )
        )
        progress()

        story.extend(
            MoDivisionReportPdfBuilder._list_section(
                title="7. การเปลี่ยนแปลงจุดรักษาการณ์",
                items=movements,
                styles=styles,
            )
        )
        progress()

        discipline_rows = [
            {
                "name": item.get("label") or item.get("key") or "-",
                "detail": f"จำนวน: {item.get('value', 0)}",
                "status": "",
                "note": "",
            }
            for item in disciplines
        ]

        story.extend(
            MoDivisionReportPdfBuilder._list_section(
                title="8. วินัยและการตักเตือน",
                items=discipline_rows,
                styles=styles,
            )
        )
        progress()

        story.append(PageBreak())
        story.pop()

        return story

    @staticmethod
    def _section_table(
        *,
        title: str,
        rows: list[tuple[str, Any]],
        styles: dict[str, ParagraphStyle],
    ) -> list[Any]:
        data = [
            [
                Paragraph("รายการ", styles["table_header"]),
                Paragraph("จำนวน", styles["table_header"]),
            ]
        ]

        for label, value in rows:
            data.append(
                [
                    Paragraph(
                        MoDivisionReportPdfBuilder._escape(label),
                        styles["table_cell"],
                    ),
                    str(value or 0),
                ]
            )

        table = Table(
            data,
            colWidths=[140 * mm, 30 * mm],
            repeatRows=1,
        )

        table.setStyle(
            MoDivisionReportPdfBuilder._table_style()
        )

        return [
            Paragraph(title, styles["section_title"]),
            Spacer(1, 1.5 * mm),
            table,
            Spacer(1, 5 * mm),
        ]

    @staticmethod
    def _list_section(
        *,
        title: str,
        items: list[dict[str, Any]],
        styles: dict[str, ParagraphStyle],
    ) -> list[Any]:
        if not items:
            return [
                Paragraph(title, styles["section_title"]),
                Paragraph(
                    "ไม่มีข้อมูล",
                    styles["empty"],
                ),
                Spacer(1, 5 * mm),
            ]

        data: list[list[Any]] = [
            [
                Paragraph("ลำดับ", styles["table_header"]),
                Paragraph("ชื่อ/รายการ", styles["table_header"]),
                Paragraph("รายละเอียด", styles["table_header"]),
                Paragraph("สถานะ", styles["table_header"]),
                Paragraph("หมายเหตุ", styles["table_header"]),
            ]
        ]

        for index, item in enumerate(items, start=1):
            data.append(
                [
                    str(index),
                    Paragraph(
                        MoDivisionReportPdfBuilder._escape(item.get("name") or "-"),
                        styles["table_cell"],
                    ),
                    Paragraph(
                        MoDivisionReportPdfBuilder._escape(item.get("detail") or "-"),
                        styles["table_cell"],
                    ),
                    Paragraph(
                        MoDivisionReportPdfBuilder._escape(item.get("status") or "-"),
                        styles["table_cell"],
                    ),
                    Paragraph(
                        MoDivisionReportPdfBuilder._escape(item.get("note") or "-"),
                        styles["table_cell"],
                    ),
                ]
            )

        table = Table(
            data,
            colWidths=[
                12 * mm,
                38 * mm,
                60 * mm,
                25 * mm,
                35 * mm,
            ],
            repeatRows=1,
        )

        table.setStyle(
            MoDivisionReportPdfBuilder._table_style()
        )

        return [
            Paragraph(title, styles["section_title"]),
            Spacer(1, 1.5 * mm),
            table,
            Spacer(1, 5 * mm),
        ]

    @staticmethod
    def _table_style() -> TableStyle:
        return TableStyle(
            [
                (
                    "FONTNAME",
                    (0, 0),
                    (-1, -1),
                    MoDivisionReportPdfBuilder.FONT_REGULAR,
                ),
                (
                    "FONTNAME",
                    (0, 0),
                    (-1, 0),
                    MoDivisionReportPdfBuilder.FONT_BOLD,
                ),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("LEADING", (0, 0), (-1, -1), 10),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("ALIGN", (-1, 1), (-1, -1), "LEFT"),
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#E2E8F0"),
                ),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.4,
                    colors.HexColor("#64748B"),
                ),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )

    @staticmethod
    def _styles() -> dict[str, ParagraphStyle]:
        styles = {
            "title": ParagraphStyle(
                "MoDivisionTitle",
                fontName=MoDivisionReportPdfBuilder.FONT_BOLD,
                fontSize=16,
                leading=20,
                alignment=TA_CENTER,
                spaceAfter=3 * mm,
            ),
            "subtitle": ParagraphStyle(
                "MoDivisionSubtitle",
                fontName=MoDivisionReportPdfBuilder.FONT_REGULAR,
                fontSize=9,
                leading=13,
                alignment=TA_CENTER,
            ),
            "section_title": ParagraphStyle(
                "MoDivisionSectionTitle",
                fontName=MoDivisionReportPdfBuilder.FONT_BOLD,
                fontSize=11,
                leading=14,
                alignment=TA_LEFT,
                spaceBefore=2 * mm,
            ),
            "table_header": ParagraphStyle(
                "MoDivisionTableHeader",
                fontName=MoDivisionReportPdfBuilder.FONT_BOLD,
                fontSize=8,
                leading=10,
                alignment=TA_CENTER,
            ),
            "table_cell": ParagraphStyle(
                "MoDivisionTableCell",
                fontName=MoDivisionReportPdfBuilder.FONT_REGULAR,
                fontSize=8,
                leading=10,
                alignment=TA_LEFT,
            ),
            "empty": ParagraphStyle(
                "MoDivisionEmpty",
                fontName=MoDivisionReportPdfBuilder.FONT_REGULAR,
                fontSize=8,
                leading=11,
                alignment=TA_LEFT,
                textColor=colors.HexColor("#64748B"),
            ),
        }

        # Enable OpenType shaping for Thai text so vowels and tone marks
        # are positioned correctly relative to consonants.
        for style in styles.values():
            style.shaping = True

        return styles

    @staticmethod
    def _register_fonts() -> None:
        if MoDivisionReportPdfBuilder._fonts_registered:
            return

        resources = Path(__file__).resolve().parents[2] / "resources"
        font_directory = resources / "fonts"

        regular = font_directory / MoDivisionReportPdfBuilder.FONT_REGULAR_FILE
        bold = font_directory / MoDivisionReportPdfBuilder.FONT_BOLD_FILE

        if not regular.is_file() or not bold.is_file():
            raise MoReportPdfBuildError(
                f"Thai PDF fonts were not found in {font_directory}"
            )

        pdfmetrics.registerFont(
            TTFont(
                MoDivisionReportPdfBuilder.FONT_REGULAR,
                str(regular),
                shapable=True,
            )
        )
        pdfmetrics.registerFont(
            TTFont(
                MoDivisionReportPdfBuilder.FONT_BOLD,
                str(bold),
                shapable=True,
            )
        )

        register_emoji_font()

        MoDivisionReportPdfBuilder._fonts_registered = True

    @staticmethod
    def _escape(value: Any) -> str:
        return emoji_font_markup(
            html.escape(str(value if value is not None else ""))
        )

    @staticmethod
    def _positive_int(value: Any) -> int | None:
        try:
            converted = int(value)
        except (TypeError, ValueError):
            return None

        return converted if converted > 0 else None

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
            return datetime.fromisoformat(text_value).strftime(
                "%d/%m/%Y"
            )
        except ValueError:
            return text_value or "-"

    @staticmethod
    def _safe_filename(value: str) -> str:
        for character in '\\/:*?"<>|':
            value = value.replace(character, "-")

        return value.strip() or "MO"
