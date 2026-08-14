"""
app.api.dependencies — decorator-based auth, role & permission guards.

Usage
-----
from app.api.dependencies import active_employee_required

@router.get("/employees")
@active_employee_required
async def list_employees(current_employee: Employee, db: Session = Depends(get_db)):
    ...
To add role / permission checks later (uncomment when ready):

    @roles_required("admin")
    @permissions_required("employees.create")
"""

from __future__ import annotations

import inspect
from functools import wraps
from typing import List, Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.audit_logger import audit_logger, set_audit_context
from app.core.db.session import get_db

from app.core.registries.dependencies_message import (
    ACCESS_DENIED_PERMISSION,
    ACCESS_DENIED_ROLE,
    ACCOUNT_INACTIVE,
    EMPLOYEE_NOT_FOUND,
)
from app.core.security.request_actor import extract_actor_employee_code
from app.models.employee_permissions import EmployeePermission
from app.models.employees import Employee
from app.models.roles import Role


def _get_active_employee(db: Session, employee_code: str) -> Employee:
    """Look up an employee by code and verify the account is active.

    Returns the Employee ORM instance.
    Raises HTTPException if not found or inactive.
    """
    employee = (
        db.query(Employee).filter(Employee.employee_code == employee_code).first()
    )

    if not employee:
        audit_logger.log(
            action=EMPLOYEE_NOT_FOUND,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ไม่พบรหัสพนักงานในระบบ โปรดติดต่อ GutsEssCenter",
        )

    if not employee.is_active:
        audit_logger.log(
            action=ACCOUNT_INACTIVE,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="บัญชีผู้ใช้ถูกปิดใช้งาน โปรดติดต่อ GutsEssCenter",
        )

    return employee


def _check_permissions(db: Session, employee_code: str, permissions: List[str]) -> bool:
    """Check if an employee has ALL the given permissions.

    Reads from the ``employee_permissions`` table (active rows only).
    """
    try:
        rows = (
            db.query(EmployeePermission.permissions_name)
            .filter(
                EmployeePermission.employee_code == employee_code,
                EmployeePermission.is_active.is_(True),
            )
            .all()
        )
        employee_perms = {row[0] for row in rows}
        return all(p in employee_perms for p in permissions)
    except Exception:
        return False


def _get_employee_role(db: Session, employee_code: str) -> Optional[str]:
    """Return the role name for an employee, or None."""
    employee = (
        db.query(Employee).filter(Employee.employee_code == employee_code).first()
    )
    if not employee:
        return None
    role = db.query(Role).filter(Role.role_id == employee.role_id).first()
    return role.role_name if role else None


def active_employee_required(func):
    """Decorator — extract employee identity from request headers and
    inject the full ``Employee`` ORM object as ``current_employee``.
    Usage
    -----
    @router.get("/me")
    @active_employee_required
    async def me(current_employee: Employee = None, db: Session = Depends(get_db)):
        return current_employee
    """

    # Build a new signature that hides ``current_employee`` from FastAPI
    original_sig = inspect.signature(func)
    new_params = [
        p for name, p in original_sig.parameters.items() if name != "current_employee"
    ]
    new_sig = original_sig.replace(parameters=new_params)

    @wraps(func)
    async def wrapper(*args, **kwargs):
        db = None
        request = None

        for value in kwargs.values():
            if isinstance(value, Session):
                db = value
            elif isinstance(value, Request):
                request = value

        # Also check positional args for request object
        for arg in args:
            if isinstance(arg, Request):
                request = arg

        if not db or not request:
            raise HTTPException(
                status_code=500,
                detail="Missing required dependencies (db session or request object)",
            )

        # Extract employee code from headers
        employee_code = extract_actor_employee_code(request)

        # Load full employee object
        current_employee = _get_active_employee(db, employee_code)

        # Set audit context with real user info (overrides middleware default)
        employee_name = (
            f"{current_employee.first_name} {current_employee.last_name}".strip()
            or current_employee.email
            or employee_code
        )
        set_audit_context(
            request=request,
            user_name=employee_name,
            employee_code=employee_code,
        )

        kwargs["current_employee"] = current_employee

        return await func(*args, **kwargs)

    wrapper.__signature__ = new_sig
    return wrapper


# ═══════════════════════════════════════════════════════════════════════
# Role-required decorator  (READY TO USE)
# ═══════════════════════════════════════════════════════════════════════


def roles_required(*allowed_roles):
    """Decorator factory — require the employee to have one of the given roles.

    Accepts roles as individual strings OR as a single list/tuple.

    Must be used **below** ``@active_employee_required`` so that
    ``current_employee`` is already injected.

    Usage
    -----
    @roles_required("admin")                 # single
    @roles_required("admin", "super_admin")  # multiple args
    @roles_required(["admin", "super_admin"]) # array
    """

    # Normalize: support both @roles_required("a", "b") and @roles_required(["a", "b"])
    if len(allowed_roles) == 1 and isinstance(allowed_roles[0], (list, tuple, set)):
        allowed_roles = tuple(allowed_roles[0])

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            db = None
            current_employee = kwargs.get("current_employee")

            for value in kwargs.values():
                if isinstance(value, Session):
                    db = value

            if not current_employee or not db:
                raise HTTPException(
                    status_code=500,
                    detail="Missing current_employee or db session",
                )

            role_name = _get_employee_role(db, current_employee.employee_code)
            if not role_name or role_name not in allowed_roles:
                audit_logger.log(
                    action=ACCESS_DENIED_ROLE,
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="ไม่สามารถเข้าถึงได้ คุณไม่มีสิทธิ์เข้าถึงข้อมูลนี้ โปรดติดต่อ GutsEssCenter",
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


# ═══════════════════════════════════════════════════════════════════════
# Permissions-required decorator  (READY TO USE)
# ═══════════════════════════════════════════════════════════════════════


class permissions_required:
    """Decorator class — require the employee to have ALL listed permissions.
    Must be used **below** ``@active_employee_required``.
    Usage
    -----
    @permissions_required("reports.read")                  # single
    @permissions_required("reports.read", "reports.write") # multiple args
    @permissions_required(["reports.read", "reports.write"]) # array
    """

    def __init__(self, *required_permissions):
        # Normalize: support both @permissions_required("a", "b") and @permissions_required(["a", "b"])
        if len(required_permissions) == 1 and isinstance(
            required_permissions[0], (list, tuple, set)
        ):
            required_permissions = tuple(required_permissions[0])
        self.required_permissions = required_permissions

    def __call__(self, func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            db = None
            current_employee = kwargs.get("current_employee")

            for value in kwargs.values():
                if isinstance(value, Session):
                    db = value

            if not current_employee or not db:
                raise HTTPException(
                    status_code=500,
                    detail="Missing current_employee or db session",
                )

            if not _check_permissions(
                db, current_employee.employee_code, self.required_permissions
            ):
                audit_logger.log(
                    action=ACCESS_DENIED_PERMISSION,
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="ไม่สามารถเข้าถึงได้ คุณไม่มีสิทธิ์เข้าถึงข้อมูลนี้ โปรดติดต่อ GutsEssCenter",
                )

            return await func(*args, **kwargs)

        return wrapper


# ═══════════════════════════════════════════════════════════════════════
# Public exports
# ═══════════════════════════════════════════════════════════════════════

__all__ = [
    "active_employee_required",
    "roles_required",
    "permissions_required",
    # "token_required",           # Activate with JWT
]
