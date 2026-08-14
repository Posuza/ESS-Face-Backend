from __future__ import annotations

from fastapi import HTTPException, status as http_status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.mo.config import get_workflow_rank, has_department_scope
from app.core.mo.workflow_status import (
    WORKFLOW_APPROVED,
    WORKFLOW_EDITING,
    WORKFLOW_RETURNED_TO,
    WORKFLOW_WAITING,
    next_workflow_rank,
    previous_workflow_rank,
    split_workflow_status,
)
from app.models.employees import Employee
from app.models.mo_daily_transactions import MoDailyTransaction
from app.models.positions import Position


def is_admin(actor: Employee, db: Session) -> bool:
    """Check if the actor has an admin-level role or position."""
    if actor.role_id in {1, 9, 99}:
        return True
    position = (
        db.execute(
            select(Position.position_name).where(
                Position.position_id == actor.position_id
            )
        )
        .scalars()
        .first()
    )
    return position is not None and "admin" in position.strip().lower()


def has_department_authority(actor: Employee, db: Session) -> bool:
    """Check if actor has department-wide authority.

    Position active check is handled by @mo_active_required decorator.
    """
    return has_department_scope(actor.position_id) or is_admin(actor, db)


def can_approve(actor: Employee, db: Session) -> bool:
    """Backward-compatible alias for department-wide authority."""
    return has_department_authority(actor, db)


def workflow_rank(actor: Employee) -> str:
    rank = get_workflow_rank(actor.position_id)
    if not rank:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="ตำแหน่งนี้ไม่มีสิทธิ์ดำเนินการใน workflow MO",
        )
    return rank


def ensure_actor_owns_workflow(
    txn: MoDailyTransaction,
    actor_employee: Employee,
    expected_state: str,
) -> str:
    actor_rank = workflow_rank(actor_employee)
    workflow_rank_code, workflow_state = split_workflow_status(txn.workflow_status)
    if workflow_rank_code != actor_rank or workflow_state != expected_state:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="รายการนี้ยังไม่อยู่ในขั้นตอนดำเนินการของตำแหน่งคุณ",
        )
    return actor_rank


def is_lowest_workflow_rank(rank_code: str) -> bool:
    return previous_workflow_rank(rank_code) is None


def can_approve_workflow_step(actor: Employee, txn: MoDailyTransaction) -> bool:
    actor_rank = workflow_rank(actor)
    workflow_rank_code, workflow_state = split_workflow_status(txn.workflow_status)
    return (
        workflow_state == WORKFLOW_WAITING
        and workflow_rank_code == actor_rank
        and not is_lowest_workflow_rank(actor_rank)
    )


def can_send_back_workflow_step(actor: Employee, txn: MoDailyTransaction) -> bool:
    actor_rank = workflow_rank(actor)
    workflow_rank_code, workflow_state = split_workflow_status(txn.workflow_status)
    return (
        workflow_rank_code == actor_rank
        and workflow_state in {WORKFLOW_WAITING, WORKFLOW_RETURNED_TO, WORKFLOW_APPROVED}
        and not is_lowest_workflow_rank(actor_rank)
    )


def actor_can_edit_rejected_workflow(
    txn: MoDailyTransaction,
    actor_employee: Employee,
    actor_rank: str,
    workflow_rank_code: str,
    workflow_state: str,
) -> bool:
    if workflow_state != WORKFLOW_RETURNED_TO:
        return False
    return (
        workflow_rank_code == actor_rank
        or txn.approved_by == actor_employee.employee_code
    )


def enforce_edit_owner_or_approver(
    actor: Employee, txn: MoDailyTransaction, db: Session
) -> None:
    if has_department_authority(actor, db):
        return
    if txn.created_by == actor.employee_code:
        return
    raise HTTPException(
        status_code=http_status.HTTP_403_FORBIDDEN,
        detail="คุณสามารถแก้ไขได้เฉพาะรายงานที่คุณสร้างเองเท่านั้น",
    )


def can_edit_report_content(actor: Employee, txn: MoDailyTransaction, db: Session) -> bool:
    if has_department_authority(actor, db):
        return True

    actor_rank = workflow_rank(actor)
    workflow_rank_code, workflow_state = split_workflow_status(txn.workflow_status)
    if workflow_state == WORKFLOW_EDITING:
        return (
            workflow_rank_code == actor_rank
            and txn.updated_by == actor.employee_code
        )
    if workflow_state == WORKFLOW_RETURNED_TO:
        return (
            workflow_rank_code == actor_rank
            and txn.created_by == actor.employee_code
        )
    if workflow_state == WORKFLOW_WAITING:
        next_rank = next_workflow_rank(actor_rank)
        return (
            txn.created_by == actor.employee_code
            and workflow_rank_code in {actor_rank, next_rank}
        )
    return False
