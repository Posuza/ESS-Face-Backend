from __future__ import annotations

import re
import secrets

from fastapi import HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.shared.audit_logger import audit_logger, set_audit_context
from app.core.shared.config import settings
from app.core.sdk.registries import (
    CLIENT_AUTH_APP_REJECTED,
    CLIENT_AUTH_FACE_LOGIN_ATTEMPT,
    CLIENT_AUTH_FACE_LOGIN_FAILED,
    CLIENT_AUTH_FACE_LOGIN_SUCCESS,
    CLIENT_AUTH_LOGIN_FAILED,
    CLIENT_AUTH_LOGIN_SUCCESS,
    CLIENT_AUTH_LOGOUT,
    CLIENT_AUTH_PASSWORD_LOGIN_ATTEMPT,
    CLIENT_AUTH_PASSWORD_LOGIN_SUCCESS,
    CLIENT_AUTH_PASSWORD_RECOVERY_ATTEMPT,
    CLIENT_AUTH_PASSWORD_RECOVERY_FAILED,
    CLIENT_AUTH_PASSWORD_RECOVERY_SUCCESS,
    CLIENT_AUTH_PROFILE_LOOKUP,
    CLIENT_AUTH_TICKET_VERIFY_FAILED,
    CLIENT_AUTH_TICKET_VERIFY_SUCCESS,
)
from app.schemas.main.face_verify import FaceVerifyRequest
from app.core.sdk.security.client_ticket import (
    InvalidClientTicket,
    issue_client_ticket,
    verify_client_ticket,
)
from app.models.sdk.auth_app_registry import AuthAppRegistry
from app.models.main.employees import Employee
from app.schemas.sdk.auth import AppRegistrationCreate, CLIENT_PUBLIC_KEY_PATTERN
from app.services.main.auth import employee_auth_service
from app.services.main.face_verify import face_verify_service


class ClientAuthService:
    """Authentication contract for external ESS clients.

    Face enrollment remains owned by the registration API. This service only
    reads an enrolled profile and authenticates against it.
    """

    @staticmethod
    def register_application(
        db: Session,
        payload: AppRegistrationCreate,
    ) -> AuthAppRegistry:
        existing = (
            db.query(AuthAppRegistry)
            .filter(AuthAppRegistry.app_name == payload.app_name)
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An application with this name is already registered.",
            )

        app = AuthAppRegistry(
            app_name=payload.app_name,
            # Twelve random bytes encode to exactly 16 URL-safe characters.
            public_key=secrets.token_urlsafe(12),
            private_key=secrets.token_urlsafe(48),
        )
        db.add(app)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The application could not be registered because it already exists.",
            )
        db.refresh(app)
        return app

    @staticmethod
    def _registered_app(db: Session, public_key: str) -> AuthAppRegistry:
        if re.fullmatch(CLIENT_PUBLIC_KEY_PATTERN, public_key) is None:
            audit_logger.log(action=CLIENT_AUTH_APP_REJECTED)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="รหัสแอปพลิเคชันไคลเอนต์ต้องมี 16 ตัวอักษร",
            )
        app = (
            db.query(AuthAppRegistry)
            .filter(
                AuthAppRegistry.public_key == public_key,
                AuthAppRegistry.is_active.is_(True),
            )
            .first()
        )
        if not app:
            audit_logger.log(action=CLIENT_AUTH_APP_REJECTED)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="ไม่พบแอปพลิเคชันไคลเอนต์ หรือแอปพลิเคชันถูกปิดใช้งาน",
            )
        return app

    @staticmethod
    def _ticket_response(app: AuthAppRegistry, employee_id: str) -> dict:
        return {"ticket": issue_client_ticket(employee_id, app.private_key)}

    @staticmethod
    def _set_employee_audit_context(request: Request, employee: Employee) -> None:
        employee_name = (
            f"{employee.first_name} {employee.last_name}".strip()
            or employee.email
            or employee.employee_code
        )
        set_audit_context(
            request=request,
            user_name=employee_name,
            employee_code=employee.employee_code,
        )

    @staticmethod
    def _log_client_login(
        app: AuthAppRegistry,
        method: str,
        employee_code: str,
        status_code: int | None = None,
    ) -> None:
        if status_code is None:
            action = CLIENT_AUTH_LOGIN_SUCCESS.format(
                app_name=app.app_name,
                method=method,
                employee_code=employee_code,
            )
        else:
            action = CLIENT_AUTH_LOGIN_FAILED.format(
                app_name=app.app_name,
                method=method,
                employee_code=employee_code,
                status_code=status_code,
            )
        audit_logger.log(action=action)

    @classmethod
    def password_ticket(
        cls,
        db: Session,
        public_key: str,
        employee_code: str,
        password: str,
        request: Request | None = None,
    ) -> dict:
        app = cls._registered_app(db, public_key)
        code = employee_code.strip().upper()
        try:
            employee = employee_auth_service.authenticate_employee(
                db=db,
                employee_code=code,
                password=password,
                request=request,
            )
        except HTTPException as exc:
            cls._log_client_login(app, "password", code, exc.status_code)
            raise
        cls._log_client_login(app, "password", employee.employee_code)
        return cls._ticket_response(app, employee.employee_code)

    @classmethod
    def face_ticket(
        cls,
        db: Session,
        public_key: str,
        employee_code: str,
        image_data_url: str,
        request: Request,
    ) -> dict:
        app = cls._registered_app(db, public_key)
        code = employee_code.strip().upper()
        try:
            employee = face_verify_service.get_employee(db, code)
            cls._set_employee_audit_context(request, employee)
            result = face_verify_service.verify_face(
                db=db,
                payload=FaceVerifyRequest(
                    employee_code=code,
                    image_data_url=image_data_url,
                ),
            )
            if not result["is_match"]:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Employee face verification failed.",
                )
        except HTTPException as exc:
            cls._log_client_login(app, "face", code, exc.status_code)
            raise
        cls._log_client_login(app, "face", employee.employee_code)
        return cls._ticket_response(app, code)

    @classmethod
    def verify_ticket(
        cls,
        db: Session,
        public_key: str,
        ticket: str,
        request: Request,
    ) -> dict:
        app = cls._registered_app(db, public_key)
        try:
            employee_id = verify_client_ticket(
                ticket,
                app.private_key,
                settings.CLIENT_TICKET_TTL_SECONDS,
            )
            employee = face_verify_service.get_employee(db, employee_id)
        except InvalidClientTicket as exc:
            audit_logger.log(
                action=CLIENT_AUTH_TICKET_VERIFY_FAILED.format(app_name=app.app_name)
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired client ticket.",
            ) from exc
        except HTTPException:
            audit_logger.log(
                action=CLIENT_AUTH_TICKET_VERIFY_FAILED.format(app_name=app.app_name)
            )
            raise
        cls._set_employee_audit_context(request, employee)
        audit_logger.log(
            action=CLIENT_AUTH_TICKET_VERIFY_SUCCESS.format(
                app_name=app.app_name,
                employee_code=employee.employee_code,
            )
        )
        return {"employee_id": employee_id}

    @classmethod
    def logout_notification(
        cls,
        db: Session,
        public_key: str,
        employee_id: str,
        request: Request,
    ) -> dict:
        app = cls._registered_app(db, public_key)
        code = employee_id.strip().upper()
        employee = face_verify_service.get_employee(db, code)
        cls._set_employee_audit_context(request, employee)
        audit_logger.log(
            action=CLIENT_AUTH_LOGOUT.format(
                app_name=app.app_name,
                employee_code=employee.employee_code,
            )
        )
        return {"message": "Logout notification recorded."}

    @staticmethod
    def get_profile(db: Session, employee_code: str) -> dict:
        code = employee_code.strip().upper()
        audit_logger.log(
            action=CLIENT_AUTH_PROFILE_LOOKUP.format(employee_code=code)
        )
        return face_verify_service.get_employee_profile(db, code)

    @staticmethod
    def password_login(
        db: Session,
        employee_code: str,
        password: str,
        request: Request | None = None,
    ) -> dict:
        code = employee_code.strip().upper()
        audit_logger.log(
            action=CLIENT_AUTH_PASSWORD_LOGIN_ATTEMPT.format(employee_code=code)
        )
        employee = employee_auth_service.authenticate_employee(
            db=db,
            employee_code=code,
            password=password,
            request=request,
        )
        response = employee_auth_service.build_login_response(db, employee)
        audit_logger.log(
            action=CLIENT_AUTH_PASSWORD_LOGIN_SUCCESS.format(employee_code=code)
        )
        return response

    @staticmethod
    def face_login(db: Session, employee_code: str, image_data_url: str) -> dict:
        code = employee_code.strip().upper()
        audit_logger.log(
            action=CLIENT_AUTH_FACE_LOGIN_ATTEMPT.format(employee_code=code)
        )
        result = face_verify_service.verify_face(
            db=db,
            payload=FaceVerifyRequest(
                employee_code=code,
                image_data_url=image_data_url,
            ),
        )

        if not result["is_match"]:
            audit_logger.log(
                action=CLIENT_AUTH_FACE_LOGIN_FAILED.format(employee_code=code)
            )
            return {**result, "employee": None}

        employee = face_verify_service.get_employee(db, code)
        profile = employee_auth_service.build_login_response(db, employee)["employee"]
        audit_logger.log(
            action=CLIENT_AUTH_FACE_LOGIN_SUCCESS.format(employee_code=code)
        )
        return {**result, "employee": profile}

    @staticmethod
    def recover_password_with_face(
        db: Session,
        employee_code: str,
        image_data_url: str,
    ) -> dict:
        code = employee_code.strip().upper()
        audit_logger.log(
            action=CLIENT_AUTH_PASSWORD_RECOVERY_ATTEMPT.format(employee_code=code)
        )
        result = face_verify_service.verify_face(
            db=db,
            payload=FaceVerifyRequest(
                employee_code=code,
                image_data_url=image_data_url,
            ),
        )

        if not result["is_match"]:
            audit_logger.log(
                action=CLIENT_AUTH_PASSWORD_RECOVERY_FAILED.format(employee_code=code)
            )
            return {**result, "password": None}

        employee = face_verify_service.get_employee(db, code)
        password = employee.password or ""
        if len(password) != 6 or not password.isdigit():
            audit_logger.log(
                action=CLIENT_AUTH_PASSWORD_RECOVERY_FAILED.format(employee_code=code)
            )
            return {
                **result,
                "message": "ข้อมูลรหัสผ่านพนักงานไม่สมบูรณ์ โปรดติดต่อ GutsEssCenter",
                "password": None,
            }

        audit_logger.log(
            action=CLIENT_AUTH_PASSWORD_RECOVERY_SUCCESS.format(employee_code=code)
        )
        return {
            **result,
            "message": "ยืนยันใบหน้าสำเร็จ",
            "password": password,
        }


client_auth_service = ClientAuthService()
