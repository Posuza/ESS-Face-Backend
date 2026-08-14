from typing import List

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.dependencies import active_employee_required
from app.core.db.session import get_db
from app.models.employees import Employee
from app.schemas.mo_workplace import DepartmentResponse, DivisionResponse
from app.services.mo_workplace import MoWorkplaceService

router = APIRouter()


@router.get("/divisions", response_model=List[DivisionResponse])
@active_employee_required
async def api_list_divisions(
    request: Request,
    department_id: int = Query(..., gt=0),
    field_id: int | None = Query(None, gt=0),
    current_employee: Employee = None,
    db: Session = Depends(get_db),
):
    return MoWorkplaceService.list_divisions(
        db=db,
        department_id=department_id,
        field_id=field_id,
        current_employee=current_employee,
    )


@router.get("/departments", response_model=List[DepartmentResponse])
@active_employee_required
async def api_list_departments_by_field(
    request: Request,
    field_id: int = Query(..., gt=0),
    current_employee: Employee = None,
    db: Session = Depends(get_db),
):
    return MoWorkplaceService.list_departments_by_field(
        db=db,
        field_id=field_id,
    )
