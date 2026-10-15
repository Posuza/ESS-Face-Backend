from __future__ import annotations

import logging

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.shared.audit_logger import audit_logger
from app.models.auth.employees import Employee
from app.services.auth.email import email_delivery_configured, send_password_email


_logger = logging.getLogger(__name__)


class PasswordService:
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

    def forgot_password(self, db: Session, employee_code: str) -> dict:
        employee = self._employee(db, employee_code)
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

        audit_logger.log(action="Employee password recovery email sent")
        return {
            "message": "ส่งรหัสผ่านไปยังอีเมลเรียบร้อยแล้ว กรุณาตรวจสอบอีเมลที่ลงทะเบียนไว้"
        }

    def change_password(
        self,
        db: Session,
        employee_code: str,
        old_password: str,
        new_password: str,
    ) -> dict:
        employee = self._employee(db, employee_code)
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
        audit_logger.log(action="Employee password changed successfully")

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
