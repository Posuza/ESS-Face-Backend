from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.services.pdf.builder.util.mo_pdf_common import MoPdfCommon


class MoPdfSections:
    """
    Builds the MO report with ReportLab.

    Layout model:
    - A page can hold several sections, packed side by side in up to
      ``columns_per_page`` columns (magazine style). Sections flow in order:
      fill the current column, then the next column, then the next page.
    - A section taller than a whole page is emitted standalone (not inside a
      column) so ReportLab splits it across pages and repeats its header via
      ``repeatRows``.
    - Row heights are never guessed: tables size their own rows from the
      wrapped content, and the only height used for column packing comes from
      ``Table.wrap`` (the same calculation ReportLab uses when rendering), so
      a section can never silently overflow its page.

    The report has exactly three sections:

    - ``summary_section``   cross-division summary tables (summary PDF only)
    - ``division_section``  one division's group tables (both PDFs, one per division)
    - ``detail_section``    one division's detail tables (both PDFs, one per division)

    The PDF builders compose them: summary PDF = summary_section followed by
    (division_section + detail_section) for each division; division PDF =
    (division_section + detail_section) for each division. Page breaks between
    sections are added by the builders, not here.
    """

    TABLE_GAP_MM = 2
    ROW_HEIGHT_MM = 6.2
    INDEX_WIDTH_MM = 9
    PAGINATION_SAFETY_MM = 4

    # ------------------------------------------------------------------
    # Helpers (top)
    # ------------------------------------------------------------------

    @classmethod
    def _two_column_table_width(cls) -> float:
        return (MoPdfCommon.BODY_WIDTH_MM - cls.TABLE_GAP_MM) / 2

    @staticmethod
    def _flowable_height_mm(reportlab: Mapping[str, Any], flowable: Any, width_mm: float) -> float:
        _wrapped_width, wrapped_height = flowable.wrap(width_mm * reportlab["mm"], 1_000_000)
        return wrapped_height / reportlab["mm"]

    @staticmethod
    def _chunks(items: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
        return [items[index : index + size] for index in range(0, len(items), size)]

    @staticmethod
    def _division_header(row: Mapping[str, Any]) -> str:
        name = str(row.get("division_name") or "").strip()
        return name or "-"

    @classmethod
    def _division_groups(cls, row: Mapping[str, Any]) -> list[tuple[str, list[dict[str, Any]]]]:
        groups: list[tuple[str, list[dict[str, Any]]]] = []
        for title, items in MoPdfCommon.FIELD_GROUPS:
            groups.append(
                (
                    title,
                    [
                        {
                            "label": label,
                            "display_value": MoPdfCommon.display_number(
                                MoPdfCommon.number(row.get(key, 0))
                            ),
                            "unit": unit,
                        }
                        for key, label, unit in items
                    ],
                )
            )

        disciplines = [
            {
                "label": item.get("label") or item.get("name") or "-",
                "display_value": MoPdfCommon.display_number(MoPdfCommon.number(item.get("value"))),
                "unit": "คน",
            }
            for item in row.get("disciplines") or []
            if isinstance(item, Mapping)
        ]
        groups.append(("วินัยและการลงโทษ", disciplines))

        projects: list[dict[str, Any]] = [
            {
                "label": "เข้าพบผู้ว่าจ้าง",
                "display_value": MoPdfCommon.display_number(MoPdfCommon.number(row.get("employer_number_count"))),
                "unit": "หน่วยงาน",
            },
            {
                "label": "พบปัญหา",
                "display_value": MoPdfCommon.display_number(MoPdfCommon.number(row.get("employer_problem_count"))),
                "unit": "หน่วยงาน",
            },
        ]
        for item in row.get("projects") or []:
            if not isinstance(item, Mapping):
                continue
            projects.append(
                {
                    "label": item.get("project_name") or item.get("name") or "-",
                    "display_value": MoPdfCommon.status_label(item.get("status")),
                    "status": item.get("status"),
                    "unit": "",
                }
            )
        groups.append(("เข้าพบผู้ว่าจ้าง", projects))

        guard_counts: dict[str, int] = {}
        for item in row.get("guard_post_movements") or []:
            if not isinstance(item, Mapping):
                continue
            status_text = str(item.get("status") or "").strip()
            if status_text:
                guard_counts[status_text] = guard_counts.get(status_text, 0) + 1
        guards = [
            {
                "label": status_text,
                "display_value": MoPdfCommon.display_number(count),
                "unit": "หน่วยงาน",
            }
            for status_text, count in guard_counts.items()
        ]
        groups.append(("การเปลี่ยนแปลงจุดรักษาการณ์", guards))
        return groups

    @classmethod
    def _division_group_table(
        cls,
        reportlab: Mapping[str, Any],
        styles: Mapping[str, Any],
        *,
        group_index: int,
        title: str,
        items: list[dict[str, Any]],
        width_mm: float,
    ) -> Any:
        p = MoPdfCommon.paragraph
        pc = MoPdfCommon.center_paragraph
        hp = MoPdfCommon.header_paragraph
        hpc = MoPdfCommon.header_center_paragraph
        display_items = items or []
        # Empty strings in a header row make ReportLab inflate that row's
        # height; use empty Paragraphs so the division header bar matches the
        # summary/detail header bars (see _summary_group_table).
        data = [
            [
                hpc(reportlab, styles, str(group_index)),
                hp(reportlab, styles, title),
                pc(reportlab, styles, ""),
                pc(reportlab, styles, ""),
            ]
        ]
        status_rows: list[tuple[int, Any]] = []

        if not display_items:
            data.append(
                [
                    pc(reportlab, styles, ""),
                    pc(reportlab, styles, "<ไม่มีข้อมูล>"),
                    pc(reportlab, styles, ""),
                    pc(reportlab, styles, ""),
                ]
            )
        else:
            for item_index, item in enumerate(display_items, start=1):
                data.append(
                    [
                        pc(reportlab, styles, f"{group_index}.{item_index}"),
                        p(reportlab, styles, item.get("label")),
                        pc(reportlab, styles, item.get("display_value")),
                        pc(reportlab, styles, item.get("unit")),
                    ]
                )
                if item.get("status"):
                    status_rows.append((len(data) - 1, item.get("status")))

        index_width = cls.INDEX_WIDTH_MM
        value_width = min(12, width_mm * 0.18)
        unit_width = min(13, width_mm * 0.22)
        label_width = max(width_mm - index_width - value_width - unit_width, 1)

        table = reportlab["Table"](
            data,
            colWidths=[
                index_width * reportlab["mm"],
                label_width * reportlab["mm"],
                value_width * reportlab["mm"],
                unit_width * reportlab["mm"],
            ],
        )
        style = MoPdfCommon.table_style(reportlab)
        style.add("MINROWHEIGHTS", (0, 0), (-1, -1), cls.ROW_HEIGHT_MM * reportlab["mm"])
        style.add("SPAN", (1, 0), (-1, 0))
        if not display_items:
            style.add("SPAN", (1, 1), (-1, 1))
            style.add("ALIGN", (1, 1), (-1, 1), "CENTER")
        for row_index, status in status_rows:
            style.add("SPAN", (2, row_index), (3, row_index))
            style.add(
                "TEXTCOLOR",
                (2, row_index),
                (3, row_index),
                MoPdfCommon.status_color(reportlab, status),
            )
        style.add("ALIGN", (0, 0), (0, -1), "CENTER")
        style.add("ALIGN", (2, 1), (-1, -1), "CENTER")
        table.setStyle(style)
        table.hAlign = "CENTER"
        table.repeatRows = 1
        return table

    @classmethod
    def _division_group_blocks(
        cls,
        reportlab: Mapping[str, Any],
        styles: Mapping[str, Any],
        row: Mapping[str, Any],
    ) -> list[tuple[Any, float]]:
        table_width_mm = cls._two_column_table_width()
        blocks: list[tuple[Any, float]] = []
        for index, (title, items) in enumerate(cls._division_groups(row), start=1):
            table = cls._division_group_table(
                reportlab,
                styles,
                group_index=index,
                title=title,
                items=items,
                width_mm=table_width_mm,
            )
            blocks.append(
                (table, cls._flowable_height_mm(reportlab, table, table_width_mm))
            )
        return blocks

    @classmethod
    def _summary_groups(
        cls,
        rows: list[dict[str, Any]],
    ) -> list[tuple[str, list[tuple[str, str, str, str | None]]]]:
        groups: list[tuple[str, list[tuple[str, str, str, str | None]]]] = [
            (title, [(key, label, unit, None) for key, label, unit in items])
            for title, items in MoPdfCommon.FIELD_GROUPS
        ]

        discipline_items: dict[str, tuple[str, str, str, str | None]] = {}
        for row in rows:
            for item in row.get("disciplines") or []:
                if not isinstance(item, Mapping):
                    continue
                label = str(item.get("label") or item.get("name") or "-")
                key = str(item.get("key") or label)
                discipline_items.setdefault(key, (key, label, "คน", None))
        groups.append(("วินัยและการลงโทษ", list(discipline_items.values())))

        groups.append(
            (
                "เข้าพบผู้ว่าจ้าง",
                [
                    ("employer_number_count", "เข้าพบผู้ว่าจ้าง", "หน่วยงาน", None),
                    ("employer_problem_count", "พบปัญหา", "หน่วยงาน", None),
                    ("warning", "ผิดปกติ", "หน่วยงาน", "warning"),
                    ("danger", "ฉุกเฉิน", "หน่วยงาน", "danger"),
                ],
            )
        )

        guard_statuses = []
        seen_statuses = set()
        for row in rows:
            for item in row.get("guard_post_movements") or []:
                if not isinstance(item, Mapping):
                    continue
                status_text = str(item.get("status") or "").strip()
                if status_text and status_text not in seen_statuses:
                    seen_statuses.add(status_text)
                    guard_statuses.append((status_text, status_text, "หน่วยงาน", status_text))
        groups.append(("การเปลี่ยนแปลงจุดรักษาการณ์", guard_statuses))
        return groups

    @classmethod
    def _summary_display_items(
        cls,
        *,
        title: str,
        items: list[tuple[str, str, str, str | None]],
        rows: list[dict[str, Any]],
    ) -> list[tuple[str, str, list[int], int]]:
        display_items: list[tuple[str, str, list[int], int]] = []
        for key, label, unit, status_key in items:
            values = [
                cls._summary_item_value(row, key=key, group_title=title, status_key=status_key)
                for row in rows
            ]
            total = sum(values)
            if title in {"เข้าพบผู้ว่าจ้าง", "การเปลี่ยนแปลงจุดรักษาการณ์"} and total <= 0:
                continue
            display_items.append((label, unit, values, total))
        if title == "วินัยและการลงโทษ" and all(total <= 0 for *_rest, total in display_items):
            return []
        return display_items

    @staticmethod
    def _summary_item_value(
        row: Mapping[str, Any],
        *,
        key: str,
        group_title: str,
        status_key: str | None,
    ) -> int:
        if group_title == "วินัยและการลงโทษ":
            for item in row.get("disciplines") or []:
                if isinstance(item, Mapping) and str(item.get("key")) == key:
                    return MoPdfCommon.number(item.get("value"))
            return 0

        if group_title == "เข้าพบผู้ว่าจ้าง" and status_key:
            return MoPdfCommon.project_status_count(row, status_key)

        if group_title == "การเปลี่ยนแปลงจุดรักษาการณ์" and status_key:
            return sum(
                1
                for item in row.get("guard_post_movements") or []
                if isinstance(item, Mapping) and str(item.get("status") or "") == status_key
            )

        return MoPdfCommon.number(row.get(key))

    @classmethod
    def _summary_group_table(
        cls,
        reportlab: Mapping[str, Any],
        styles: Mapping[str, Any],
        *,
        group_index: int,
        title: str,
        items: list[tuple[str, str, str, str | None]],
        rows: list[dict[str, Any]],
    ) -> Any:
        p = MoPdfCommon.paragraph
        pc = MoPdfCommon.center_paragraph
        hp = MoPdfCommon.header_paragraph
        hpc = MoPdfCommon.header_center_paragraph
        display_items = cls._summary_display_items(title=title, items=items, rows=rows)
        data = [
            [
                hpc(reportlab, styles, str(group_index)),
                hp(reportlab, styles, title),
                *[pc(reportlab, styles, "") for _ in range(len(rows) + 2)],
            ],
        ]

        if not display_items:
            data.append([
                pc(reportlab, styles, "<ไม่มีข้อมูล>"),
                pc(reportlab, styles, ""),
                *[pc(reportlab, styles, "") for _ in rows],
                pc(reportlab, styles, ""),
                pc(reportlab, styles, ""),
            ])
        else:
            data.append(
                [
                    hpc(reportlab, styles, "หัวข้อ"),
                    hpc(reportlab, styles, ""),
                    *[hpc(reportlab, styles, cls._division_header(row)) for row in rows],
                    hpc(reportlab, styles, "รวม"),
                    hpc(reportlab, styles, ""),
                ]
            )
            for index, (label, unit, values, total) in enumerate(display_items, start=1):
                data.append([
                    pc(reportlab, styles, f"{group_index}.{index}"),
                    p(reportlab, styles, label),
                    *[pc(reportlab, styles, MoPdfCommon.display_number(value)) for value in values],
                    pc(reportlab, styles, MoPdfCommon.display_number(total)),
                    pc(reportlab, styles, unit),
                ])

        division_width = 10 if len(rows) < 5 else 18
        label_width = max(
            32,
            (
                MoPdfCommon.BODY_WIDTH_MM
                if len(rows) >= 5
                else MoPdfSections._two_column_table_width()
            )
            - cls.INDEX_WIDTH_MM
            - (len(rows) * division_width)
            - 10
            - 12.5,
        )
        table = reportlab["Table"](
            data,
            colWidths=[
                cls.INDEX_WIDTH_MM * reportlab["mm"],
                label_width * reportlab["mm"],
                *[division_width * reportlab["mm"] for _ in rows],
                10 * reportlab["mm"],
                12.5 * reportlab["mm"],
            ],
        )
        style = MoPdfCommon.table_style(reportlab)
        style.add("MINROWHEIGHTS", (0, 0), (-1, -1), cls.ROW_HEIGHT_MM * reportlab["mm"])
        style.add("SPAN", (1, 0), (-1, 0))
        style.add("ALIGN", (0, 0), (0, -1), "CENTER")
        if not display_items:
            style.add("SPAN", (0, 1), (-1, 1))
            style.add("ALIGN", (0, 1), (-1, 1), "CENTER")
        else:
            style.add("SPAN", (0, 1), (1, 1))
            style.add("BACKGROUND", (0, 1), (-1, 1), reportlab["colors"].white)
            style.add("ALIGN", (0, 1), (1, 1), "CENTER")
            style.add("ALIGN", (2, 1), (-1, -1), "CENTER")
        table.setStyle(style)
        table.hAlign = "CENTER"
        table.repeatRows = 2
        return table

    @classmethod
    def _columns_table(
        cls,
        *,
        reportlab: Mapping[str, Any],
        columns: list[list[Any]],
        table_width_mm: float,
    ) -> Any:
        gap_width_mm = cls.TABLE_GAP_MM
        row: list[Any] = []
        col_widths = []
        for index, column in enumerate(columns):
            if index:
                row.append("")
                col_widths.append(gap_width_mm * reportlab["mm"])
            row.append(column)
            col_widths.append(table_width_mm * reportlab["mm"])

        table = reportlab["Table"](
            [row],
            colWidths=col_widths,
            style=reportlab["TableStyle"](
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            ),
        )
        table.hAlign = "CENTER"
        return table

    @classmethod
    def _paginated_columns(
        cls,
        *,
        reportlab: Mapping[str, Any],
        blocks: list[tuple[Any, float]],
        table_width_mm: float,
        columns_per_page: int,
    ) -> list[Any]:
        """
        Pack section blocks into columns, page by page.

        Rules (sections keep their order):
        - A block that fits the remaining space of the current column is placed
          there; otherwise it moves to the next column, and if that does not
          fit either, the current page is flushed and the block starts a new
          page.
        - A block taller than a full page is emitted standalone so ReportLab
          can split it across pages and repeat its header row.
        """
        story: list[Any] = []
        page_columns: list[list[Any]] = [[] for _ in range(columns_per_page)]
        heights = [0.0 for _ in range(columns_per_page)]
        column_index = 0
        available_height_mm = MoPdfCommon.BODY_HEIGHT_MM - cls.PAGINATION_SAFETY_MM

        def flush() -> None:
            nonlocal page_columns, heights, column_index
            used_columns = [column for column in page_columns if column]
            if not used_columns:
                return
            story.append(
                cls._columns_table(
                    reportlab=reportlab,
                    columns=used_columns,
                    table_width_mm=table_width_mm,
                )
            )
            story.append(reportlab["PageBreak"]())
            page_columns = [[] for _ in range(columns_per_page)]
            heights = [0.0 for _ in range(columns_per_page)]
            column_index = 0

        block_count = len(blocks)
        for block_index, (block, estimated_height) in enumerate(blocks):
            if estimated_height > available_height_mm:
                flush()
                story.append(block)
                if block_index + 1 < block_count:
                    story.append(reportlab["PageBreak"]())
                continue

            gap = cls.TABLE_GAP_MM if page_columns[column_index] else 0
            if heights[column_index] + gap + estimated_height > available_height_mm:
                if column_index < columns_per_page - 1:
                    column_index += 1
                else:
                    flush()
            if page_columns[column_index]:
                page_columns[column_index].append(reportlab["Spacer"](1, cls.TABLE_GAP_MM * reportlab["mm"]))
            page_columns[column_index].append(block)
            heights[column_index] += (
                (cls.TABLE_GAP_MM if heights[column_index] else 0) + estimated_height
            )

        before_flush_count = len(story)
        flush()
        if len(story) > before_flush_count and story and story[-1].__class__.__name__ == "PageBreak":
            story.pop()
        return story

    @classmethod
    def _detail_header_table(
        cls,
        reportlab: Mapping[str, Any],
        styles: Mapping[str, Any],
        group_index: int,
        title: str,
        width_mm: float,
    ) -> Any:
        """The group's header bar (number + title), shown on every page of the group."""
        hp = MoPdfCommon.header_paragraph
        hpc = MoPdfCommon.header_center_paragraph
        label_width = min(18, width_mm * 0.18)
        value_width = max(width_mm - label_width, 1)
        table = reportlab["Table"](
            [[hpc(reportlab, styles, str(group_index)), hp(reportlab, styles, title)]],
            colWidths=[
                label_width * reportlab["mm"],
                value_width * reportlab["mm"],
            ],
        )
        style = MoPdfCommon.table_style(reportlab)
        style.add("SPAN", (1, 0), (-1, 0))
        style.add("ALIGN", (0, 0), (0, -1), "CENTER")
        table.setStyle(style)
        table.hAlign = "CENTER"
        return table

    @classmethod
    def _detail_item_table(
        cls,
        reportlab: Mapping[str, Any],
        styles: Mapping[str, Any],
        *,
        group_index: int,
        item_index: int,
        item: Mapping[str, Any],
        width_mm: float,
    ) -> Any:
        p = MoPdfCommon.detail_paragraph
        pc = MoPdfCommon.detail_center_paragraph
        pw = MoPdfCommon.detail_wrapped_paragraph
        label = item.get("project_name") or item.get("label") or item.get("name") or "-"
        detail = item.get("detail") or "-"
        status = MoPdfCommon.status_label(item.get("status"))
        note = item.get("note") or "-"
        label_width = min(18, width_mm * 0.18)
        value_width = max(width_mm - label_width, 1)

        data = [
            [pc(reportlab, styles, f"{group_index}.{item_index}"), p(reportlab, styles, label)],
            [pc(reportlab, styles, "รายละเอียด"), pw(reportlab, styles, detail, width_mm=value_width)],
            [pc(reportlab, styles, "สถานะ"), p(reportlab, styles, status)],
            [pc(reportlab, styles, "หมายเหตุ"), pw(reportlab, styles, note, width_mm=value_width)],
        ]
        table = reportlab["Table"](
            data,
            colWidths=[
                label_width * reportlab["mm"],
                value_width * reportlab["mm"],
            ],
        )
        style = MoPdfCommon.table_style(reportlab)
        # The shared style paints row 0 as a header; the item label row is not
        # a header (the group header bar above it is), so strip the background.
        style.add("BACKGROUND", (0, 0), (-1, 0), reportlab["colors"].white)
        style.add("MINROWHEIGHTS", (0, 0), (-1, -1), cls.ROW_HEIGHT_MM * reportlab["mm"])
        style.add("ALIGN", (0, 0), (0, -1), "CENTER")
        if item.get("status"):
            style.add(
                "TEXTCOLOR",
                (1, 2),
                (1, 2),
                MoPdfCommon.status_color(reportlab, item.get("status")),
            )
        table.setStyle(style)
        table.hAlign = "CENTER"
        table.repeatRows = 1
        return table

    @classmethod
    def _detail_groups_story(
        cls,
        reportlab: Mapping[str, Any],
        styles: Mapping[str, Any],
        sections: list[tuple[int, str, list[Mapping[str, Any]]]],
        width_mm: float,
    ) -> list[Any]:
        """One continuous centered column across every detail group.

        Each project/movement is one table. Only the single table that does not
        fit the remaining page space moves to the next page — never a whole
        group. The active group's header bar is repeated at the top of every
        page the group spans.
        """
        available_h = MoPdfCommon.BODY_HEIGHT_MM - cls.PAGINATION_SAFETY_MM
        story: list[Any] = []
        page_items: list[Any] = []
        used_h = 0.0
        active_header: Any = None
        active_header_h = 0.0
        last_was_header = False

        def flush() -> None:
            nonlocal page_items, used_h
            if not page_items:
                return
            story.append(
                cls._columns_table(
                    reportlab=reportlab,
                    columns=[page_items],
                    table_width_mm=width_mm,
                )
            )
            story.append(reportlab["PageBreak"]())
            page_items = []
            used_h = 0.0

        def add(block: Any, height: float, *, is_header: bool = False) -> None:
            nonlocal used_h, last_was_header
            if height > available_h:
                # Taller than a full page: emit standalone so ReportLab can
                # split it across pages and repeat its label row (repeatRows).
                flush()
                story.append(block)
                last_was_header = False
                return
            if page_items and used_h + cls.TABLE_GAP_MM + height > available_h:
                flush()
            # Every page that holds items opens with the active group's header
            # bar (unless the block being placed is the header itself).
            if not page_items and not is_header and active_header is not None:
                page_items.append(active_header)
                used_h += active_header_h
                last_was_header = True
            # No gap right after the group's header bar; other tables are
            # separated by TABLE_GAP_MM.
            if page_items and not last_was_header:
                page_items.append(reportlab["Spacer"](1, cls.TABLE_GAP_MM * reportlab["mm"]))
                used_h += cls.TABLE_GAP_MM
            page_items.append(block)
            used_h += height
            last_was_header = is_header

        for group_index, title, items in sections:
            normalized = [item for item in items if isinstance(item, Mapping)]
            if not normalized:
                continue
            header = cls._detail_header_table(reportlab, styles, group_index, title, width_mm)
            active_header = header
            active_header_h = cls._flowable_height_mm(reportlab, header, width_mm)
            first_item = cls._detail_item_table(
                reportlab,
                styles,
                group_index=group_index,
                item_index=1,
                item=normalized[0],
                width_mm=width_mm,
            )
            first_h = cls._flowable_height_mm(reportlab, first_item, width_mm)
            # Keep the header with its first item (no gap between them) so the
            # header bar never sits alone at the bottom of a page.
            if page_items and used_h + cls.TABLE_GAP_MM + active_header_h + first_h > available_h:
                flush()
            add(header, active_header_h, is_header=True)
            add(first_item, first_h)
            for item_index, item in enumerate(normalized[1:], start=2):
                block = cls._detail_item_table(
                    reportlab,
                    styles,
                    group_index=group_index,
                    item_index=item_index,
                    item=item,
                    width_mm=width_mm,
                )
                add(block, cls._flowable_height_mm(reportlab, block, width_mm))

        before_flush_count = len(story)
        flush()
        if len(story) > before_flush_count and story and story[-1].__class__.__name__ == "PageBreak":
            story.pop()
        return story

    # ------------------------------------------------------------------
    # The three public sections (bottom)
    # ------------------------------------------------------------------

    @classmethod
    def division_section(
        cls,
        reportlab: Mapping[str, Any],
        styles: Mapping[str, Any],
        row: Mapping[str, Any],
    ) -> list[Any]:
        """One division's group tables, packed into 2-column pages."""
        return cls._paginated_columns(
            reportlab=reportlab,
            blocks=cls._division_group_blocks(reportlab, styles, row),
            table_width_mm=cls._two_column_table_width(),
            columns_per_page=2,
        )

    @classmethod
    def summary_section(
        cls,
        reportlab: Mapping[str, Any],
        styles: Mapping[str, Any],
        rows: list[dict[str, Any]],
    ) -> list[Any]:
        division_count = max(len(rows), 1)
        columns_per_page = 1 if division_count >= 5 else 2
        table_width_mm = (
            MoPdfCommon.BODY_WIDTH_MM
            if columns_per_page == 1
            else cls._two_column_table_width()
        )
        blocks: list[tuple[Any, float]] = []
        for group_index, (title, items) in enumerate(cls._summary_groups(rows), start=1):
            for chunk in cls._chunks(rows, 5 if division_count >= 5 else len(rows)):
                table = cls._summary_group_table(
                    reportlab,
                    styles,
                    group_index=group_index,
                    title=title,
                    items=items,
                    rows=chunk,
                )
                blocks.append(
                    (
                        table,
                        cls._flowable_height_mm(reportlab, table, table_width_mm),
                    )
                )
        return cls._paginated_columns(
            reportlab=reportlab,
            blocks=blocks,
            table_width_mm=table_width_mm,
            columns_per_page=columns_per_page,
        )

    @classmethod
    def detail_section(
        cls,
        reportlab: Mapping[str, Any],
        styles: Mapping[str, Any],
        row: Mapping[str, Any],
    ) -> list[Any]:
        """One division's detail tables, in one continuous centered column.

        Projects and movements are each a *group of tables*: the group header
        bar (number + title) repeats at the top of every page the group spans,
        followed by one table per item. Only the single table that does not
        fit the remaining page space moves to the next page — never a whole
        group.
        """
        width_mm = MoPdfCommon.BODY_WIDTH_MM * 0.6
        sections = [
            (6, "รายละเอียด เพิ่มเติม : เข้าพบผู้ว่าจ้าง", row.get("projects") or []),
            (
                7,
                "รายละเอียด เพิ่มเติม : การเปลี่ยนแปลงจุดรักษาการณ์",
                row.get("guard_post_movements") or [],
            ),
        ]
        return cls._detail_groups_story(reportlab, styles, sections, width_mm)
