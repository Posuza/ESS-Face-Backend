from __future__ import annotations

import html
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Mapping


class MoReportPdfBuildError(Exception):
    """Raised when MO report PDF generation fails."""


class MoReportPdfCancelledError(Exception):
    """Raised when the worker cancels a running MO report PDF job."""


class MoReportPdfNoDataError(Exception):
    """Raised when no MO reports match the export filters."""


class MoPdfCommon:
    FONT_REGULAR_NAME = "Sarabun"
    FONT_BOLD_NAME = "Sarabun-SemiBold"
    FONT_REGULAR_FILE = "Sarabun-Regular.ttf"
    FONT_BOLD_FILE = "Sarabun-SemiBold.ttf"

    # ===== ขนาดฟอนต์ / ระยะบรรทัด PDF: ปรับจากตรงนี้ =====
    FONT_SIZE_TITLE = 9.5
    FONT_LEADING_TITLE = 12

    FONT_SIZE_SECTION = 7.7
    FONT_LEADING_SECTION = 9.4

    # เนื้อหาในตารางของทั้ง 3 sections (normal / normal_center / detail / detail_center)
    FONT_SIZE_BODY = 6.5
    FONT_LEADING_BODY = 8.0

    FONT_SIZE_SMALL = 7
    FONT_LEADING_SMALL = 9

    # ส่วนหัว/ท้ายกระดาษ: เวลาที่ดึงข้อมูล + เลขหน้า ตั้งขนาดเท่ากับฟอนต์ตาราง
    # (FONT_SIZE_BODY=6.5) แต่แยกเป็นค่าคงที่ของตัวเอง ปรับได้อิสระ
    FONT_SIZE_HEADER_INFO = 6.5
    FONT_SIZE_FOOTER = 6.5
    FONT_SIZE_HEADER_TITLE = 9.5

    LOGO_FILE_NAME = "logoguts.png"
    LOGO_WIDTH_MM = 23.6
    LOGO_HEIGHT_MM = 12

    PAGE_WIDTH_MM = 210
    PAGE_HEIGHT_MM = 297
    PAGE_PADDING_X_MM = 7
    PAGE_PADDING_Y_MM = 4
    HEADER_HEIGHT_MM = 22.5
    FOOTER_HEIGHT_MM = 10
    BODY_WIDTH_MM = 196
    BODY_HEIGHT_MM = 256.5

    FIELD_GROUPS = [
        (
            "หน่วยงานที่รับผิดชอบ",
            [
                ("dept_guard_post_count", "จุดรักษาการณ์", "หน่วยงาน"),
                ("dept_current_personnel_count", "กำลังพลปัจจุบัน", "คน"),
                ("dept_missing_regular_count", "ขาดตัวประจำ", "หน่วยงาน"),
                ("dept_missing_personnel_count", "ขาดกำลังพล", "คน"),
                ("dept_recruitment_count", "รับ รปภ. ใหม่", "คน"),
                ("dept_supplement_count", "จัดกำลังพลเสริมพิเศษ", "คน"),
                ("dept_reserve_units_count", "จำนวนหน่วยงานสำรองเวร", "หน่วย"),
                ("dept_reserve_personnel_count", "จำนวนกำลังพลสำรองเวร", "คน"),
            ],
        ),
        (
            "การลา",
            [
                ("leave_personal_count", "ลากิจ", "คน"),
                ("leave_sick_count", "ลาป่วย", "คน"),
                ("leave_absent_count", "ขาดงาน", "คน"),
                ("leave_deserted_count", "หนีหาย", "คน"),
                ("leave_resigned_count", "ลาออก", "คน"),
                ("leave_terminated_count", "ส่ง รปภ. คืนฝ่ายบริหารงานบุคคล", "คน"),
            ],
        ),
        (
            "การบริหารการครองเวร",
            [
                ("shift_18_count", "18 ชั่วโมง", "คน"),
                ("shift_24_count", "24 ชั่วโมง", "คน"),
                ("shift_36_count", "36 ชั่วโมง", "คน"),
            ],
        ),
        (
            "อบรมและควบคุมหน้างาน",
            [
                ("training_shift_change_count", "อบรมเปลี่ยนผลัด", "หน่วยงาน"),
                ("training_planned_count", "อบรมตามแผนงานที่กำหนด", "หน่วยงาน"),
                ("training_supervise_onsite_count", "ควบคุมหน้างาน", "หน่วยงาน"),
                (
                    "training_supervise_virtual_simulation_count",
                    "จำลองสถานการณ์เสมือนจริง",
                    "หน่วยงาน",
                ),
            ],
        ),
    ]

    @staticmethod
    def import_reportlab() -> dict[str, Any]:
        try:
            from reportlab.lib import colors
            from reportlab.lib.enums import TA_CENTER, TA_LEFT
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
            from reportlab.lib.units import mm
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            from reportlab.pdfgen.canvas import Canvas
            from reportlab.platypus import (
                BaseDocTemplate,
                Flowable,
                Frame,
                Image as PdfImage,
                PageBreak,
                PageTemplate,
                Paragraph,
                SimpleDocTemplate,
                Spacer,
                Table,
                TableStyle,
            )
        except ImportError as exc:
            raise MoReportPdfBuildError(
                "ReportLab is required for MO PDF export. Add "
                "'reportlab[shaping]>=4.4.10,<5.0.0' to backend requirements "
                "and install dependencies."
            ) from exc

        return {
            "A4": A4,
            "Canvas": Canvas,
            "BaseDocTemplate": BaseDocTemplate,
            "Flowable": Flowable,
            "Frame": Frame,
            "PageBreak": PageBreak,
            "PageTemplate": PageTemplate,
            "Paragraph": Paragraph,
            "PdfImage": PdfImage,
            "ParagraphStyle": ParagraphStyle,
            "SimpleDocTemplate": SimpleDocTemplate,
            "Spacer": Spacer,
            "TA_CENTER": TA_CENTER,
            "TA_LEFT": TA_LEFT,
            "Table": Table,
            "TableStyle": TableStyle,
            "TTFont": TTFont,
            "colors": colors,
            "getSampleStyleSheet": getSampleStyleSheet,
            "mm": mm,
            "pdfmetrics": pdfmetrics,
        }

    @classmethod
    def register_fonts(cls, reportlab: Mapping[str, Any]) -> dict[str, str]:
        resources_dir = cls.resources_dir() / "fonts"
        regular_path = resources_dir / cls.FONT_REGULAR_FILE
        bold_path = resources_dir / cls.FONT_BOLD_FILE

        regular_name = "Helvetica"
        bold_name = "Helvetica-Bold"
        if regular_path.exists() and bold_path.exists():
            try:
                regular_font = reportlab["TTFont"](
                    cls.FONT_REGULAR_NAME,
                    str(regular_path),
                    shapable=True,
                )
                bold_font = reportlab["TTFont"](
                    cls.FONT_BOLD_NAME,
                    str(bold_path),
                    shapable=True,
                )
            except TypeError:
                regular_font = reportlab["TTFont"](cls.FONT_REGULAR_NAME, str(regular_path))
                bold_font = reportlab["TTFont"](cls.FONT_BOLD_NAME, str(bold_path))

            reportlab["pdfmetrics"].registerFont(regular_font)
            reportlab["pdfmetrics"].registerFont(bold_font)
            reportlab["pdfmetrics"].registerFontFamily(
                cls.FONT_REGULAR_NAME,
                normal=cls.FONT_REGULAR_NAME,
                bold=cls.FONT_BOLD_NAME,
            )
            regular_name = cls.FONT_REGULAR_NAME
            bold_name = cls.FONT_BOLD_NAME

        return {"regular": regular_name, "bold": bold_name}

    @staticmethod
    def resources_dir() -> Path:
        return Path(__file__).resolve().parents[4] / "resources"

    @classmethod
    def logo_path(cls) -> Path | None:
        logo_path = cls.resources_dir() / "images" / cls.LOGO_FILE_NAME
        if not logo_path.is_file():
            return None
        return logo_path

    @classmethod
    def get_logo_image(cls, reportlab: Mapping[str, Any]) -> Any | None:
        logo_path = cls.logo_path()
        if logo_path is None:
            return None
        logo = reportlab["PdfImage"](str(logo_path))
        logo._restrictSize(
            cls.LOGO_WIDTH_MM * reportlab["mm"],
            cls.LOGO_HEIGHT_MM * reportlab["mm"],
        )
        logo.hAlign = "CENTER"
        return logo

    @staticmethod
    def build_styles(reportlab: Mapping[str, Any], fonts: Mapping[str, str]) -> dict[str, Any]:
        base = reportlab["getSampleStyleSheet"]()
        styles = {
            "title": reportlab["ParagraphStyle"](
                "MoTitle",
                parent=base["Title"],
                fontName=fonts["bold"],
                fontSize=MoPdfCommon.FONT_SIZE_TITLE,
                leading=MoPdfCommon.FONT_LEADING_TITLE,
                alignment=reportlab["TA_CENTER"],
            ),
            "section": reportlab["ParagraphStyle"](
                "MoSection",
                parent=base["Heading2"],
                fontName=fonts["bold"],
                fontSize=MoPdfCommon.FONT_SIZE_SECTION,
                leading=MoPdfCommon.FONT_LEADING_SECTION,
                spaceBefore=3,
                spaceAfter=2,
            ),
            "normal": reportlab["ParagraphStyle"](
                "MoNormal",
                parent=base["Normal"],
                fontName=fonts["regular"],
                fontSize=MoPdfCommon.FONT_SIZE_BODY,
                leading=MoPdfCommon.FONT_LEADING_BODY,
                alignment=reportlab["TA_LEFT"],
            ),
            "normal_center": reportlab["ParagraphStyle"](
                "MoNormalCenter",
                parent=base["Normal"],
                fontName=fonts["regular"],
                fontSize=MoPdfCommon.FONT_SIZE_BODY,
                leading=MoPdfCommon.FONT_LEADING_BODY,
                alignment=reportlab["TA_CENTER"],
            ),
            "detail": reportlab["ParagraphStyle"](
                "MoDetail",
                parent=base["Normal"],
                fontName=fonts["regular"],
                fontSize=MoPdfCommon.FONT_SIZE_BODY,
                leading=MoPdfCommon.FONT_LEADING_BODY,
                alignment=reportlab["TA_LEFT"],
            ),
            "detail_center": reportlab["ParagraphStyle"](
                "MoDetailCenter",
                parent=base["Normal"],
                fontName=fonts["regular"],
                fontSize=MoPdfCommon.FONT_SIZE_BODY,
                leading=MoPdfCommon.FONT_LEADING_BODY,
                alignment=reportlab["TA_CENTER"],
            ),
            "header": reportlab["ParagraphStyle"](
                "MoHeader",
                parent=base["Normal"],
                fontName=fonts["bold"],
                fontSize=MoPdfCommon.FONT_SIZE_BODY,
                leading=MoPdfCommon.FONT_LEADING_BODY,
                alignment=reportlab["TA_LEFT"],
            ),
            "header_center": reportlab["ParagraphStyle"](
                "MoHeaderCenter",
                parent=base["Normal"],
                fontName=fonts["bold"],
                fontSize=MoPdfCommon.FONT_SIZE_BODY,
                leading=MoPdfCommon.FONT_LEADING_BODY,
                alignment=reportlab["TA_CENTER"],
            ),
            "small": reportlab["ParagraphStyle"](
                "MoSmall",
                parent=base["Normal"],
                fontName=fonts["regular"],
                fontSize=MoPdfCommon.FONT_SIZE_SMALL,
                leading=MoPdfCommon.FONT_LEADING_SMALL,
                textColor=reportlab["colors"].HexColor("#000000"),
            ),
        }

        # Enable OpenType shaping for Thai text so vowels and tone marks
        # are positioned correctly relative to consonants.
        for style in styles.values():
            style.shaping = True

        return styles

    @staticmethod
    def table_style(reportlab: Mapping[str, Any]) -> Any:
        colors = reportlab["colors"]
        mm = reportlab["mm"]
        return reportlab["TableStyle"](
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#D9D9D9")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#000000")),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#BFC5CC")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )

    @staticmethod
    def paragraph(reportlab: Mapping[str, Any], styles: Mapping[str, Any], value: Any) -> Any:
        return reportlab["Paragraph"](MoPdfCommon.text(value), styles["normal"])

    @staticmethod
    def center_paragraph(reportlab: Mapping[str, Any], styles: Mapping[str, Any], value: Any) -> Any:
        return reportlab["Paragraph"](MoPdfCommon.text(value), styles["normal_center"])

    @staticmethod
    def detail_paragraph(reportlab: Mapping[str, Any], styles: Mapping[str, Any], value: Any) -> Any:
        return reportlab["Paragraph"](MoPdfCommon.text(value), styles["detail"])

    @staticmethod
    def detail_center_paragraph(reportlab: Mapping[str, Any], styles: Mapping[str, Any], value: Any) -> Any:
        return reportlab["Paragraph"](MoPdfCommon.text(value), styles["detail_center"])

    @staticmethod
    def header_paragraph(reportlab: Mapping[str, Any], styles: Mapping[str, Any], value: Any) -> Any:
        return reportlab["Paragraph"](MoPdfCommon.text(value), styles["header"])

    @staticmethod
    def header_center_paragraph(reportlab: Mapping[str, Any], styles: Mapping[str, Any], value: Any) -> Any:
        return reportlab["Paragraph"](MoPdfCommon.text(value), styles["header_center"])

    @staticmethod
    def division_marker(reportlab: Mapping[str, Any], division_name: str) -> Any:
        """Zero-size flowable that stamps the division name onto the canvas.

        The page header reads it per page, so a multi-division PDF (summary
        report) can show each division's name on its own pages only.
        """
        Flowable = reportlab["Flowable"]

        class _DivisionMarker(Flowable):
            def __init__(self, name: str) -> None:
                super().__init__()
                self.name = name
                self.width = 0
                self.height = 0

            def wrap(self, avail_width: float, avail_height: float) -> tuple[float, float]:
                return (0, 0)

            def draw(self) -> None:
                pass

            def drawOn(self, canvas: Any, x: float, y: float, _sW: float = 0) -> None:
                canvas._current_division = self.name

        return _DivisionMarker(str(division_name or "").strip())

    @staticmethod
    def detail_wrapped_paragraph(
        reportlab: Mapping[str, Any],
        styles: Mapping[str, Any],
        value: Any,
        *,
        width_mm: float,
    ) -> Any:
        return reportlab["Paragraph"](
            MoPdfCommon.detail_wrapped_markup(value, width_mm=width_mm),
            styles["detail"],
        )

    @staticmethod
    def text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, datetime):
            value = value.strftime("%Y-%m-%d %H:%M")
        return html.escape(MoPdfCommon.normalize_thai_text(str(value)))

    @staticmethod
    def normalize_thai_text(value: str) -> str:
        """
        Remove invalid duplicate Thai tone marks inside one glyph cluster.

        Example from imported MO data: "ไม่้กั้น" contains both mai ek and
        mai tho on the same "ม". ReportLab correctly shapes both marks, but
        visually they collide. Thai syllables should carry only one tone mark,
        so the PDF display keeps the last tone mark in that cluster.
        """
        tone_marks = {"\u0e48", "\u0e49", "\u0e4a", "\u0e4b"}
        thai_combining_marks = {
            "\u0e31",
            *[chr(codepoint) for codepoint in range(0x0E34, 0x0E3B)],
            *[chr(codepoint) for codepoint in range(0x0E47, 0x0E4F)],
        }

        output: list[str] = []
        tone_mark_index: int | None = None

        for char in value:
            if char in tone_marks:
                if tone_mark_index is None:
                    tone_mark_index = len(output)
                    output.append(char)
                else:
                    output[tone_mark_index] = char
                continue

            if char not in thai_combining_marks:
                tone_mark_index = None

            output.append(char)

        return "".join(output).replace("\u0e4d\u0e32", "\u0e33")

    @staticmethod
    def detail_wrapped_markup(value: Any, *, width_mm: float) -> str:
        normalized = MoPdfCommon.normalize_thai_text(
            str(value if value not in (None, "") else "-")
        )
        normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
        max_chars = max(18, int(width_mm / 1.03))
        lines: list[str] = []

        for source_line in normalized.split("\n"):
            # Normalize horizontal whitespace without losing explicit newlines.
            source_line = " ".join(source_line.split())
            if not source_line:
                lines.append("")
                continue

            current = ""
            for word in source_line.split(" "):
                candidate = word if not current else f"{current} {word}"
                if len(MoPdfCommon.visible_thai_units(candidate)) <= max_chars:
                    current = candidate
                    continue
                if current:
                    lines.append(current)
                current = ""
                while len(MoPdfCommon.visible_thai_units(word)) > max_chars:
                    chunk, word = MoPdfCommon.split_visible_thai_units(
                        word,
                        max_chars,
                    )
                    lines.append(chunk)
                current = word

            if current:
                lines.append(current)

        return "<br/>".join(html.escape(line) for line in lines) or "-"

    @staticmethod
    def visible_thai_units(value: str) -> list[str]:
        units: list[str] = []
        for char in value:
            if "\u0e31" <= char <= "\u0e4e" and units:
                units[-1] += char
            else:
                units.append(char)
        return units

    @staticmethod
    def split_visible_thai_units(value: str, max_units: int) -> tuple[str, str]:
        units = MoPdfCommon.visible_thai_units(value)
        return "".join(units[:max_units]), "".join(units[max_units:])

    @staticmethod
    def number(value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def display_number(value: int) -> str:
        return "-" if value == 0 else f"{value:,}"

    @staticmethod
    def status_label(value: Any) -> str:
        if value == "warning":
            return "ผิดปกติ"
        if value == "danger":
            return "ฉุกเฉิน"
        return MoPdfCommon.text(value)

    @staticmethod
    def status_color(reportlab: Mapping[str, Any], value: Any) -> Any:
        colors = reportlab["colors"]
        if value == "warning":
            return colors.HexColor("#FF9800")
        if value == "danger":
            return colors.HexColor("#B71C1C")
        return colors.HexColor("#000000")

    @staticmethod
    def project_status_count(row: Mapping[str, Any], status_key: str) -> int:
        return sum(
            1
            for item in row.get("projects") or []
            if isinstance(item, Mapping) and str(item.get("status") or "") == status_key
        )

    @staticmethod
    def format_filter_summary(filters: Mapping[str, Any]) -> str:
        parts = []
        for key in ("department_id", "division_id", "start_date", "end_date", "status", "created_by"):
            value = filters.get(key)
            if value not in (None, ""):
                parts.append(f"{key}: {html.escape(str(value))}")
        return " | ".join(parts) if parts else "ทุกข้อมูลที่เลือกส่งออก"

    @staticmethod
    def format_export_datetime(value: datetime | None = None) -> str:
        thai_short_months = [
            "ม.ค.",
            "ก.พ.",
            "มี.ค.",
            "เม.ย.",
            "พ.ค.",
            "มิ.ย.",
            "ก.ค.",
            "ส.ค.",
            "ก.ย.",
            "ต.ค.",
            "พ.ย.",
            "ธ.ค.",
        ]
        now = value or datetime.now()
        date_text = f"{now.day} {thai_short_months[now.month - 1]} {now.year + 543}"
        time_text = f"{now.hour:02d}:{now.minute:02d} น."
        return f"เวลาที่ดึงข้อมูล: {date_text} {time_text}"

    @staticmethod
    def format_report_round_date(raw_value: Any) -> str:
        if not raw_value:
            return ""
        if isinstance(raw_value, datetime):
            report_date = raw_value.date()
        else:
            raw_text = str(raw_value)
            try:
                report_date = datetime.fromisoformat(raw_text[:10]).date()
            except ValueError:
                return raw_text

        thai_short_months = [
            "ม.ค.",
            "ก.พ.",
            "มี.ค.",
            "เม.ย.",
            "พ.ค.",
            "มิ.ย.",
            "ก.ค.",
            "ส.ค.",
            "ก.ย.",
            "ต.ค.",
            "พ.ย.",
            "ธ.ค.",
        ]
        thai_day_names = [
            "จันทร์",
            "อังคาร",
            "พุธ",
            "พฤหัสบดี",
            "ศุกร์",
            "เสาร์",
            "อาทิตย์",
        ]
        round_date = datetime.combine(report_date, datetime.min.time()).date() - timedelta(days=1)
        day_name = thai_day_names[round_date.weekday()]
        return (
            f"รายงาน รอบวัน {day_name} ที่ {round_date.day} "
            f"{thai_short_months[round_date.month - 1]} {round_date.year + 543}"
        )


class MoReportNumberedCanvas:
    def __new__(cls, *args: Any, **kwargs: Any) -> Any:
        reportlab = MoPdfCommon.import_reportlab()
        canvas_base = reportlab["Canvas"]

        class _NumberedCanvas(canvas_base):
            def __init__(
                self,
                *canvas_args: Any,
                footer_right_margin: float,
                footer_y: float,
                font_name: str,
                font_bold_name: str,
                font_size: float,
                footer_font_size: float,
                header_title: str,
                header_subtitle: str,
                first_page_suffix: str,
                logo_path: Path | None,
                **canvas_kwargs: Any,
            ) -> None:
                super().__init__(*canvas_args, **canvas_kwargs)
                self._saved_page_states: list[dict[str, Any]] = []
                self._footer_right_margin = footer_right_margin
                self._footer_y = footer_y
                self._font_name = font_name
                self._font_bold_name = font_bold_name
                self._font_size = font_size
                self._footer_font_size = footer_font_size
                self._header_title = header_title
                self._header_subtitle = header_subtitle
                self._first_page_suffix = first_page_suffix
                self._logo_path = logo_path
                self._current_division = ""

            def showPage(self) -> None:
                self._saved_page_states.append(dict(self.__dict__))
                self._startPage()

            def save(self) -> None:
                total_pages = len(self._saved_page_states)
                for page_state in self._saved_page_states:
                    self.__dict__.update(page_state)
                    self._draw_page_number(total_pages)
                    super().showPage()
                super().save()

            def _draw_page_number(self, total_pages: int) -> None:
                self.saveState()
                self._draw_header()
                self.setFont(self._font_name, self._footer_font_size)
                self.drawRightString(
                    self._pagesize[0] - self._footer_right_margin,
                    self._footer_y,
                    f"{self._pageNumber} / {total_pages}",
                )
                self.restoreState()

            def _draw_header(self) -> None:
                page_width, page_height = self._pagesize
                mm = reportlab["mm"]
                padding_x = MoPdfCommon.PAGE_PADDING_X_MM * mm
                padding_y = MoPdfCommon.PAGE_PADDING_Y_MM * mm
                logo_y = page_height - padding_y - (MoPdfCommon.LOGO_HEIGHT_MM * mm)

                self.setFont(self._font_name, self._font_size)
                self.drawRightString(
                    page_width - padding_x,
                    page_height - ((MoPdfCommon.PAGE_PADDING_Y_MM + 3.5) * mm),
                    MoPdfCommon.format_export_datetime(),
                )

                if self._logo_path is not None:
                    logo_width = MoPdfCommon.LOGO_WIDTH_MM * mm
                    logo_height = MoPdfCommon.LOGO_HEIGHT_MM * mm
                    self.drawImage(
                        str(self._logo_path),
                        (page_width - logo_width) / 2,
                        logo_y,
                        width=logo_width,
                        height=logo_height,
                        preserveAspectRatio=True,
                        mask="auto",
                    )

                title_parts = [self._header_title, self._header_subtitle]
                division_name = getattr(self, "_current_division", "") or ""
                if division_name:
                    title_parts.append(division_name)
                if self._pageNumber == 1 and self._first_page_suffix:
                    title_parts.append(self._first_page_suffix)
                title_text = " | ".join(part for part in title_parts if part)

                self.setFont(self._font_bold_name, MoPdfCommon.FONT_SIZE_HEADER_TITLE)
                self.drawCentredString(
                    page_width / 2,
                    page_height - (19.2 * mm),
                    title_text,
                )

        return _NumberedCanvas(*args, **kwargs)
