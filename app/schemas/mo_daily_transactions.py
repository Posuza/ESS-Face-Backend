from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class SectorReportDiscipline(BaseModel):
    """A single discipline/warning item (dynamic key-value)."""

    key: str = ""
    label: str = ""
    value: int = 0

    model_config = ConfigDict(extra="ignore")


class SectorReportProject(BaseModel):
    """group3 — เข้าพบผู้ว่าจ้าง (status: normal/warning/danger)."""

    name: str = ""
    detail: str = ""
    status: str = "normal"
    note: str = ""

    model_config = ConfigDict(extra="ignore")


class GuardPostMovement(BaseModel):
    """group4 — การเปลี่ยนแปลงจุดรักษาการณ์ (status: Thai text or custom)."""

    name: str = ""
    detail: str = ""
    status: str = ""
    note: str = ""

    model_config = ConfigDict(extra="ignore")


class MoDailyTransactionCreate(BaseModel):
    """Flat create — all fields in one body, matching what frontend sends."""

    department_id: int
    department_name: str = ""
    division_id: int = 0
    division_name: str = ""
    created_by: Optional[str] = None
    workflow_status: Optional[str] = None
    approved_by: Optional[str] = None
    approved_status: Optional[str] = None
    approved_remark: Optional[str] = None

    # Detail 1 — หน่วยงานที่รับผิดชอบ
    dept_guard_post_count: int = 0
    dept_current_personnel_count: int = 0
    dept_missing_regular_count: int = 0
    dept_missing_personnel_count: int = 0
    dept_supplement_count: int = 0
    dept_recruitment_count: int = 0
    dept_reserve_units_count: int = 0
    dept_reserve_personnel_count: int = 0

    # Detail 1 — การลา
    leave_personal_count: int = 0
    leave_sick_count: int = 0
    leave_absent_count: int = 0
    leave_deserted_count: int = 0
    leave_resigned_count: int = 0
    leave_terminated_count: int = 0
    leave_extra_1: int = 0
    leave_extra_2: int = 0
    leave_extra_3: int = 0
    leave_extra_4: int = 0
    leave_extra_5: int = 0

    # Detail 1 — การบริหารการควงเวร
    shift_18_count: int = 0
    shift_24_count: int = 0
    shift_36_count: int = 0

    # Detail 1 — อบรม
    training_shift_change_count: int = 0
    training_planned_count: int = 0
    training_supervise_onsite_count: int = 0
    training_supervise_virtual_simulation_count: int = 0

    # Detail 1 — เข้าพบผู้ว่าจ้าง summary
    employer_number_count: int = 0
    employer_problem_count: int = 0

    # Detail 2 — projects/meetings
    projects: List[SectorReportProject] = []

    # Detail 2 — guard post movements
    guard_post_movements: List[GuardPostMovement] = []

    # Dynamic disciplines/warnings
    disciplines: List[SectorReportDiscipline] = []

    model_config = ConfigDict(extra="ignore")


class MoDailyTransactionUpdate(BaseModel):
    """Flat partial update."""

    division_id: int = 0
    division_name: str = ""
    workflow_status: Optional[str] = None
    approved_by: Optional[str] = None
    approved_status: Optional[str] = None
    approved_remark: Optional[str] = None

    dept_guard_post_count: Optional[int] = None
    dept_current_personnel_count: Optional[int] = None
    dept_missing_regular_count: Optional[int] = None
    dept_missing_personnel_count: Optional[int] = None
    dept_supplement_count: Optional[int] = None
    dept_recruitment_count: Optional[int] = None
    dept_reserve_units_count: Optional[int] = None
    dept_reserve_personnel_count: Optional[int] = None

    leave_personal_count: Optional[int] = None
    leave_sick_count: Optional[int] = None
    leave_absent_count: Optional[int] = None
    leave_deserted_count: Optional[int] = None
    leave_resigned_count: Optional[int] = None
    leave_terminated_count: Optional[int] = None
    leave_extra_1: Optional[int] = None
    leave_extra_2: Optional[int] = None
    leave_extra_3: Optional[int] = None
    leave_extra_4: Optional[int] = None
    leave_extra_5: Optional[int] = None

    shift_18_count: Optional[int] = None
    shift_24_count: Optional[int] = None
    shift_36_count: Optional[int] = None

    training_shift_change_count: Optional[int] = None
    training_planned_count: Optional[int] = None
    training_supervise_onsite_count: Optional[int] = None
    training_supervise_virtual_simulation_count: Optional[int] = None

    employer_number_count: Optional[int] = None
    employer_problem_count: Optional[int] = None

    projects: Optional[List[SectorReportProject]] = None

    guard_post_movements: Optional[List[GuardPostMovement]] = None

    # Dynamic disciplines/warnings
    disciplines: Optional[List[SectorReportDiscipline]] = None

    model_config = ConfigDict(extra="ignore")


class MoDailyTransactionResponse(BaseModel):
    """Flat response — same shape as frontend SectorReport."""

    id: int
    mo_daily_transaction_id: int
    department_id: int
    department_name: str = ""
    division_id: int = 0
    division_name: str = ""
    report_date: Optional[str] = None
    status: Optional[str] = None
    workflow_status: Optional[str] = None
    approved_status: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    approved_remark: Optional[str] = None
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    updated_by: Optional[str] = None

    # Detail 1 fields
    dept_guard_post_count: int = 0
    dept_current_personnel_count: int = 0
    dept_missing_regular_count: int = 0
    dept_missing_personnel_count: int = 0
    dept_supplement_count: int = 0
    dept_recruitment_count: int = 0
    dept_reserve_units_count: int = 0
    dept_reserve_personnel_count: int = 0
    leave_personal_count: int = 0
    leave_sick_count: int = 0
    leave_absent_count: int = 0
    leave_deserted_count: int = 0
    leave_resigned_count: int = 0
    leave_terminated_count: int = 0
    leave_extra_1: int = 0
    leave_extra_2: int = 0
    leave_extra_3: int = 0
    leave_extra_4: int = 0
    leave_extra_5: int = 0
    shift_18_count: int = 0
    shift_24_count: int = 0
    shift_36_count: int = 0
    training_shift_change_count: int = 0
    training_planned_count: int = 0
    training_supervise_onsite_count: int = 0
    training_supervise_virtual_simulation_count: int = 0
    employer_number_count: int = 0
    employer_problem_count: int = 0

    # Detail 2 — projects
    projects: List[SectorReportProject] = []

    # Detail 2 — guard post movements
    guard_post_movements: List[GuardPostMovement] = []

    # Dynamic disciplines/warnings
    disciplines: List[SectorReportDiscipline] = []

    model_config = ConfigDict(from_attributes=True)


class MoDailyTransactionWorkflowStatusResponse(BaseModel):
    mo_daily_transaction_id: int
    workflow_status: Optional[str] = None
    updated_by: Optional[str] = None
    updated_by_position_name: Optional[str] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class GuardPostStatusResponse(BaseModel):
    """Simple list of distinct guard post movement statuses."""

    statuses: List[str]
