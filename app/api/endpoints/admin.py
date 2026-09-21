from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.dependencies import (
    active_employee_required,
    admin_user_manager_required,
    roles_required,
)
from app.core.audit_logger import audit_logger
from app.core.db.session import get_db
from app.services.model_settings import (
    get_frontend_model_settings,
    get_model_settings,
    reset_model_settings,
    update_model_settings,
)
from app.models.employees import Employee
from app.schemas.admin import (
    AdminEmployeeCreate,
    AdminEmployeeListResponse,
    AdminEmployeeResponse,
    AdminEmployeeUpdate,
    ModelSettingsReset,
    ModelSettingsUpdate,
)
from app.schemas.face_verify import FaceEnrollRequest, FaceEnrollResponse
from app.core.registries import ADMIN_FACE_PROFILE_REPLACE_SUCCESS
from app.services.admin import admin_employee_service
from app.services.face_verify import face_verify_service


router = APIRouter()


@router.get("/model-settings/frontend")
def frontend_model_settings(mode: str | None = None):
    return get_frontend_model_settings(mode)


@router.get("/admin/users", response_model=AdminEmployeeListResponse)
@active_employee_required
@admin_user_manager_required
async def list_users(
    http_request: Request,
    search: str = "",
    is_active: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_employee: Employee | None = None,
):
    return admin_employee_service.list_employees(
        db, search=search, is_active=is_active, page=page, page_size=page_size
    )


@router.get("/admin/users/options")
@active_employee_required
@admin_user_manager_required
async def user_options(
    http_request: Request,
    db: Session = Depends(get_db),
    current_employee: Employee | None = None,
):
    return admin_employee_service.options(db)


@router.post("/admin/users", response_model=AdminEmployeeResponse, status_code=201)
@active_employee_required
@admin_user_manager_required
async def create_user(
    payload: AdminEmployeeCreate,
    http_request: Request,
    db: Session = Depends(get_db),
    current_employee: Employee | None = None,
):
    return admin_employee_service.create_employee(db, payload, current_employee.employee_code)


@router.get("/admin/users/{employee_code}", response_model=AdminEmployeeResponse)
@active_employee_required
@admin_user_manager_required
async def get_user(
    employee_code: str,
    http_request: Request,
    db: Session = Depends(get_db),
    current_employee: Employee | None = None,
):
    return admin_employee_service.get_employee(db, employee_code)


@router.patch("/admin/users/{employee_code}", response_model=AdminEmployeeResponse)
@active_employee_required
@admin_user_manager_required
async def update_user(
    employee_code: str,
    payload: AdminEmployeeUpdate,
    http_request: Request,
    db: Session = Depends(get_db),
    current_employee: Employee | None = None,
):
    return admin_employee_service.update_employee(
        db, employee_code, payload, current_employee.employee_code
    )


@router.delete("/admin/users/{employee_code}", status_code=204)
@active_employee_required
@admin_user_manager_required
async def delete_user(
    employee_code: str,
    http_request: Request,
    db: Session = Depends(get_db),
    current_employee: Employee | None = None,
):
    admin_employee_service.delete_employee(db, employee_code, current_employee.employee_code)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/admin/users/{employee_code}/face-profile", response_class=FileResponse)
@active_employee_required
@admin_user_manager_required
async def get_user_face_profile(
    employee_code: str,
    http_request: Request,
    db: Session = Depends(get_db),
    current_employee: Employee | None = None,
):
    image_path = face_verify_service.get_profile_image_path(db, employee_code)
    return FileResponse(image_path, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.put("/admin/users/{employee_code}/face-profile", response_model=FaceEnrollResponse)
@active_employee_required
@admin_user_manager_required
async def replace_user_face_profile(
    employee_code: str,
    payload: dict,
    http_request: Request,
    db: Session = Depends(get_db),
    current_employee: Employee | None = None,
):
    request = FaceEnrollRequest(
        employee_code=employee_code,
        image_data_url=payload.get("image_data_url", ""),
        created_by=current_employee.employee_code,
    )
    employee = face_verify_service.enroll_face(db, request)
    audit_logger.log(
        action=ADMIN_FACE_PROFILE_REPLACE_SUCCESS.format(employee_code=employee_code)
    )
    return FaceEnrollResponse.model_validate(employee)


@router.delete("/admin/users/{employee_code}/face-profile", status_code=204)
@active_employee_required
@admin_user_manager_required
async def delete_user_face_profile(
    employee_code: str,
    http_request: Request,
    db: Session = Depends(get_db),
    current_employee: Employee | None = None,
):
    admin_employee_service.delete_face_profile(db, employee_code, current_employee.employee_code)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/admin/model-settings")
@active_employee_required
@roles_required("admin", "super_admin")
async def admin_model_settings(
    http_request: Request,
    mode: str | None = None,
    db: Session = Depends(get_db),
    current_employee: Employee | None = None,
):
    return get_model_settings(mode)


@router.patch("/admin/model-settings/{group}/{model_key}")
@active_employee_required
@roles_required("admin", "super_admin")
async def patch_model_settings(
    group: str,
    model_key: str,
    payload: ModelSettingsUpdate,
    http_request: Request,
    mode: str | None = None,
    db: Session = Depends(get_db),
    current_employee: Employee | None = None,
):
    return update_model_settings(
        group,
        model_key,
        active=payload.active,
        values=payload.settings_values,
        mode=mode,
    )


@router.post("/admin/model-settings/reset")
@active_employee_required
@roles_required("admin", "super_admin")
async def reset_admin_model_settings(
    payload: ModelSettingsReset,
    http_request: Request,
    mode: str | None = None,
    db: Session = Depends(get_db),
    current_employee: Employee | None = None,
):
    return reset_model_settings(payload.group, payload.model_key, mode)
