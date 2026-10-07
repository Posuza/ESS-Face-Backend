from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.shared.audit_logger import audit_logger
from app.core.shared.media_storage import (
    media_storage_root,
    normalize_face_image_key,
    resolve_face_image_path,
)
from app.core.main.registries import (
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
from app.models.main.departments import Department
from app.models.main.divisions import Division
from app.models.main.employees import Employee
from app.models.main.fields import FieldModel
from app.models.main.name_prefixs import NamePrefix
from app.models.main.positions import Position
from app.models.main.roles import Role
from app.models.main.routes import Route
from app.models.main.shifts import Shift
from app.schemas.main.admin import AdminEmployeeCreate, AdminEmployeeUpdate


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


def _employee_population_filter():
    """Select employees shown in face-registration summaries and tables."""
    normalized_role_name = func.replace(
        func.replace(func.lower(func.trim(Role.role_name)), "-", "_"),
        " ",
        "_",
    )
    super_admin_role_ids = select(Role.role_id).where(
        normalized_role_name == "super_admin"
    )
    return Employee.role_id.not_in(super_admin_role_ids)


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
    def employee_summary(
        db: Session,
        *,
        is_active: bool | None = True,
        include_super_admin: bool = False,
        excluded_include_super_admin: bool | None = None,
    ) -> dict[str, int]:
        registered_face = and_(
            Employee.profile_image_path.is_not(None),
            Employee.profile_image_path != "",
        )
        filters = [] if include_super_admin else [_employee_population_filter()]
        if is_active is not None:
            filters.append(Employee.is_active.is_(is_active))
        total, registered = db.execute(
            select(
                func.count(),
                func.coalesce(func.sum(case((registered_face, 1), else_=0)), 0),
            )
            .select_from(Employee)
            .where(*filters)
        ).one()
        total = int(total or 0)
        registered = int(registered or 0)
        if excluded_include_super_admin is None:
            excluded_include_super_admin = include_super_admin
        excluded_filters = (
            [] if excluded_include_super_admin else [_employee_population_filter()]
        )
        visible_population = db.scalar(
            select(func.count()).select_from(Employee).where(*excluded_filters)
        ) or 0
        active_population = db.scalar(
            select(func.count())
            .select_from(Employee)
            .where(
                _employee_population_filter(),
                Employee.is_active.is_(True),
            )
        ) or 0
        excluded = int(visible_population) - int(active_population)
        return {
            "total": total,
            "registered": registered,
            "missing": total - registered,
            "excluded": excluded,
        }

    @staticmethod
    def list_employees(
        db: Session,
        *,
        search: str,
        is_active: bool | None,
        page: int,
        page_size: int,
        registered_faces_first: bool = False,
        sort_employee_code: bool = False,
        sort_by: str | None = None,
        sort_direction: str = "asc",
        face_status: str = "all",
        include_super_admin: bool = False,
    ) -> dict:
        filters = [] if include_super_admin else [_employee_population_filter()]
        normalized = search.strip()
        if normalized:
            pattern = f"%{normalized}%"
            filters.append(
                or_(
                    Employee.employee_code.ilike(pattern),
                    Employee.first_name.ilike(pattern),
                    Employee.last_name.ilike(pattern),
                )
            )
        if is_active is not None:
            filters.append(Employee.is_active.is_(is_active))
        missing_face_profile = case(
            (
                or_(
                    Employee.profile_image_path.is_(None),
                    Employee.profile_image_path == "",
                ),
                1,
            ),
            else_=0,
        )
        registered_face_filter = and_(
            Employee.profile_image_path.is_not(None),
            Employee.profile_image_path != "",
        )
        if face_status == "registered":
            filters.append(registered_face_filter)
        elif face_status == "missing":
            filters.append(
                or_(
                    Employee.profile_image_path.is_(None),
                    Employee.profile_image_path == "",
                )
            )
        total = db.scalar(select(func.count()).select_from(Employee).where(*filters)) or 0
        order_by = []
        if sort_by == "face_status":
            order_by.append(
                missing_face_profile.asc()
                if sort_direction == "asc"
                else missing_face_profile.desc()
            )
            order_by.append(Employee.employee_code.asc())
        elif sort_by == "employee_code":
            order_by.append(
                Employee.employee_code.asc()
                if sort_direction == "asc"
                else Employee.employee_code.desc()
            )
        else:
            if registered_faces_first:
                order_by.append(missing_face_profile.asc())
            if sort_employee_code:
                order_by.append(Employee.employee_code.asc())
            else:
                order_by.extend((Employee.created_at.desc(), Employee.employee_code.asc()))
        employees = db.scalars(
            select(Employee)
            .where(*filters)
            .order_by(*order_by)
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
