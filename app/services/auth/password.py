from __future__ import annotations

import logging

from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.shared.audit_logger import audit_logger
from app.core.shared.audit_logger import set_audit_context
from app.core.auth.registries import (
    PASSWORD_CHANGE_ATTEMPT,
    PASSWORD_CHANGE_FAILED,
    PASSWORD_CHANGE_SUCCESS,
    PASSWORD_RECOVERY_EMAIL_ATTEMPT,
    PASSWORD_RECOVERY_EMAIL_FAILED,
    PASSWORD_RECOVERY_EMAIL_SUCCESS,
)
from app.models.auth.employees import Employee
from app.services.auth.email import email_delivery_configured, send_password_email


_logger = logging.getLogger(__name__)


class PasswordService:
    @staticmethod
    def _set_known_employee_context(
        db: Session,
        employee_code: str,
        request: Request | None,
    ) -> None:
        if request is None:
            return
        employee = db.execute(
            select(Employee).where(Employee.employee_code == employee_code)
        ).scalar_one_or_none()
        if employee is None:
            return
        set_audit_context(
            request=request,
            user_name=f"{employee.first_name} {employee.last_name}".strip()
            or employee.employee_code,
            employee_code=employee.employee_code,
        )

    @staticmethod
    def _employee(db: Session, employee_code: str) -> Employee:
        code = (employee_code or "").strip().upper()
        if len(code) != 6 or not code.isascii() or not code.isalnum():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="กรุณากรอกรหัสพนักงาน 6 ตัว โดยใช้ตัวอักษรหรือตัวเลข",
            )

        employee = db.execute(
            select(Employee).where(Employee.employee_code == code)
        ).scalar_one_or_none()
        if employee is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="ไม่พบรหัสพนักงานในระบบ โปรดติดต่อ GutsEssCenter",
            )
        if not employee.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="บัญชีพนักงานถูกปิดใช้งาน โปรดติดต่อ GutsEssCenter",
            )
        return employee

    @staticmethod
    def _validate_password(value: str, label: str) -> str:
        if len(value) != 6 or not value.isascii() or not value.isdigit():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"กรุณากรอก{label}เป็นตัวเลข 6 หลัก",
            )
        return value

    def forgot_password(
        self,
        db: Session,
        employee_code: str,
        request: Request | None = None,
    ) -> dict:
        code = (employee_code or "").strip().upper()
        self._set_known_employee_context(db, code, request)
        audit_logger.log(
            action=PASSWORD_RECOVERY_EMAIL_ATTEMPT.format(employee_code=code)
        )
        try:
            employee = self._employee(db, code)
            if request:
                set_audit_context(
                    request=request,
                    user_name=f"{employee.first_name} {employee.last_name}".strip()
                    or employee.employee_code,
                    employee_code=employee.employee_code,
                )
            if not employee.email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="ไม่พบอีเมลที่ลงทะเบียนไว้สำหรับรหัสพนักงานนี้ โปรดติดต่อ GutsEssCenter",
                )
            if not email_delivery_configured():
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="ระบบอีเมลยังไม่พร้อมใช้งาน กรุณาติดต่อ GutsEssCenter",
                )

            employee_name = f"{employee.first_name} {employee.last_name}".strip()
            delivered = send_password_email(
                to_email=employee.email,
                employee_name=employee_name,
                employee_code=employee.employee_code,
                password=employee.password,
            )
            if not delivered:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="ไม่สามารถส่งอีเมลได้ในขณะนี้ กรุณาลองใหม่อีกครั้ง",
                )
        except HTTPException as exc:
            audit_logger.log(
                action=PASSWORD_RECOVERY_EMAIL_FAILED.format(
                    employee_code=code,
                    status_code=exc.status_code,
                )
            )
            raise
        except Exception:
            audit_logger.log(
                action=PASSWORD_RECOVERY_EMAIL_FAILED.format(
                    employee_code=code,
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            )
            raise

        audit_logger.log(
            action=PASSWORD_RECOVERY_EMAIL_SUCCESS.format(employee_code=code)
        )
        return {
            "message": "ส่งรหัสผ่านไปยังอีเมลเรียบร้อยแล้ว กรุณาตรวจสอบอีเมลที่ลงทะเบียนไว้"
        }

    def change_password(
        self,
        db: Session,
        employee_code: str,
        old_password: str,
        new_password: str,
        request: Request | None = None,
    ) -> dict:
        code = (employee_code or "").strip().upper()
        self._set_known_employee_context(db, code, request)
        audit_logger.log(action=PASSWORD_CHANGE_ATTEMPT.format(employee_code=code))
        try:
            employee = self._employee(db, code)
            if request:
                set_audit_context(
                    request=request,
                    user_name=f"{employee.first_name} {employee.last_name}".strip()
                    or employee.employee_code,
                    employee_code=employee.employee_code,
                )
            old_value = self._validate_password(old_password, "รหัสผ่านล่าสุด")
            new_value = self._validate_password(new_password, "รหัสผ่านใหม่")

            if employee.password != old_value:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="รหัสผ่านล่าสุดไม่ถูกต้อง",
                )
            if old_value == new_value:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="รหัสผ่านใหม่ต้องไม่ซ้ำกับรหัสผ่านล่าสุด",
                )

            employee.password = new_value
            db.commit()
        except HTTPException as exc:
            audit_logger.log(
                action=PASSWORD_CHANGE_FAILED.format(
                    employee_code=code,
                    status_code=exc.status_code,
                )
            )
            raise
        except Exception:
            db.rollback()
            audit_logger.log(
                action=PASSWORD_CHANGE_FAILED.format(
                    employee_code=code,
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            )
            raise

        audit_logger.log(action=PASSWORD_CHANGE_SUCCESS.format(employee_code=code))

        if employee.email and email_delivery_configured():
            employee_name = f"{employee.first_name} {employee.last_name}".strip()
            if not send_password_email(
                to_email=employee.email,
                employee_name=employee_name,
                employee_code=employee.employee_code,
                password=new_value,
                changed=True,
            ):
                _logger.warning(
                    "Password changed, but notification email failed for %s",
                    employee.employee_code,
                )

        return {"message": "เปลี่ยนรหัสผ่านสำเร็จ"}


password_service = PasswordService()
