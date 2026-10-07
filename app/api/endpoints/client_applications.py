from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.api.dependencies import active_employee_required, roles_required
from app.core.db.session import get_db
from app.models.employees import Employee
from app.schemas.client_auth import AppRegistrationCreate, AppRegistrationCreated
from app.services.client_auth import client_auth_service


router = APIRouter()


@router.post(
    "",
    response_model=AppRegistrationCreated,
    status_code=status.HTTP_201_CREATED,
)
@active_employee_required
@roles_required("super_admin")
async def register_client_application(
    payload: AppRegistrationCreate,
    http_request: Request,
    db: Session = Depends(get_db),
    current_employee: Employee | None = None,
) -> AppRegistrationCreated:
    app = client_auth_service.register_application(db, payload)
    return AppRegistrationCreated.model_validate(app)
