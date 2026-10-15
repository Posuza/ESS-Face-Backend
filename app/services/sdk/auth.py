from __future__ import annotations

import re
import secrets

from fastapi import HTTPException, Request, status
from starlette.requests import HTTPConnection
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.shared.audit_logger import audit_logger, get_client_ip, set_audit_context
from app.core.shared.config import settings
from app.core.sdk.registries import (
    CLIENT_AUTH_APP_REJECTED,
    CLIENT_AUTH_APP_CREATED,
    CLIENT_AUTH_APP_DELETED,
    CLIENT_AUTH_APP_UPDATED,
    CLIENT_AUTH_CALLBACK_ACCEPTED,
    CLIENT_AUTH_CALLBACK_IP_BLOCKED,
    CLIENT_AUTH_CALLBACK_REJECTED,
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
    CLIENT_AUTH_SIGNING_KEY_REVEALED,
    CLIENT_AUTH_SIGNING_KEY_ROTATED,
)
from app.schemas.auth.face_verify import FaceVerifyRequest
from app.core.sdk.security.client_ticket import (
    InvalidClientTicket,
    issue_client_ticket,
    verify_client_ticket,
)
from app.core.sdk.security.callback_origin import (
    InvalidCallbackUrl,
    callback_origin,
    callback_matches_origin,
    normalize_allowed_origin,
)
from app.core.sdk.security.callback_rate_limit import CallbackAttemptStore
from app.models.sdk.auth_app_registry import AuthAppRegistry
from app.models.auth.employees import Employee
from app.schemas.sdk.auth import (
    AppRegistrationCreate,
    AppRegistrationUpdate,
    CLIENT_PUBLIC_KEY_PATTERN,
)
from app.services.auth.auth import employee_auth_service
from app.services.auth.face_verify import face_verify_service


callback_attempt_store = CallbackAttemptStore(
    max_failures=settings.CALLBACK_MAX_FAILED_ATTEMPTS,
    window_seconds=settings.CALLBACK_FAILURE_WINDOW_SECONDS,
    block_seconds=settings.CALLBACK_IP_BLOCK_SECONDS,
)


class ClientAuthService:
    """Authentication contract for external ESS clients.

    Face enrollment remains owned by the registration API. This service only
    reads an enrolled profile and authenticates against it.
    """

    @classmethod
    def generate_key_pair(cls) -> tuple[str, str]:
        return secrets.token_urlsafe(12), secrets.token_urlsafe(48)

    @classmethod
    def register_application(
        cls,
        db: Session,
        payload: AppRegistrationCreate,
        actor_employee_code: str,
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

        generated_public_key, generated_private_key = cls.generate_key_pair()
        app = AuthAppRegistry(
            app_name=payload.app_name,
            public_key=payload.public_key or generated_public_key,
            private_key=payload.private_key or generated_private_key,
            allowed_callback_origin=cls._normalize_allowed_origin(
                payload.allowed_callback_origin
            ),
            created_by=actor_employee_code,
            updated_by=actor_employee_code,
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
        audit_logger.log(
            action=CLIENT_AUTH_APP_CREATED.format(
                app_name=app.app_name,
                public_key=app.public_key,
            )
        )
        return app

    @staticmethod
    def list_applications(db: Session) -> list[AuthAppRegistry]:
        return (
            db.query(AuthAppRegistry)
            .order_by(AuthAppRegistry.app_name.asc())
            .all()
        )

    @staticmethod
    def _application_by_id(db: Session, app_registration_id: int) -> AuthAppRegistry:
        app = db.get(AuthAppRegistry, app_registration_id)
        if app is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client application was not found.",
            )
        return app

    @classmethod
    def update_application(
        cls,
        db: Session,
        app_registration_id: int,
        payload: AppRegistrationUpdate,
        actor_employee_code: str,
    ) -> AuthAppRegistry:
        app = cls._application_by_id(db, app_registration_id)
        changes = payload.model_dump(exclude_unset=True)

        if "allowed_callback_origin" in changes:
            changes["allowed_callback_origin"] = cls._normalize_allowed_origin(
                changes["allowed_callback_origin"]
            )

        for field, value in changes.items():
            setattr(app, field, value)
        app.updated_by = actor_employee_code

        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An application with this name is already registered.",
            )
        db.refresh(app)
        audit_logger.log(
            action=CLIENT_AUTH_APP_UPDATED.format(
                app_name=app.app_name,
                fields=",".join(sorted(changes)),
            )
        )
        return app

    @classmethod
    def rotate_signing_key(
        cls,
        db: Session,
        app_registration_id: int,
        actor_employee_code: str,
    ) -> AuthAppRegistry:
        app = cls._application_by_id(db, app_registration_id)
        app.private_key = secrets.token_urlsafe(48)
        app.updated_by = actor_employee_code
        db.commit()
        db.refresh(app)
        audit_logger.log(
            action=CLIENT_AUTH_SIGNING_KEY_ROTATED.format(app_name=app.app_name)
        )
        return app

    @classmethod
    def reveal_signing_key(
        cls,
        db: Session,
        app_registration_id: int,
    ) -> str:
        app = cls._application_by_id(db, app_registration_id)
        audit_logger.log(
            action=CLIENT_AUTH_SIGNING_KEY_REVEALED.format(app_name=app.app_name)
        )
        return app.private_key

    @classmethod
    def delete_application(
        cls,
        db: Session,
        app_registration_id: int,
    ) -> None:
        app = cls._application_by_id(db, app_registration_id)
        app_name = app.app_name
        public_key = app.public_key
        db.delete(app)
        db.commit()
        audit_logger.log(
            action=CLIENT_AUTH_APP_DELETED.format(
                app_name=app_name,
                public_key=public_key,
            )
        )

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

    @classmethod
    def registered_application(
        cls,
        db: Session,
        public_key: str,
    ) -> AuthAppRegistry:
        """Return an active SDK application or raise the standard rejection."""
        return cls._registered_app(db, public_key)

    @staticmethod
    def _normalize_allowed_origin(value: str) -> str:
        try:
            return normalize_allowed_origin(value)
        except InvalidCallbackUrl as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc

    @classmethod
    def registered_application_for_callback(
        cls,
        db: Session,
        public_key: str,
        return_to: str,
        request: HTTPConnection,
    ) -> AuthAppRegistry:
        client_ip = get_client_ip(request)
        retry_after = callback_attempt_store.retry_after(db, client_ip)
        if retry_after:
            audit_logger.log(
                action=CLIENT_AUTH_CALLBACK_IP_BLOCKED.format(
                    retry_after_seconds=retry_after
                )
            )
            cls._raise_callback_ip_blocked(retry_after)

        safe_public_key = cls._safe_audit_value(public_key, 32)
        safe_origin = cls._callback_audit_origin(return_to)
        try:
            app = cls._registered_app(db, public_key)
        except HTTPException:
            retry_after = cls._record_callback_failure(
                db,
                client_ip,
                reason="invalid_public_key",
                public_key=safe_public_key,
                origin=safe_origin,
            )
            if retry_after:
                cls._raise_callback_ip_blocked(retry_after)
            raise
        if not callback_matches_origin(return_to, app.allowed_callback_origin):
            retry_after = cls._record_callback_failure(
                db,
                client_ip,
                reason="origin_mismatch",
                public_key=safe_public_key,
                origin=safe_origin,
            )
            if retry_after:
                cls._raise_callback_ip_blocked(retry_after)
            safe_redirect_url = cls._client_error_redirect(
                app.allowed_callback_origin,
                "invalid_callback",
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "message": "Callback URL is not registered for this client application.",
                    "code": "CALLBACK_ORIGIN_REJECTED",
                    "safe_redirect_url": safe_redirect_url,
                },
            )
        audit_logger.log(
            action=CLIENT_AUTH_CALLBACK_ACCEPTED.format(
                app_name=app.app_name,
                origin=safe_origin,
            )
        )
        return app

    @staticmethod
    def _safe_audit_value(value: str, max_length: int) -> str:
        return "".join(character for character in value if character.isprintable())[
            :max_length
        ]

    @classmethod
    def _callback_audit_origin(cls, return_to: str) -> str:
        try:
            return callback_origin(return_to)
        except InvalidCallbackUrl:
            return cls._safe_audit_value(return_to, 180)

    @staticmethod
    def _client_error_redirect(allowed_origin: str, code: str) -> str:
        return f"{allowed_origin}/?essauth_error={code}"

    @classmethod
    def _record_callback_failure(
        cls,
        db: Session,
        client_ip: str,
        *,
        reason: str,
        public_key: str,
        origin: str,
    ) -> int:
        retry_after = callback_attempt_store.record_failure(db, client_ip)
        audit_logger.log(
            action=CLIENT_AUTH_CALLBACK_REJECTED.format(
                reason=reason,
                public_key=public_key,
                origin=origin,
            )
        )
        if retry_after:
            audit_logger.log(
                action=CLIENT_AUTH_CALLBACK_IP_BLOCKED.format(
                    retry_after_seconds=retry_after
                )
            )
        return retry_after

    @staticmethod
    def _raise_callback_ip_blocked(retry_after: int) -> None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "message": "Too many rejected callback attempts. Please try again later.",
                "code": "CALLBACK_IP_BLOCKED",
                "retry_after_seconds": retry_after,
            },
            headers={"Retry-After": str(retry_after)},
        )

    @classmethod
    def validate_callback(
        cls,
        db: Session,
        public_key: str,
        return_to: str | None,
        request: HTTPConnection,
    ) -> dict:
        resolved_return_to = return_to
        if not resolved_return_to:
            client_ip = get_client_ip(request)
            retry_after = callback_attempt_store.retry_after(db, client_ip)
            if retry_after:
                cls._raise_callback_ip_blocked(retry_after)
            try:
                app = cls._registered_app(db, public_key)
            except HTTPException:
                retry_after = cls._record_callback_failure(
                    db,
                    client_ip,
                    reason="invalid_public_key",
                    public_key=cls._safe_audit_value(public_key, 32),
                    origin="registered_default",
                )
                if retry_after:
                    cls._raise_callback_ip_blocked(retry_after)
                raise
            if not app.allowed_callback_origin:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Client application has no registered callback origin.",
                )
            resolved_return_to = cls._normalize_allowed_origin(
                app.allowed_callback_origin
            )

        cls.registered_application_for_callback(
            db,
            public_key,
            resolved_return_to,
            request,
        )
        return {"valid": True, "return_to": resolved_return_to}

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
        return_to: str,
        request: Request | None = None,
    ) -> dict:
        if request is None:
            raise HTTPException(status_code=500, detail="Missing request context")
        app = cls.registered_application_for_callback(
            db, public_key, return_to, request
        )
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
        return_to: str,
        request: Request,
    ) -> dict:
        app = cls.registered_application_for_callback(
            db, public_key, return_to, request
        )
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
