from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.audit_logger import audit_logger
from app.core.media_storage import (
    media_storage_root,
    normalize_face_image_key,
    resolve_face_image_path,
)
from app.core.registries import (
    ADMIN_EMPLOYEE_CREATE_SUCCESS,
    ADMIN_EMPLOYEE_DELETE_SUCCESS,
    ADMIN_EMPLOYEE_UPDATE_SUCCESS,
    ADMIN_ERROR_DELETE_SELF,
    ADMIN_ERROR_EMPLOYEE_CODE_EXISTS,
    ADMIN_ERROR_EMPLOYEE_DATA_CONFLICT,
    ADMIN_ERROR_EMPLOYEE_NOT_FOUND,
    ADMIN_ERROR_EMPLOYEE_REFERENCED,
    ADMIN_ERROR_FACE_PROFILE_NOT_FOUND,
    ADMIN_FACE_PROFILE_DELETE_SUCCESS,
)
from app.models.departments import Department
from app.models.divisions import Division
from app.models.employees import Employee
from app.models.fields import FieldModel
from app.models.name_prefixs import NamePrefix
from app.models.positions import Position
from app.models.roles import Role
from app.models.routes import Route
from app.models.shifts import Shift
from app.schemas.admin import AdminEmployeeCreate, AdminEmployeeUpdate


def _employee_or_404(db: Session, employee_code: str) -> Employee:
    employee = db.scalar(
        select(Employee).where(Employee.employee_code == employee_code.strip())
    )
    if employee is None:
        raise HTTPException(status_code=404, detail=ADMIN_ERROR_EMPLOYEE_NOT_FOUND)
    return employee


def _lookup_map(db: Session, model, id_column, label_column) -> dict[int, str]:
    return {int(item_id): str(label) for item_id, label in db.execute(select(id_column, label_column)).all()}


def _optional_int(value: object) -> int | None:
    """Normalize blank legacy foreign keys without mutating stored employee data."""
    if value is None or value == "":
        return None
    return int(value)


def _serialize_employee(
    db: Session,
    employee: Employee,
    *,
    role_names: dict[int, str] | None = None,
    prefix_names: dict[int, str] | None = None,
) -> dict:
    if role_names is None:
        role_names = _lookup_map(db, Role, Role.role_id, Role.role_name)
    if prefix_names is None:
        prefix_names = _lookup_map(
            db, NamePrefix, NamePrefix.prefix_id, NamePrefix.prefix_name
        )
    face_profile_location = None
    if employee.profile_image_path:
        try:
            folder = media_storage_root().name
            filename = normalize_face_image_key(employee.profile_image_path)
            face_profile_location = f"/{folder}/{filename}" if folder else filename
        except ValueError:
            face_profile_location = None
    return {
        "employee_code": employee.employee_code,
        "role_id": employee.role_id,
        "role_name": role_names.get(employee.role_id),
        "name_prefix_id": employee.name_prefix_id,
        "name_prefix": prefix_names.get(employee.name_prefix_id),
        "first_name": employee.first_name,
        "last_name": employee.last_name,
        "birth_date": employee.birth_date,
        "email": employee.email,
        "phone_number": employee.phone_number,
        "address_id": _optional_int(employee.address_id),
        "field_id": _optional_int(employee.field_id),
        "department_id": _optional_int(employee.department_id),
        "division_id": _optional_int(employee.division_id),
        "position_id": _optional_int(employee.position_id),
        "routes_id": _optional_int(employee.routes_id),
        "shift_id": _optional_int(employee.shift_id),
        "is_active": employee.is_active,
        "start_date": employee.start_date,
        "leave_date": employee.leave_date,
        "has_face_profile": bool(employee.profile_image_path),
        "face_profile_location": face_profile_location,
        "profile_image_updated_at": employee.profile_image_updated_at,
        "created_at": employee.created_at,
        "updated_at": employee.updated_at,
    }


class AdminEmployeeService:
    @staticmethod
    def list_employees(
        db: Session,
        *,
        search: str,
        is_active: bool | None,
        page: int,
        page_size: int,
    ) -> dict:
        filters = []
        normalized = search.strip()
        if normalized:
            pattern = f"%{normalized}%"
            filters.append(
                or_(
                    Employee.employee_code.ilike(pattern),
                    Employee.first_name.ilike(pattern),
                    Employee.last_name.ilike(pattern),
                    Employee.email.ilike(pattern),
                )
            )
        if is_active is not None:
            filters.append(Employee.is_active.is_(is_active))
        total = db.scalar(select(func.count()).select_from(Employee).where(*filters)) or 0
        employees = db.scalars(
            select(Employee)
            .where(*filters)
            .order_by(Employee.created_at.desc(), Employee.employee_code)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        role_names = _lookup_map(db, Role, Role.role_id, Role.role_name)
        prefix_names = _lookup_map(
            db, NamePrefix, NamePrefix.prefix_id, NamePrefix.prefix_name
        )
        return {
            "items": [
                _serialize_employee(
                    db,
                    employee,
                    role_names=role_names,
                    prefix_names=prefix_names,
                )
                for employee in employees
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    @staticmethod
    def get_employee(db: Session, employee_code: str) -> dict:
        return _serialize_employee(db, _employee_or_404(db, employee_code))

    @staticmethod
    def create_employee(db: Session, payload: AdminEmployeeCreate, actor_code: str) -> dict:
        code = payload.employee_code.upper()
        if db.get(Employee, code) is not None:
            raise HTTPException(status_code=409, detail=ADMIN_ERROR_EMPLOYEE_CODE_EXISTS)
        values = payload.model_dump()
        values["employee_code"] = code
        values["created_by"] = actor_code
        values["updated_by"] = actor_code
        employee = Employee(**values)
        db.add(employee)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail=ADMIN_ERROR_EMPLOYEE_DATA_CONFLICT) from exc
        db.refresh(employee)
        audit_logger.log(
            action=ADMIN_EMPLOYEE_CREATE_SUCCESS.format(employee_code=employee.employee_code)
        )
        return _serialize_employee(db, employee)

    @staticmethod
    def update_employee(
        db: Session,
        employee_code: str,
        payload: AdminEmployeeUpdate,
        actor_code: str,
    ) -> dict:
        employee = _employee_or_404(db, employee_code)
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(employee, key, value)
        employee.updated_by = actor_code
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail=ADMIN_ERROR_EMPLOYEE_DATA_CONFLICT) from exc
        db.refresh(employee)
        audit_logger.log(
            action=ADMIN_EMPLOYEE_UPDATE_SUCCESS.format(employee_code=employee.employee_code)
        )
        return _serialize_employee(db, employee)

    @staticmethod
    def delete_employee(db: Session, employee_code: str, actor_code: str) -> None:
        if employee_code == actor_code:
            raise HTTPException(status_code=409, detail=ADMIN_ERROR_DELETE_SELF)
        employee = _employee_or_404(db, employee_code)
        image_path: Path | None = None
        if employee.profile_image_path:
            try:
                image_path = resolve_face_image_path(employee.profile_image_path)
            except ValueError:
                image_path = None
        db.delete(employee)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail=ADMIN_ERROR_EMPLOYEE_REFERENCED,
            ) from exc
        if image_path is not None:
            image_path.unlink(missing_ok=True)
        audit_logger.log(
            action=ADMIN_EMPLOYEE_DELETE_SUCCESS.format(employee_code=employee_code)
        )

    @staticmethod
    def delete_face_profile(db: Session, employee_code: str, actor_code: str) -> None:
        employee = _employee_or_404(db, employee_code)
        if not employee.profile_image_path:
            raise HTTPException(status_code=404, detail=ADMIN_ERROR_FACE_PROFILE_NOT_FOUND)
        try:
            image_path = resolve_face_image_path(employee.profile_image_path)
        except ValueError:
            image_path = None
        employee.profile_image_path = None
        employee.profile_image_updated_at = None
        employee.updated_by = actor_code
        db.commit()
        if image_path is not None:
            image_path.unlink(missing_ok=True)
        audit_logger.log(
            action=ADMIN_FACE_PROFILE_DELETE_SUCCESS.format(employee_code=employee_code)
        )

    @staticmethod
    def options(db: Session) -> dict:
        def options_for(model, id_column, label_column) -> list[dict]:
            return [
                {"id": item_id, "label": str(label)}
                for item_id, label in db.execute(select(id_column, label_column).order_by(label_column)).all()
            ]

        return {
            "roles": options_for(Role, Role.role_id, Role.role_name),
            "prefixes": options_for(NamePrefix, NamePrefix.prefix_id, NamePrefix.prefix_name),
            "fields": options_for(FieldModel, FieldModel.field_id, FieldModel.field_name),
            "departments": options_for(Department, Department.department_id, Department.department_name),
            "divisions": options_for(Division, Division.division_id, Division.division_name),
            "positions": options_for(Position, Position.position_id, Position.position_name),
            "shifts": options_for(Shift, Shift.shift_id, Shift.shift_name_th),
            "routes": options_for(Route, Route.route_id, Route.route_name),
        }


admin_employee_service = AdminEmployeeService()
