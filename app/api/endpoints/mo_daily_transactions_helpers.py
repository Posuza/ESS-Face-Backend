from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.dependencies import active_employee_required, mo_active_required
from app.core.db.session import get_db
from app.models.employees import Employee
from app.schemas.mo_daily_transactions import (
    GuardPostStatusResponse,
    MoDailyTransactionWorkflowStatusResponse,
)
from app.services.mo_daily_transactions import MoDailyTransactionService

router = APIRouter()


@router.get("/distinct-guard-post-movement-statuses",
    response_model=GuardPostStatusResponse,
)
@active_employee_required
async def api_list_distinct_guard_post_statuses(
    http_request: Request,
    current_employee: Employee = None,
    db: Session = Depends(get_db),
    ):
    """
    Return all distinct guard post movement statuses from existing reports.
    Excludes "normal", "warning", "danger" (those are project statuses).
    """
    statuses = MoDailyTransactionService.list_distinct_guard_post_statuses(db=db)
    return GuardPostStatusResponse(statuses=statuses)


@router.get("/available-report-divisions")
@active_employee_required
@mo_active_required
async def api_list_available_report_divisions(
    http_request: Request,
    department_id: int = Query(...),
    current_employee: Employee = None,
    db: Session = Depends(get_db),
    ):
    return MoDailyTransactionService.list_available_report_divisions(
        db=db,
        actor_employee=current_employee,
        department_id=department_id,
    )


@router.get(
    "/{mo_daily_transaction_id}/mo_daily_transaction_workflow_status",
    response_model=MoDailyTransactionWorkflowStatusResponse,
)
@active_employee_required
@mo_active_required
async def api_get_report_workflow_status(
    mo_daily_transaction_id: int,
    http_request: Request,
    current_employee: Employee = None,
    db: Session = Depends(get_db),
):
    return MoDailyTransactionService.get_workflow_status(
        db=db,
        mo_daily_transaction_id=mo_daily_transaction_id,
        actor_employee=current_employee,
    )
