from __future__ import annotations

from typing import Final

# =========================================================
# MO — Audit action messages
# =========================================================
MO_REPORT_CREATED: Final[str] = (
    "MO report created: report_id={report_id}, department_id={department_id}, "
    "division_id={division_id}"
)

MO_REPORT_UPDATED: Final[str] = (
    "MO report updated: report_id={report_id}, changes={changes}"
)

MO_REPORT_DELETED: Final[str] = (
    "MO report deleted: report_id={report_id}, department_id={department_id}, "
    "division_id={division_id}"
)

MO_REPORT_APPROVED: Final[str] = (
    "MO report approved: report_id={report_id}, old_status={old_status}, "
    "new_status={new_status}"
)

MO_REPORT_REJECTED: Final[str] = (
    "MO report sent back: report_id={report_id}, old_status={old_status}, "
    "new_status={new_status}, remark={remark}"
)

MO_REPORT_UPDATE_DENIED: Final[str] = (
    "MO report update denied: report_id={report_id}, "
    "actor={actor}, requested_status={requested_status}, "
    "reason={reason}"
)

MO_REPORT_NOT_FOUND: Final[str] = (
    "MO report not found: report_id={report_id}, actor={actor}, "
    "operation={operation}"
)
