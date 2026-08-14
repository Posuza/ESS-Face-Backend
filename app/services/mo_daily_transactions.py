from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from fastapi import HTTPException, status as http_status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.audit_logger import audit_logger
from app.core.mo.config import ACCESS_FIELD_ONLY, get_employee_access_level
from app.core.mo.scope import (
    actor_has_department_scope,
    enforce_division_scope,
    enforce_report_scope,
    enforce_same_department,
    validate_department_exists,
    validate_division_belongs_to_department,
    validate_report_scope_is_active,
)
from app.core.mo.workflow_access import (
    actor_can_edit_rejected_workflow,
    can_approve_workflow_step,
    can_edit_report_content,
    can_send_back_workflow_step,
    can_approve,
    enforce_edit_owner_or_approver,
    has_department_authority,
    ensure_actor_owns_workflow,
    is_admin,
    workflow_rank,
)
from app.core.mo.workflow_status import (
    WORKFLOW_APPROVED,
    WORKFLOW_EDITING,
    WORKFLOW_RETURNED_TO,
    WORKFLOW_WAITING,
    initial_workflow_status,
    make_workflow_status,
    next_workflow_rank,
    previous_workflow_rank,
    split_workflow_status,
    workflow_rank_label,
)
from app.core.registries import (
    MO_REPORT_APPROVED,
    MO_REPORT_CREATED,
    MO_REPORT_DELETED,
    MO_REPORT_NOT_FOUND,
    MO_REPORT_REJECTED,
    MO_REPORT_UPDATE_DENIED,
    MO_REPORT_UPDATED,
)
from app.models.departments import Department
from app.models.divisions import Division
from app.models.employees import Employee
from app.models.mo_daily_transaction_details import MoDailyTransactionDetail1
from app.models.mo_daily_transaction_project import MoDailyTransactionProject
from app.models.mo_daily_transactions import ApprovedStatusEnum, MoDailyTransaction
from app.models.mo_transaction_discipline_warning import MoTransactionDisciplineWarning
from app.models.positions import Position
from app.schemas.mo_daily_transactions import (
    MoDailyTransactionCreate,
    MoDailyTransactionResponse,
    MoDailyTransactionUpdate,
    SectorReportDiscipline,
    SectorReportProject,
)

# ─── All Detail 1 column names (map directly to model columns) ────────────
DETAIL_1_COLUMNS = [
    # dept
    "dept_guard_post_count",
    "dept_current_personnel_count",
    "dept_missing_regular_count",
    "dept_missing_personnel_count",
    "dept_supplement_count",
    "dept_recruitment_count",
    "dept_reserve_units_count",
    "dept_reserve_personnel_count",
    "dept_extra_1",
    "dept_extra_2",
    "dept_extra_3",
    "dept_extra_4",
    "dept_extra_5",
    # leave
    "leave_personal_count",
    "leave_sick_count",
    "leave_absent_count",
    "leave_deserted_count",
    "leave_resigned_count",
    "leave_terminated_count",
    "leave_extra_1",
    "leave_extra_2",
    "leave_extra_3",
    "leave_extra_4",
    "leave_extra_5",
    # shift
    "shift_18_count",
    "shift_24_count",
    "shift_36_count",
    "shift_extra_1",
    "shift_extra_2",
    "shift_extra_3",
    "shift_extra_4",
    "shift_extra_5",
    # training
    "training_shift_change_count",
    "training_planned_count",
    "training_supervise_onsite_count",
    "training_supervise_virtual_simulation_count",
    "training_extra_2",
    "training_extra_3",
    # employer visit summary
    "employer_number_count",
    "employer_problem_count",
]
DETAIL_1_SET = set(DETAIL_1_COLUMNS)

class MoDailyTransactionService:
    """Service layer for MO Daily Transaction operations.

    All public methods follow the same pattern:
      - ``db`` is injected by the caller (FastAPI ``Depends(get_db)``)
      - ``actor_employee`` is resolved by the ``@active_employee_required`` decorator
    """

    # ─── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _as_int(value, default: int = 0) -> int:
        if value is None or value == "":
            return default
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _initial_workflow_status(actor: Employee) -> str:
        actor_rank = workflow_rank(actor)
        return initial_workflow_status(actor_rank)

    @staticmethod
    def _normalize_flat(data: dict) -> dict:
        """Return a mutable copy of data."""
        return dict(data)

    @staticmethod
    def _format_audit_value(value) -> str:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, date):
            return value.isoformat()
        if value is None:
            return "null"
        return repr(value)

    @staticmethod
    def _format_audit_changes(
        old_data: dict, new_data: dict, changed_fields: set[str]
    ) -> str:
        changes = []
        for field in sorted(changed_fields):
            old_value = old_data.get(field)
            new_value = new_data.get(field)
            if old_value != new_value:
                changes.append(
                    f"{field}: "
                    f"{MoDailyTransactionService._format_audit_value(old_value)} -> "
                    f"{MoDailyTransactionService._format_audit_value(new_value)}"
                )
        return "; ".join(changes) if changes else "no changes"

    @staticmethod
    def _build_response(txn: MoDailyTransaction, db: Session) -> dict:
        """Build a flat response dict from a transaction + its detail rows."""
        data = {
            "id": txn.mo_daily_transaction_id,
            "mo_daily_transaction_id": txn.mo_daily_transaction_id,
            "department_id": txn.department_id,
            "department_name": txn.department_name,
            "division_id": txn.division_id,
            "division_name": txn.division_name,
            "report_date": txn.created_at.date().isoformat()
            if txn.created_at
            else None,
            "status": txn.approved_status.value if txn.approved_status else None,
            "workflow_status": txn.workflow_status,
            "approved_status": txn.approved_status.value
            if txn.approved_status
            else None,
            "approved_by": txn.approved_by,
            "approved_at": txn.approved_at,
            "approved_remark": txn.approved_remark,
            "created_by": txn.created_by,
            "created_at": txn.created_at,
            "updated_at": txn.updated_at,
            "updated_by": txn.updated_by,
        }

        # Default all detail1 fields to 0
        for col in DETAIL_1_COLUMNS:
            data[col] = 0

        # Load the single detail1 row (1:1 with transaction)
        d1 = (
            db.execute(
                select(MoDailyTransactionDetail1).where(
                    MoDailyTransactionDetail1.mo_daily_transaction_id
                    == txn.mo_daily_transaction_id
                )
            )
            .scalars()
            .first()
        )
        if d1:
            for col in DETAIL_1_COLUMNS:
                data[col] = MoDailyTransactionService._as_int(getattr(d1, col, "0"))

        # Load disciplines
        discipline_rows = (
            db.execute(
                select(MoTransactionDisciplineWarning)
                .where(
                    MoTransactionDisciplineWarning.mo_daily_transaction_id
                    == txn.mo_daily_transaction_id
                )
                .order_by(MoTransactionDisciplineWarning.created_at)
            )
            .scalars()
            .all()
        )

        disciplines = []
        for row in discipline_rows:
            disciplines.append(
                {
                    "key": row.key,
                    "label": row.label,
                    "value": MoDailyTransactionService._as_int(row.value),
                }
            )
        data["disciplines"] = disciplines

        # Load projects
        project_rows = (
            db.execute(
                select(MoDailyTransactionProject)
                .where(
                    MoDailyTransactionProject.mo_daily_transaction_id
                    == txn.mo_daily_transaction_id
                )
                .order_by(MoDailyTransactionProject.created_at)
            )
            .scalars()
            .all()
        )

        projects = []
        guard_post_movements = []
        for row in project_rows:
            item = {
                "name": row.project_name,
                "detail": row.detail or "",
                "status": row.status or "",
                "note": row.note or "",
            }
            if row.status in ("normal", "warning", "danger"):
                projects.append(item)
            else:
                guard_post_movements.append(item)
        data["projects"] = projects
        data["guard_post_movements"] = guard_post_movements

        return data

    @staticmethod
    def _replace_detail1(db: Session, txn_id: int, payload: dict) -> None:
        db.execute(
            delete(MoDailyTransactionDetail1).where(
                MoDailyTransactionDetail1.mo_daily_transaction_id == txn_id
            )
        )
        values = {"mo_daily_transaction_id": txn_id}
        for col in DETAIL_1_COLUMNS:
            values[col] = MoDailyTransactionService._as_int(payload.get(col))
        db.add(MoDailyTransactionDetail1(**values))

    @staticmethod
    def _get_next_discipline_custom_id(db: Session) -> int:
        """Find the biggest numeric suffix from discipline_custom_N keys."""
        rows = (
            db.execute(
                select(MoTransactionDisciplineWarning.key).where(
                    MoTransactionDisciplineWarning.key.like("discipline_custom_%")
                )
            )
            .scalars()
            .all()
        )
        max_num = 0
        for key in rows:
            parts = key.rsplit("_", 1)
            if len(parts) == 2:
                try:
                    num = int(parts[1])
                    if num > max_num:
                        max_num = num
                except ValueError:
                    pass
        return max_num

    @staticmethod
    def _replace_disciplines(db: Session, txn_id: int, payload: dict) -> None:
        existing_keys_by_label = {
            str(label).strip(): key
            for key, label in db.execute(
                select(
                    MoTransactionDisciplineWarning.key,
                    MoTransactionDisciplineWarning.label,
                ).where(
                    MoTransactionDisciplineWarning.key.like("discipline_custom_%")
                )
            ).all()
            if key and label and str(label).strip()
        }

        db.execute(
            delete(MoTransactionDisciplineWarning).where(
                MoTransactionDisciplineWarning.mo_daily_transaction_id == txn_id
            )
        )
        rows = []
        next_custom_id = MoDailyTransactionService._get_next_discipline_custom_id(db)
        for disc_data in payload.get("disciplines") or []:
            if hasattr(disc_data, "model_dump"):
                disc_data = disc_data.model_dump()
            elif not isinstance(disc_data, dict):
                disc_data = dict(disc_data)

            # Auto-generate key only if null/empty or starts with "auto_gen".
            # Existing "discipline_custom_N" keys are kept as-is. If the same
            # custom label already exists, reuse its key instead of making a new one.
            raw_key = str(disc_data.get("key", "") or "")
            label = str(disc_data.get("label", "") or "")
            normalized_label = label.strip()
            if not raw_key or raw_key.startswith("auto_gen"):
                existing_key = existing_keys_by_label.get(normalized_label)
                if existing_key:
                    raw_key = existing_key
                else:
                    next_custom_id += 1
                    raw_key = f"discipline_custom_{next_custom_id}"
                    if normalized_label:
                        existing_keys_by_label[normalized_label] = raw_key

            rows.append(
                MoTransactionDisciplineWarning(
                    mo_daily_transaction_id=txn_id,
                    key=raw_key,
                    label=label,
                    value=MoDailyTransactionService._as_int(disc_data.get("value")),
                )
            )
        db.add_all(rows)

    @staticmethod
    def _replace_detail2(db: Session, txn_id: int, payload: dict) -> None:
        db.execute(
            delete(MoDailyTransactionProject).where(
                MoDailyTransactionProject.mo_daily_transaction_id == txn_id
            )
        )
        rows = []
        sort_order = 1

        # Projects/meetings (group3 — เข้าพบผู้ว่าจ้าง)
        for project_data in payload.get("projects") or []:
            if hasattr(project_data, "model_dump"):
                project_data = project_data.model_dump()
            elif not isinstance(project_data, dict):
                project_data = dict(project_data)
            rows.append(
                MoDailyTransactionProject(
                    mo_daily_transaction_id=txn_id,
                    project_name=project_data.get("name", ""),
                    detail=project_data.get("detail", ""),
                    status=project_data.get("status", "normal"),
                    note=project_data.get("note", ""),
                )
            )
            sort_order += 1

        # Guard post movements (group4 — การเปลี่ยนแปลงจุดรักษาการณ์)
        for gp_item in payload.get("guard_post_movements") or []:
            if hasattr(gp_item, "model_dump"):
                gp_item = gp_item.model_dump()
            elif not isinstance(gp_item, dict):
                gp_item = dict(gp_item)
            rows.append(
                MoDailyTransactionProject(
                    mo_daily_transaction_id=txn_id,
                    project_name=gp_item.get("name", ""),
                    detail=gp_item.get("detail", ""),
                    status=gp_item.get("status", ""),
                    note=gp_item.get("note", ""),
                )
            )
            sort_order += 1

        db.add_all(rows)

    # ─── Public Methods ───────────────────────────────────────────────────────

    @staticmethod
    def list_reports(
        db: Session,
        actor_employee: Employee,
        field_id: Optional[int] = None,
        department_id: Optional[int] = None,
        division_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        status: Optional[ApprovedStatusEnum] = None,
        created_by: Optional[str] = None,
    ) -> List[dict]:
        if not is_admin(actor_employee, db):
            access_level = get_employee_access_level(actor_employee)
            if access_level == ACCESS_FIELD_ONLY:
                if field_id is not None and field_id != actor_employee.field_id:
                    raise HTTPException(
                        status_code=http_status.HTTP_403_FORBIDDEN,
                        detail="You can only list reports in your own field",
                    )
                field_id = actor_employee.field_id
                if department_id is not None:
                    enforce_same_department(actor_employee, department_id, db)
            else:
                if (
                    department_id is not None
                    and department_id != actor_employee.department_id
                ):
                    raise HTTPException(
                        status_code=http_status.HTTP_403_FORBIDDEN,
                        detail="You can only list reports in your own department",
                    )
                department_id = actor_employee.department_id

            if (
                access_level != ACCESS_FIELD_ONLY
                and not actor_has_department_scope(actor_employee, db)
            ):
                if (
                    division_id is not None
                    and division_id != actor_employee.division_id
                ):
                    raise HTTPException(
                        status_code=http_status.HTTP_403_FORBIDDEN,
                        detail="You can only list reports in your own division",
                    )
                division_id = (
                    actor_employee.division_id
                    if actor_employee.division_id is not None
                    else -1
                )

        stmt = select(MoDailyTransaction)
        if field_id is not None:
            stmt = stmt.join(
                Department,
                Department.department_id == MoDailyTransaction.department_id,
            ).where(Department.field_id == field_id)
        if department_id is not None:
            stmt = stmt.where(MoDailyTransaction.department_id == department_id)
        if division_id is not None:
            stmt = stmt.where(MoDailyTransaction.division_id == division_id)
        if start_date:
            stmt = stmt.where(MoDailyTransaction.created_at >= start_date)
        if end_date:
            if end_date.hour == 0 and end_date.minute == 0 and end_date.second == 0:
                end_date = end_date.replace(
                    hour=23, minute=59, second=59, microsecond=999999
                )
            stmt = stmt.where(MoDailyTransaction.created_at <= end_date)
        if status:
            stmt = stmt.where(MoDailyTransaction.approved_status == status)
        if created_by:
            stmt = stmt.where(MoDailyTransaction.created_by == created_by)
        stmt = stmt.order_by(MoDailyTransaction.division_id.asc())
        rows = db.execute(stmt).scalars().all()
        return [MoDailyTransactionService._build_response(r, db) for r in rows]

    @staticmethod
    def list_available_report_divisions(
        db: Session,
        actor_employee: Employee,
        department_id: int,
    ) -> List[dict]:
        """Return active divisions that do not already have today's report.

        Used by Add New so the frontend does not have to merge all divisions with
        today's reports itself. Inactive department/division rows resolve to an
        empty list for selection purposes.
        """
        enforce_same_department(
            actor_employee, department_id, db
        )

        department = (
            db.execute(
                select(Department).where(
                    Department.department_id == department_id,
                    Department.is_active,
                )
            )
            .scalars()
            .first()
        )
        if not department:
            return []

        reported_today = select(MoDailyTransaction.division_id).where(
            MoDailyTransaction.department_id == department_id,
            func.date(MoDailyTransaction.created_at) == date.today(),
            MoDailyTransaction.division_id.is_not(None),
        )

        stmt = select(Division).where(
            Division.department_id == department_id,
            Division.is_active,
            Division.division_id.not_in(reported_today),
        )

        if actor_employee.position_id not in {1, 5}:
            stmt = stmt.where(Division.division_id == actor_employee.division_id)

        rows = db.execute(stmt.order_by(Division.division_name)).scalars().all()
        return [
            {
                "division_id": row.division_id,
                "division_name": row.division_name,
                "department_id": row.department_id,
            }
            for row in rows
        ]

    @staticmethod
    def list_distinct_guard_post_statuses(db: Session) -> list[str]:
        """Return all distinct guard post movement statuses from existing reports.

        Filters out "normal", "warning", "danger" since those belong to projects.
        Returns a simple list of status strings, sorted alphabetically.
        """
        rows = (
            db.execute(
                select(MoDailyTransactionProject.status)
                .where(
                    MoDailyTransactionProject.status.notin_(
                        ["normal", "warning", "danger"]
                    ),
                    MoDailyTransactionProject.status != None,
                    MoDailyTransactionProject.status != "",
                )
                .distinct()
                .order_by(MoDailyTransactionProject.status)
            )
            .scalars()
            .all()
        )
        return list(rows)

    @staticmethod
    def create_report(
        db: Session,
        payload: MoDailyTransactionCreate,
        actor_employee: Employee,
    ) -> dict:
        data = MoDailyTransactionService._normalize_flat(payload.model_dump())
        enforce_same_department(
            actor_employee, data["department_id"], db
        )

        # ── Validate department / division exist ──────────────────────────────
        validate_department_exists(db, data["department_id"])
        division_id = data.get("division_id", 0)
        if division_id != 0:
            validate_division_belongs_to_department(
                db, division_id, data["department_id"]
            )
        enforce_division_scope(
            actor_employee, division_id, db
        )
        # ──────────────────────────────────────────────────────────────────────

        # ── Duplicate check: same department + division for today ────────────
        today = date.today()
        existing = (
            db.execute(
                select(MoDailyTransaction).where(
                    MoDailyTransaction.department_id == data["department_id"],
                    MoDailyTransaction.division_id == data.get("division_id", 0),
                    func.date(MoDailyTransaction.created_at) == today,
                )
            )
            .scalars()
            .first()
        )

        if existing:
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail=("รายงานของหน่วยงานนี้ถูกสร้างไปแล้วในวันนี้ "),
            )
        # ────────────────────────────────────────────────────────────────────

        requested_status = data.get("approved_status")
        actor_can_approve = can_approve(actor_employee, db)
        if (
            requested_status
            in {
                ApprovedStatusEnum.APPROVED.value,
                ApprovedStatusEnum.REJECTED.value,
            }
            and not actor_can_approve
        ):
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="ตำแหน่งนี้ไม่มีสิทธิ์อนุมัติหรือปฏิเสธรายงาน",
            )

        workflow_status = MoDailyTransactionService._initial_workflow_status(
            actor_employee
        )
        if requested_status == ApprovedStatusEnum.APPROVED.value:
            workflow_status = make_workflow_status(
                workflow_rank(actor_employee),
                WORKFLOW_APPROVED,
            )

        if requested_status in {
            ApprovedStatusEnum.APPROVED.value,
            ApprovedStatusEnum.REJECTED.value,
        }:
            data["approved_by"] = (
                data.get("approved_by") or actor_employee.employee_code
            )
            data["approved_at"] = data.get("approved_at") or func.now()

        txn = MoDailyTransaction(
            department_id=data["department_id"],
            department_name=data.get("department_name", ""),
            division_id=data.get("division_id"),
            division_name=data.get("division_name"),
            workflow_status=workflow_status,
            approved_by=data.get("approved_by"),
            approved_status=data.get("approved_status") or ApprovedStatusEnum.PENDING,
            approved_at=data.get("approved_at"),
            approved_remark=data.get("approved_remark"),
            created_by=data.get("created_by") or actor_employee.employee_code,
        )
        db.add(txn)
        db.flush()

        MoDailyTransactionService._replace_detail1(
            db, txn.mo_daily_transaction_id, data
        )
        MoDailyTransactionService._replace_disciplines(
            db, txn.mo_daily_transaction_id, data
        )
        MoDailyTransactionService._replace_detail2(
            db, txn.mo_daily_transaction_id, data
        )
        db.commit()
        db.refresh(txn)

        audit_logger.log(
            action=MO_REPORT_CREATED.format(
                report_id=txn.mo_daily_transaction_id,
                department_id=txn.department_id,
                division_id=txn.division_id,
            )
        )

        return MoDailyTransactionService._build_response(txn, db)

    @staticmethod
    def get_report(
        db: Session,
        mo_daily_transaction_id: int,
        actor_employee: Employee,
    ) -> dict:
        txn = (
            db.execute(
                select(MoDailyTransaction).where(
                    MoDailyTransaction.mo_daily_transaction_id
                    == mo_daily_transaction_id
                )
            )
            .scalars()
            .first()
        )
        if not txn:
            audit_logger.log(
                action=MO_REPORT_NOT_FOUND.format(
                    report_id=mo_daily_transaction_id,
                    actor=actor_employee.employee_code,
                    operation="get",
                )
            )
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="ขออภัย รายการนี้ถูกลบไปแล้วโดยผู้สร้างหรือผู้อำนวยการ",
            )
        enforce_report_scope(actor_employee, txn, db)
        return MoDailyTransactionService._build_response(txn, db)

    @staticmethod
    def get_workflow_status(
        db: Session,
        mo_daily_transaction_id: int,
        actor_employee: Employee,
    ) -> dict:
        txn = (
            db.execute(
                select(MoDailyTransaction).where(
                    MoDailyTransaction.mo_daily_transaction_id
                    == mo_daily_transaction_id
                )
            )
            .scalars()
            .first()
        )
        if not txn:
            audit_logger.log(
                action=MO_REPORT_NOT_FOUND.format(
                    report_id=mo_daily_transaction_id,
                    actor=actor_employee.employee_code,
                    operation="get workflow status",
                )
            )
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="ขออภัย รายการนี้ถูกลบไปแล้วโดยผู้สร้างหรือผู้อำนวยการ",
            )

        enforce_report_scope(actor_employee, txn, db)

        updated_by_position_name = None
        if txn.updated_by:
            updated_by_position_name = (
                db.execute(
                    select(Position.position_name)
                    .join(Employee, Employee.position_id == Position.position_id)
                    .where(Employee.employee_code == txn.updated_by)
                )
                .scalars()
                .first()
            )

        return {
            "mo_daily_transaction_id": txn.mo_daily_transaction_id,
            "workflow_status": txn.workflow_status,
            "updated_by": txn.updated_by,
            "updated_by_position_name": updated_by_position_name,
            "updated_at": txn.updated_at,
        }

    @staticmethod
    def update_report(
        db: Session,
        mo_daily_transaction_id: int,
        payload: MoDailyTransactionUpdate,
        actor_employee: Employee,
    ) -> dict:
        data = MoDailyTransactionService._normalize_flat(
            payload.model_dump(exclude_unset=True)
        )

        txn = (
            db.execute(
                select(MoDailyTransaction).where(
                    MoDailyTransaction.mo_daily_transaction_id
                    == mo_daily_transaction_id
                )
            )
            .scalars()
            .first()
        )
        if not txn:
            audit_logger.log(
                action=MO_REPORT_NOT_FOUND.format(
                    report_id=mo_daily_transaction_id,
                    actor=actor_employee.employee_code,
                    operation="update",
                )
            )
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="ขออภัย รายการนี้ถูกลบไปแล้วโดยผู้สร้างหรือผู้อำนวยการ",
            )
        enforce_report_scope(actor_employee, txn, db)
        validate_report_scope_is_active(db, txn)

        requested_workflow_status = data.pop("workflow_status", None)

        old_data = MoDailyTransactionService._build_response(txn, db)
        old_status = old_data.get("approved_status")
        requested_status = data.get("approved_status")

        status_changed = requested_status is not None and requested_status != old_status
        is_approve_action = requested_status == ApprovedStatusEnum.APPROVED.value
        is_send_back_action = requested_status == ApprovedStatusEnum.REJECTED.value
        actor_has_authority = has_department_authority(actor_employee, db)
        actor_can_approve_step = can_approve_workflow_step(actor_employee, txn)
        actor_can_send_back_step = can_send_back_workflow_step(actor_employee, txn)
        actor_rank = workflow_rank(actor_employee)
        workflow_rank_code, workflow_state = split_workflow_status(
            txn.workflow_status
        )
        if workflow_state == WORKFLOW_EDITING and txn.updated_by != actor_employee.employee_code:
            editing_rank_label = workflow_rank_label(
                workflow_rank_code
            )
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail=f"รายการนี้กำลังถูกแก้ไขโดย{editing_rank_label}",
            )

        if requested_workflow_status:
            requested_workflow_status = requested_workflow_status.upper()
            if requested_workflow_status == (txn.workflow_status or "").upper():
                return MoDailyTransactionService._build_response(txn, db)

            requested_rank, requested_state = (
                split_workflow_status(
                    requested_workflow_status
                )
            )
            if (
                workflow_state == WORKFLOW_EDITING
                and txn.updated_by == actor_employee.employee_code
                and requested_state in {WORKFLOW_WAITING, WORKFLOW_RETURNED_TO}
            ):
                if not can_edit_report_content(actor_employee, txn, db):
                    raise HTTPException(
                        status_code=http_status.HTTP_403_FORBIDDEN,
                        detail="คุณไม่มีสิทธิ์แก้ไขเนื้อหารายงานนี้",
                    )
                if requested_state == WORKFLOW_WAITING and not actor_has_authority:
                    restore_rank = (
                        next_workflow_rank(actor_rank)
                        or actor_rank
                    )
                    requested_workflow_status = (
                        make_workflow_status(
                            restore_rank, WORKFLOW_WAITING
                        )
                    )
                txn.workflow_status = requested_workflow_status
                txn.updated_by = actor_employee.employee_code
                txn.updated_at = func.now()
                db.commit()
                db.refresh(txn)
                return MoDailyTransactionService._build_response(txn, db)
            if requested_rank != actor_rank or requested_state != WORKFLOW_EDITING:
                raise HTTPException(
                    status_code=http_status.HTTP_403_FORBIDDEN,
                    detail="ไม่สามารถเปลี่ยน workflow ของตำแหน่งอื่นได้",
                )
            can_edit_rejected = (
                actor_can_edit_rejected_workflow(
                    txn,
                    actor_employee,
                    actor_rank,
                    workflow_rank_code,
                    workflow_state,
                )
            )
            can_creator_pull_back_pending = (
                workflow_state == WORKFLOW_WAITING
                and txn.created_by == actor_employee.employee_code
            )
            can_approver_edit_current_step = (
                actor_has_authority
                and workflow_rank_code == actor_rank
                and workflow_state in {WORKFLOW_WAITING, WORKFLOW_APPROVED}
            )
            if (
                workflow_rank_code
                and workflow_rank_code != actor_rank
                and not can_edit_rejected
                and not can_creator_pull_back_pending
                and not can_approver_edit_current_step
            ):
                raise HTTPException(
                    status_code=http_status.HTTP_403_FORBIDDEN,
                    detail="รายการนี้ยังไม่อยู่ในขั้นตอนแก้ไขของตำแหน่งคุณ",
                )
            if not can_edit_report_content(actor_employee, txn, db):
                raise HTTPException(
                    status_code=http_status.HTTP_403_FORBIDDEN,
                    detail="คุณไม่มีสิทธิ์แก้ไขเนื้อหารายงานนี้",
                )
            txn.workflow_status = requested_workflow_status
            txn.updated_by = actor_employee.employee_code
            txn.updated_at = func.now()
            db.commit()
            db.refresh(txn)
            return MoDailyTransactionService._build_response(txn, db)

        if (
            is_approve_action
            and not actor_can_approve_step
        ):
            audit_logger.log(
                action=MO_REPORT_UPDATE_DENIED.format(
                    report_id=txn.mo_daily_transaction_id,
                    actor=actor_employee.employee_code,
                    requested_status=requested_status,
                    reason="actor lacks approval permission",
                )
            )
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="รายการนี้ยังไม่อยู่ในขั้นตอนอนุมัติของตำแหน่งคุณ",
            )

        if (
            is_send_back_action
            and not actor_can_send_back_step
        ):
            audit_logger.log(
                action=MO_REPORT_UPDATE_DENIED.format(
                    report_id=txn.mo_daily_transaction_id,
                    actor=actor_employee.employee_code,
                    requested_status=requested_status,
                    reason="actor cannot send back current workflow step",
                )
            )
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="รายการนี้ยังไม่อยู่ในขั้นตอนส่งกลับของตำแหน่งคุณ",
            )

        can_send_back_approved = (
            is_send_back_action
            and txn.approved_status == ApprovedStatusEnum.APPROVED
            and actor_can_send_back_step
            and workflow_rank_code == actor_rank
            and workflow_state == WORKFLOW_APPROVED
        )
        if (
            is_approve_action
            and not can_send_back_approved
        ):
            ensure_actor_owns_workflow(
                txn, actor_employee, WORKFLOW_WAITING
            )

        if status_changed and requested_status == ApprovedStatusEnum.PENDING.value:
            can_edit_rejected = (
                actor_can_edit_rejected_workflow(
                    txn,
                    actor_employee,
                    actor_rank,
                    workflow_rank_code,
                    workflow_state,
                )
            )
            if (
                workflow_rank_code
                and workflow_rank_code != actor_rank
                and not can_edit_rejected
            ):
                raise HTTPException(
                    status_code=http_status.HTTP_403_FORBIDDEN,
                    detail="รายการนี้ยังไม่อยู่ในขั้นตอนส่งกลับแก้ไขของตำแหน่งคุณ",
                )
            if not can_edit_report_content(actor_employee, txn, db):
                raise HTTPException(
                    status_code=http_status.HTTP_403_FORBIDDEN,
                    detail="คุณไม่มีสิทธิ์แก้ไขเนื้อหารายงานนี้",
                )

        has_report_content = any(name in data for name in DETAIL_1_COLUMNS) or any(
            name in data for name in {"disciplines", "projects", "guard_post_movements"}
        )
        if has_report_content and not (
            requested_status
            in {
                ApprovedStatusEnum.APPROVED.value,
                ApprovedStatusEnum.REJECTED.value,
            }
        ):
            if not can_edit_report_content(actor_employee, txn, db):
                raise HTTPException(
                    status_code=http_status.HTTP_403_FORBIDDEN,
                    detail="คุณไม่มีสิทธิ์แก้ไขเนื้อหารายงานนี้",
                )

        # ── Prevent edits on already-approved reports, but allow Send Back ──
        if txn.approved_status == ApprovedStatusEnum.APPROVED:
            # Allow Send Back (APPROVED → REJECTED) only for approval-level users.
            if (
                not is_send_back_action
                or not actor_can_send_back_step
            ):
                raise HTTPException(
                    status_code=http_status.HTTP_409_CONFLICT,
                    detail=("รายงานนี้ได้รับการอนุมัติแล้ว ไม่สามารถแก้ไขได้ "),
                )
        # ────────────────────────────────────────────────────────────────────

        # ── Validate division if it changed ──────────────────────────────────
        if "division_id" in data:
            requested_div = data["division_id"]
            if requested_div != 0:
                validate_division_belongs_to_department(
                    db, requested_div, txn.department_id
                )
            enforce_division_scope(
                actor_employee, requested_div, db
            )
        # ──────────────────────────────────────────────────────────────────────

        # Update main transaction fields
        for field in (
            "division_id",
            "division_name",
            "approved_remark",
        ):
            if field in data:
                setattr(txn, field, data[field])

        if "approved_status" in data:
            txn.approved_status = data["approved_status"]

        if is_approve_action:
            next_rank = next_workflow_rank(actor_rank)
            if next_rank:
                txn.approved_status = ApprovedStatusEnum.PENDING
                txn.workflow_status = make_workflow_status(
                    next_rank, WORKFLOW_WAITING
                )
            else:
                txn.workflow_status = make_workflow_status(
                    actor_rank, WORKFLOW_APPROVED
                )
        elif is_send_back_action:
            target_rank = (
                previous_workflow_rank(actor_rank)
                or actor_rank
            )
            txn.workflow_status = make_workflow_status(
                target_rank, WORKFLOW_RETURNED_TO
            )
        elif status_changed and requested_status == ApprovedStatusEnum.PENDING.value:
            if workflow_state == WORKFLOW_RETURNED_TO:
                if txn.approved_by == actor_employee.employee_code:
                    target_rank = actor_rank
                else:
                    target_rank = (
                        next_workflow_rank(actor_rank)
                        or actor_rank
                    )
            elif workflow_state == WORKFLOW_EDITING:
                target_rank = (
                    actor_rank
                    if actor_has_authority
                    else next_workflow_rank(actor_rank)
                    or actor_rank
                )
            else:
                target_rank = (
                    next_workflow_rank(actor_rank)
                    or actor_rank
                )
            txn.workflow_status = make_workflow_status(
                target_rank, WORKFLOW_WAITING
            )
        if not status_changed and has_report_content:
            target_rank = (
                actor_rank
                if actor_has_authority
                else next_workflow_rank(actor_rank)
                or actor_rank
            )
            txn.workflow_status = make_workflow_status(
                target_rank, WORKFLOW_WAITING
            )

        if is_approve_action:
            txn.approved_by = actor_employee.employee_code
            txn.approved_at = func.now()
        elif is_send_back_action:
            txn.approved_by = actor_employee.employee_code
            txn.approved_at = func.now()
        elif status_changed and requested_status == ApprovedStatusEnum.PENDING.value:
            txn.approved_by = None
            txn.approved_at = None

        txn.updated_by = actor_employee.employee_code
        txn.updated_at = func.now()

        db.commit()

        # Replace detail rows (only if any detail1 fields are in payload)
        has_detail_fields = any(name in data for name in DETAIL_1_COLUMNS)
        if has_detail_fields:
            MoDailyTransactionService._replace_detail1(
                db, txn.mo_daily_transaction_id, data
            )

        if "disciplines" in data:
            MoDailyTransactionService._replace_disciplines(
                db, txn.mo_daily_transaction_id, data
            )

        if "projects" in data or "guard_post_movements" in data:
            MoDailyTransactionService._replace_detail2(
                db, txn.mo_daily_transaction_id, data
            )

        db.commit()
        db.refresh(txn)

        new_data = MoDailyTransactionService._build_response(txn, db)
        changed_fields = set(data.keys())
        changes_text = MoDailyTransactionService._format_audit_changes(
            old_data, new_data, changed_fields
        )
        new_status = new_data.get("approved_status")

        if old_status != new_status and new_status == ApprovedStatusEnum.APPROVED.value:
            audit_logger.log(
                action=MO_REPORT_APPROVED.format(
                    report_id=txn.mo_daily_transaction_id,
                    old_status=old_status,
                    new_status=new_status,
                )
            )
        elif (
            old_status != new_status and new_status == ApprovedStatusEnum.REJECTED.value
        ):
            audit_logger.log(
                action=MO_REPORT_REJECTED.format(
                    report_id=txn.mo_daily_transaction_id,
                    old_status=old_status,
                    new_status=new_status,
                    remark=new_data.get("approved_remark") or "",
                )
            )
        else:
            audit_logger.log(
                action=MO_REPORT_UPDATED.format(
                    report_id=txn.mo_daily_transaction_id,
                    changes=changes_text,
                )
            )

        return new_data

    @staticmethod
    def delete_report(
        db: Session,
        mo_daily_transaction_id: int,
        actor_employee: Employee,
    ) -> dict:
        txn = (
            db.execute(
                select(MoDailyTransaction).where(
                    MoDailyTransaction.mo_daily_transaction_id
                    == mo_daily_transaction_id
                )
            )
            .scalars()
            .first()
        )
        if not txn:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="ขออภัย รายการนี้ถูกลบไปแล้วโดยผู้สร้างหรือผู้อำนวยการ",
            )
        enforce_report_scope(actor_employee, txn, db)
        enforce_edit_owner_or_approver(
            actor_employee, txn, db
        )
        validate_report_scope_is_active(db, txn)
        _, workflow_state = split_workflow_status(
            txn.workflow_status
        )
        if workflow_state == WORKFLOW_EDITING:
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail="รายการนี้กำลังถูกแก้ไข ไม่สามารถลบได้",
            )

        deleted_report_id = txn.mo_daily_transaction_id
        deleted_department_id = txn.department_id
        deleted_division_id = txn.division_id

        # CASCADE should handle details, but be explicit
        db.execute(
            delete(MoDailyTransactionDetail1).where(
                MoDailyTransactionDetail1.mo_daily_transaction_id
                == mo_daily_transaction_id
            )
        )
        db.execute(
            delete(MoTransactionDisciplineWarning).where(
                MoTransactionDisciplineWarning.mo_daily_transaction_id
                == mo_daily_transaction_id
            )
        )
        db.execute(
            delete(MoDailyTransactionProject).where(
                MoDailyTransactionProject.mo_daily_transaction_id
                == mo_daily_transaction_id
            )
        )
        db.delete(txn)
        db.commit()

        audit_logger.log(
            action=MO_REPORT_DELETED.format(
                report_id=deleted_report_id,
                department_id=deleted_department_id,
                division_id=deleted_division_id,
            )
        )

        return {"message": "Report deleted successfully"}
