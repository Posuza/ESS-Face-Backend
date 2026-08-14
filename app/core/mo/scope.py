from __future__ import annotations

from typing import Optional

from fastapi import HTTPException, status as http_status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.mo.config import (
    ACCESS_DEPARTMENT_ONLY,
    ACCESS_FIELD_ONLY,
    get_employee_access_level,
)
from app.core.mo.workflow_access import is_admin
from app.models.departments import Department
from app.models.divisions import Division
from app.models.employees import Employee
from app.models.mo_daily_transactions import MoDailyTransaction


def validate_department_exists(db: Session, department_id: int) -> Department:
    """Ensure the department exists and is active."""
    dept = (
        db.execute(
            select(Department).where(
                Department.department_id == department_id,
                Department.is_active,
            )
        )
        .scalars()
        .first()
    )
    if dept:
        return dept

    any_dept = (
        db.execute(select(Department).where(Department.department_id == department_id))
        .scalars()
        .first()
    )
    if any_dept:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"หน่วยงาน '{any_dept.department_name}' ถูกปิดใช้งาน",
        )
    raise HTTPException(
        status_code=http_status.HTTP_404_NOT_FOUND,
        detail="ไม่พบหน่วยงาน หรือถูกปิดใช้งาน",
    )


def validate_division_belongs_to_department(
    db: Session, division_id: int, department_id: int
) -> Division | None:
    """Ensure the division exists, is active, and belongs to the department."""
    if division_id == 0:
        return None

    div = (
        db.execute(
            select(Division).where(
                Division.division_id == division_id,
                Division.department_id == department_id,
                Division.is_active,
            )
        )
        .scalars()
        .first()
    )
    if div:
        return div

    any_div = (
        db.execute(
            select(Division).where(
                Division.division_id == division_id,
                Division.department_id == department_id,
            )
        )
        .scalars()
        .first()
    )
    any_dept = (
        db.execute(select(Department).where(Department.department_id == department_id))
        .scalars()
        .first()
    )
    div_name = any_div.division_name if any_div else f"id={division_id}"
    dept_name = any_dept.department_name if any_dept else f"id={department_id}"
    raise HTTPException(
        status_code=http_status.HTTP_404_NOT_FOUND,
        detail=(
            f"ไม่พบหน่วยงานย่อย '{div_name}' สำหรับหน่วยงาน '{dept_name}' "
            f"หรือถูกปิดใช้งาน"
        ),
    )


def validate_report_scope_is_active(db: Session, txn: MoDailyTransaction) -> None:
    """Ensure an existing report's department/division are still active."""
    validate_department_exists(db, txn.department_id)
    if txn.division_id:
        validate_division_belongs_to_department(
            db, txn.division_id, txn.department_id
        )


def enforce_same_department(
    actor: Employee, department_id: Optional[int], db: Session
) -> None:
    if is_admin(actor, db):
        return
    if get_employee_access_level(actor) == ACCESS_FIELD_ONLY:
        department = db.execute(
            select(Department).where(Department.department_id == department_id)
        ).scalars().first()
        if department and department.field_id == actor.field_id:
            return
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="You can only access reports in your own field",
        )
    if department_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Department is required",
        )
    if actor.department_id != department_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="You can only access reports in your own department",
        )


def actor_has_department_scope(actor: Employee, db: Session) -> bool:
    return get_employee_access_level(actor) in {
        ACCESS_FIELD_ONLY,
        ACCESS_DEPARTMENT_ONLY,
    } or is_admin(actor, db)


def enforce_division_scope(
    actor: Employee, division_id: Optional[int], db: Session
) -> None:
    if actor_has_department_scope(actor, db):
        return
    if actor.division_id is None or division_id != actor.division_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="You can only access reports in your own division",
        )


def enforce_report_scope(
    actor: Employee, txn: MoDailyTransaction, db: Session
) -> None:
    enforce_same_department(actor, txn.department_id, db)
    enforce_division_scope(actor, txn.division_id, db)
