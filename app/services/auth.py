from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import BackgroundTasks, HTTPException, Request, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.audit_logger import audit_logger, set_audit_context
from app.core.registries import (
    CHANGE_PASSWORD_ATTEMPT,
    CHANGE_PASSWORD_SUCCESS,
    CLIENT_ERROR_BAD_REQUEST,
    FORGOT_PASSWORD_ATTEMPT,
    EMAIL_SEND_SUCCESS,
    FORGOT_PASSWORD_FAILED,
    LOGIN_ATTEMPT,
    LOGIN_FAILED_REASON,
    LOGIN_SUCCESS,
    LOGOUT_SUCCESS,
    REGISTER,
    REGISTER_DUPLICATE,
)
from app.models.departments import Department
from app.models.divisions import Division
from app.models.employees import Employee
from app.models.fields import FieldModel
from app.models.name_prefixs import NamePrefix
from app.models.positions import Position
from app.models.roles import Role
from app.models.routes import Route
from app.services.email import (
    send_change_password_notification_email,
    send_plain_password_email,
)

_logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# EmployeeAuthService
# ─────────────────────────────────────────────────────────────────────────────


class EmployeeAuthService:
    """Service layer for employee authentication operations.

    All business logic AND audit logging live here — endpoints only route.
    """

    @staticmethod
    def register_employee(
        db: Session,
        employee_code: str,
        password: str,
        email: Optional[str],
        first_name: str,
        last_name: str,
        phone_number: Optional[str],
        birth_date,
        role_id: int,
        name_prefix_id: int,
        field_id: Optional[int],
        department_id: Optional[int],
        division_id: Optional[int],
        position_id: Optional[int],
        shift_id: Optional[int],
        address_id: Optional[int] = None,
        routes_id: Optional[int] = None,
        start_date: Optional[Any] = None,
        leave_date: Optional[Any] = None,
        created_by: str = "SYSTEM",
    ) -> Employee:
        """
        Register a new employee.

        Audits: REGISTER on success.
        Raises:
            HTTPException: If employee_code or email already exists
        """
        # Check if employee already exists
        existing = (
            db.query(Employee).filter(Employee.employee_code == employee_code).first()
        )

        if existing:
            audit_logger.log(
                action=REGISTER_DUPLICATE.format(
                    resource="Employee", field="employee_code", value=employee_code
                ),
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="รหัสนี้มีในระบบแล้ว โปรดติดต่อ GutsEssCenter",
            )

        # Check email uniqueness if provided
        if email:
            existing_email = (
                db.query(Employee).filter(Employee.email == email.lower()).first()
            )
            if existing_email:
                audit_logger.log(
                    action=REGISTER_DUPLICATE.format(
                        resource="Employee", field="email", value=email
                    ),
                )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="อีเมลนี้มีในระบบแล้ว โปรดติดต่อ GutsEssCenter",
                )

        # Create employee
        db_employee = Employee(
            employee_code=employee_code,
            password=password,
            email=email.lower() if email else None,
            first_name=first_name,
            last_name=last_name,
            phone_number=phone_number,
            birth_date=birth_date,
            role_id=role_id,
            name_prefix_id=name_prefix_id,
            field_id=field_id,
            department_id=department_id,
            division_id=division_id,
            position_id=position_id,
            shift_id=shift_id,
            address_id=address_id,
            routes_id=routes_id,
            start_date=start_date,
            leave_date=leave_date,
            is_active=True,
            created_by=created_by,
        )

        db.add(db_employee)
        db.commit()
        db.refresh(db_employee)

        # Audit registration success
        audit_logger.log(
            action=REGISTER.format(
                resource="Employee", employee_code=db_employee.employee_code
            ),
        )

        return db_employee

    @staticmethod
    def authenticate_employee(
        db: Session, employee_code: str, password: str, request: Request | None = None
    ) -> Employee:
        """
        Authenticate employee by code and password.
        Sets audit context if request is provided.
        """
        employee = (
            db.query(Employee).filter(Employee.employee_code == employee_code).first()
        )

        # Set audit context with real user info (before any checks)
        if request:
            employee_name = (
                f"{employee.first_name} {employee.last_name}".strip()
                or employee.email
                or employee_code
                if employee
                else employee_code
            )
            set_audit_context(
                request=request,
                user_name=employee_name,
                employee_code=employee_code,
            )

        # Audit login attempt
        audit_logger.log(action=LOGIN_ATTEMPT.format(resource="Employee"))

        if not employee:
            audit_logger.log(
                action=LOGIN_FAILED_REASON.format(
                    resource="Employee",
                    reason="employee not found",
                )
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="ไม่พบรหัสพนักงานในระบบ โปรดติดต่อ GutsEssCenter",
            )

        # Verify password (plaintext comparison - TODO: hash when security enabled)
        if employee.password != password:
            audit_logger.log(
                action=LOGIN_FAILED_REASON.format(
                    resource="Employee",
                    reason="invalid password",
                )
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="รหัสผ่านไม่ถูกต้อง โปรดติดต่อ GutsEssCenter",
            )

        # Check if account is active
        if not employee.is_active:
            audit_logger.log(
                action=LOGIN_FAILED_REASON.format(
                    resource="Employee",
                    reason="account inactive",
                )
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="บัญชีผู้ใช้ถูกปิดใช้งาน โปรดติดต่อ GutsEssCenter",
            )

        # Audit login success
        audit_logger.log(action=LOGIN_SUCCESS.format(resource="Employee"))

        return employee

    @staticmethod
    def logout(employee_code: str) -> dict:
        """
        Record logout audit and return standard response.
        """
        audit_logger.log(action=LOGOUT_SUCCESS.format(resource="Employee"))
        return {"message": "ออกจากระบบสำเร็จ", "tokens_revoked": 0}

    @staticmethod
    def build_login_response(db: Session, employee: Employee) -> dict:
        """Build the login response dict, resolving IDs to display names."""
        db_role = db.query(Role).filter(Role.role_id == employee.role_id).first()
        db_position = (
            db.query(Position)
            .filter(Position.position_id == employee.position_id)
            .first()
        )
        db_prefix = (
            db.query(NamePrefix)
            .filter(NamePrefix.prefix_id == employee.name_prefix_id)
            .first()
        )
        db_field = (
            db.query(FieldModel)
            .filter(FieldModel.field_id == employee.field_id)
            .first()
        )
        db_dept = (
            db.query(Department)
            .filter(Department.department_id == employee.department_id)
            .first()
        )
        db_division = (
            db.query(Division)
            .filter(Division.division_id == employee.division_id)
            .first()
        )
        db_route = db.query(Route).filter(Route.route_id == employee.routes_id).first()

        role_name = db_role.role_name if db_role else ""
        position_name = db_position.position_name if db_position else ""
        prefix_name = db_prefix.prefix_name if db_prefix else ""
        field_name = db_field.field_name if db_field else ""
        department_name = db_dept.department_name if db_dept else ""
        division_name = db_division.division_name if db_division else ""
        route_name = db_route.route_name if db_route else ""

        return {
            "employee": {
                "employee_code": employee.employee_code,
                "email": employee.email,
                "first_name": employee.first_name,
                "last_name": employee.last_name,
                "role_name": role_name,
                "name_prefix": prefix_name,
                "field_id": employee.field_id,
                "field_name": field_name,
                "position_id": employee.position_id or None,
                "position_name": position_name,
                "department_id": employee.department_id or None,
                "department_name": department_name,
                "division_id": employee.division_id or None,
                "division_name": division_name,
                "route_id": employee.routes_id or None,
                "route_name": route_name,
            },
            "message": "เข้าสู่ระบบสำเร็จ",
        }

    @staticmethod
    def get_employee_display_name(employee: Employee) -> str:
        """Build a human-readable display name for audit logging."""
        return (
            f"{employee.first_name} {employee.last_name}".strip()
            or employee.email
            or employee.employee_code
        )


class PasswordService:
    """Service layer for password operations.

    All business logic AND audit logging live here — endpoints only route.
    """

    @staticmethod
    def forgot_password(
        db: Session,
        employee_code: str,
        send_plain_password: bool,
        background_tasks: BackgroundTasks,
    ) -> dict:
        # Look up employee
        employee = db.execute(
            select(Employee).where(Employee.employee_code == employee_code)
        ).scalar_one_or_none()

        # ── Attempt audit ──────────────────────────────────────────────
        audit_logger.log(
            action=FORGOT_PASSWORD_ATTEMPT.format(resource="Employee"),
        )

        # ── Validate ──────────────────────────────────────────────────
        if not employee:
            audit_logger.log(
                action=FORGOT_PASSWORD_FAILED.format(
                    resource="Employee", reason="Employee not found"
                ),
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="ไม่พบรหัสพนักงานในระบบ โปรดติดต่อ GutsEssCenter",
            )

        employee_name = (
            f"{employee.first_name} {employee.last_name}".strip()
            or employee.employee_code
        )

        if not employee.is_active:
            audit_logger.log(
                action=FORGOT_PASSWORD_FAILED.format(
                    resource="Employee", reason="Employee account is inactive"
                ),
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="บัญชีพนักงานถูกปิดใช้งาน โปรดติดต่อ GutsEssCenter",
            )

        if not employee.email:
            audit_logger.log(
                action=FORGOT_PASSWORD_FAILED.format(
                    resource="Employee", reason="Employee has no email registered"
                ),
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ไม่พบอีเมลที่ลงทะเบียนไว้สำหรับรหัสพนักงานนี้ โปรดติดต่อ GutsEssCenter",
            )

        # ── Send email and audit based on real result ────────────────
        email_to = employee.email
        email_emp_code = employee.employee_code

        def _send_and_audit():
            success = send_plain_password_email(
                email_to, employee_name, employee.password, email_emp_code
            )
            if success:
                audit_logger.log(
                    action=EMAIL_SEND_SUCCESS.format(
                        resource="Employee", email=email_to
                    ),
                )
            else:
                audit_logger.log(
                    action=FORGOT_PASSWORD_FAILED.format(
                        resource="Employee", reason="Email delivery failed"
                    ),
                )

        background_tasks.add_task(_send_and_audit)

        return {
            "message": "ส่งรหัสผ่านไปยังอีเมลเรียบร้อยแล้ว กรุณาตรวจสอบอีเมลที่ลงทะเบียนไว้",
        }

    @staticmethod
    def change_password(
        db: Session,
        employee_code: str,
        old_password: str,
        new_password: str,
        background_tasks: BackgroundTasks,
    ) -> dict:
        # Audit attempt
        audit_logger.log(
            action=CHANGE_PASSWORD_ATTEMPT.format(resource="Employee"),
        )

        # Look up employee
        employee = db.execute(
            select(Employee).where(Employee.employee_code == employee_code)
        ).scalar_one_or_none()

        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="ไม่พบรหัสพนักงานในระบบ โปรดติดต่อ GutsEssCenter",
            )

        if not employee.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="บัญชีพนักงานถูกปิดใช้งาน โปรดติดต่อ GutsEssCenter",
            )

        if employee.password != old_password:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="รหัสผ่านล่าสุดไม่ถูกต้อง โปรดติดต่อ GutsEssCenter",
            )

        if employee.password == new_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=CLIENT_ERROR_BAD_REQUEST,
            )

        # Store name and email before update for the email task
        employee_name = (
            f"{employee.first_name} {employee.last_name}".strip()
            or employee.employee_code
        )
        employee_email = employee.email

        # Update password (plaintext for now)
        stmt = (
            update(Employee)
            .where(Employee.employee_code == employee_code)
            .values(password=new_password)
        )
        db.execute(stmt)
        db.commit()

        # Audit password change success (immediately after commit)
        audit_logger.log(
            action=CHANGE_PASSWORD_SUCCESS.format(resource="Employee"),
        )

        # Send notification email (background, separate concern)
        def _send_notification():
            if employee_email:
                success = send_change_password_notification_email(
                    employee_email, employee_name, new_password, employee_code
                )
                if not success:
                    _logger.warning(
                        "Change-password notification email FAILED for %s", employee_email
                    )

        background_tasks.add_task(_send_notification)

        return {"message": "เปลี่ยนรหัสผ่านสำเร็จ"}


# Singleton instances
employee_auth_service = EmployeeAuthService()
password_service = PasswordService()
