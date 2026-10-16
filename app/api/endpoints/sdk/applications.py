from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import active_employee_required, roles_required
from app.api.dependencies.base import _employee_has_role, _get_active_employee
from app.core.shared.audit_logger import audit_logger
from app.core.shared.db.session import get_db, get_session
from app.core.sdk.registries import (
    CLIENT_AUTH_APP_CREATE_ATTEMPT,
    CLIENT_AUTH_APP_CREATE_FAILED,
    CLIENT_AUTH_APP_DELETE_ATTEMPT,
    CLIENT_AUTH_APP_DELETE_FAILED,
    CLIENT_AUTH_APP_UPDATE_ATTEMPT,
    CLIENT_AUTH_APP_UPDATE_FAILED,
)
from app.models.auth.employees import Employee
from app.schemas.sdk.auth import (
    AppRegistrationCreate,
    AppKeyPair,
    AppRegistrationSummary,
    AppRegistrationUpdate,
    AppSigningKeyReveal,
    AppSigningKeyRotated,
)
from app.services.sdk.auth import client_auth_service
from app.services.sdk.presence import client_presence_service
from app.services.sdk.presence_settings import presence_settings_service


router = APIRouter()


class PresenceSettingsUpdate(BaseModel):
    enabled: bool


def _presence_snapshot(db: Session) -> dict:
    """Build the enriched monitor snapshot using a short-lived DB session."""
    snapshot = client_presence_service.snapshot()
    snapshot["monitoring_enabled"] = presence_settings_service.get()["enabled"]
    employee_codes = {
        connection["employee_id"]
        for connection in snapshot["connections"]
    }
    employees = (
        db.query(Employee).filter(Employee.employee_code.in_(employee_codes)).all()
        if employee_codes
        else []
    )
    employee_names = {
        employee.employee_code: " ".join(
            value
            for value in (employee.first_name, employee.last_name)
            if value
        ).strip() or employee.employee_code
        for employee in employees
    }
    for connection in snapshot["connections"]:
        connection["employee_name"] = employee_names.get(
            connection["employee_id"],
            connection["employee_id"],
        )
    active_apps = {
        app["public_key"]: app
        for app in snapshot["applications"]
    }
    registered_apps = client_auth_service.list_applications(db)
    snapshot["summary"]["registered_applications"] = len(registered_apps)
    snapshot["summary"]["active_applications"] = len(active_apps)
    snapshot["summary"]["registered_employees"] = (
        db.query(Employee)
        .filter(Employee.is_active.is_(True))
        .count()
    )
    snapshot["applications"] = [
        {
            "app_name": app.app_name,
            "public_key": app.public_key,
            "is_active": app.is_active,
            "connections": active_apps.get(app.public_key, {}).get("connections", 0),
            "employees": active_apps.get(app.public_key, {}).get("employees", 0),
            "devices": active_apps.get(app.public_key, {}).get("devices", 0),
            "clients": active_apps.get(app.public_key, {}).get("clients", 0),
        }
        for app in registered_apps
    ]
    return snapshot


@router.get("/presence")
@active_employee_required
@roles_required("super_admin")
async def client_presence_snapshot(
    http_request: Request,
    db: Session = Depends(get_db),
    current_employee: Employee | None = None,
) -> dict:
    """Return current in-memory client presence for the live monitor."""
    return _presence_snapshot(db)


@router.websocket("/presence/ws")
async def client_presence_stream(websocket: WebSocket, employee_code: str) -> None:
    """Stream coalesced presence snapshots to an authenticated Super Admin."""
    await websocket.accept()
    try:
        with get_session() as db:
            employee = _get_active_employee(db, employee_code.strip())
            if not _employee_has_role(db, employee.employee_code, {"super_admin"}):
                raise HTTPException(status_code=403, detail="Super Admin access required")
    except HTTPException:
        await websocket.close(code=1008, reason="Super Admin access required")
        return

    updates = client_presence_service.subscribe()
    try:
        while True:
            await updates.get()
            with get_session() as db:
                snapshot = _presence_snapshot(db)
            await websocket.send_json(snapshot)
    except WebSocketDisconnect:
        pass
    finally:
        client_presence_service.unsubscribe(updates)


@router.get("/presence/settings")
@active_employee_required
@roles_required("super_admin")
async def get_presence_settings(
    http_request: Request,
    db: Session = Depends(get_db),
    current_employee: Employee | None = None,
) -> dict[str, bool]:
    return presence_settings_service.get()


@router.put("/presence/settings")
@active_employee_required
@roles_required("super_admin")
async def update_presence_settings(
    payload: PresenceSettingsUpdate,
    http_request: Request,
    db: Session = Depends(get_db),
    current_employee: Employee | None = None,
) -> dict[str, bool]:
    settings = presence_settings_service.update(payload.enabled)
    client_presence_service.publish_update()
    return settings


@router.post("/generate-key-pair", response_model=AppKeyPair)
@active_employee_required
@roles_required("super_admin")
async def generate_client_application_key_pair(
    http_request: Request,
    db: Session = Depends(get_db),
    current_employee: Employee | None = None,
) -> AppKeyPair:
    public_key, private_key = client_auth_service.generate_key_pair()
    return AppKeyPair(public_key=public_key, private_key=private_key)


@router.get("", response_model=list[AppRegistrationSummary])
@active_employee_required
@roles_required("super_admin")
async def list_client_applications(
    http_request: Request,
    db: Session = Depends(get_db),
    current_employee: Employee | None = None,
) -> list[AppRegistrationSummary]:
    audit_logger.log(action="Client application list read attempt")
    try:
        apps = client_auth_service.list_applications(db)
        response = [AppRegistrationSummary.model_validate(app) for app in apps]
    except Exception:
        audit_logger.log(action="Client application list read failed")
        raise
    audit_logger.log(action="Client application list read successful")
    return response


@router.post(
    "",
    response_model=AppRegistrationSummary,
    status_code=status.HTTP_201_CREATED,
)
@active_employee_required
@roles_required("super_admin")
async def register_client_application(
    payload: AppRegistrationCreate,
    http_request: Request,
    db: Session = Depends(get_db),
    current_employee: Employee | None = None,
) -> AppRegistrationSummary:
    assert current_employee is not None
    actor_code = current_employee.employee_code
    audit_logger.log(
        action=CLIENT_AUTH_APP_CREATE_ATTEMPT.format(
            app_name=payload.app_name,
            actor_employee_code=actor_code,
        )
    )
    try:
        app = client_auth_service.register_application(
            db,
            payload,
            actor_code,
        )
    except HTTPException as exc:
        audit_logger.log(
            action=CLIENT_AUTH_APP_CREATE_FAILED.format(
                app_name=payload.app_name,
                actor_employee_code=actor_code,
                status_code=exc.status_code,
            )
        )
        raise
    except Exception:
        audit_logger.log(
            action=CLIENT_AUTH_APP_CREATE_FAILED.format(
                app_name=payload.app_name,
                actor_employee_code=actor_code,
                status_code=500,
            )
        )
        raise
    return AppRegistrationSummary.model_validate(app)


@router.patch("/{app_registration_id}", response_model=AppRegistrationSummary)
@active_employee_required
@roles_required("super_admin")
async def update_client_application(
    app_registration_id: int,
    payload: AppRegistrationUpdate,
    http_request: Request,
    db: Session = Depends(get_db),
    current_employee: Employee | None = None,
) -> AppRegistrationSummary:
    assert current_employee is not None
    actor_code = current_employee.employee_code
    audit_logger.log(
        action=CLIENT_AUTH_APP_UPDATE_ATTEMPT.format(
            app_registration_id=app_registration_id,
            actor_employee_code=actor_code,
        )
    )
    try:
        app = client_auth_service.update_application(
            db,
            app_registration_id,
            payload,
            actor_code,
        )
    except HTTPException as exc:
        audit_logger.log(
            action=CLIENT_AUTH_APP_UPDATE_FAILED.format(
                app_registration_id=app_registration_id,
                actor_employee_code=actor_code,
                status_code=exc.status_code,
            )
        )
        raise
    except Exception:
        audit_logger.log(
            action=CLIENT_AUTH_APP_UPDATE_FAILED.format(
                app_registration_id=app_registration_id,
                actor_employee_code=actor_code,
                status_code=500,
            )
        )
        raise
    return AppRegistrationSummary.model_validate(app)


@router.delete("/{app_registration_id}")
@active_employee_required
@roles_required("super_admin")
async def delete_client_application(
    app_registration_id: int,
    http_request: Request,
    db: Session = Depends(get_db),
    current_employee: Employee | None = None,
) -> dict[str, str]:
    assert current_employee is not None
    actor_code = current_employee.employee_code
    audit_logger.log(
        action=CLIENT_AUTH_APP_DELETE_ATTEMPT.format(
            app_registration_id=app_registration_id,
            actor_employee_code=actor_code,
        )
    )
    try:
        client_auth_service.delete_application(
            db,
            app_registration_id,
            actor_code,
        )
    except HTTPException as exc:
        audit_logger.log(
            action=CLIENT_AUTH_APP_DELETE_FAILED.format(
                app_registration_id=app_registration_id,
                actor_employee_code=actor_code,
                status_code=exc.status_code,
            )
        )
        raise
    except Exception:
        audit_logger.log(
            action=CLIENT_AUTH_APP_DELETE_FAILED.format(
                app_registration_id=app_registration_id,
                actor_employee_code=actor_code,
                status_code=500,
            )
        )
        raise
    return {"message": "Client application was deleted."}


@router.get(
    "/{app_registration_id}/signing-key",
    response_model=AppSigningKeyReveal,
)
@active_employee_required
@roles_required("super_admin")
async def reveal_client_application_signing_key(
    app_registration_id: int,
    http_request: Request,
    db: Session = Depends(get_db),
    current_employee: Employee | None = None,
) -> AppSigningKeyReveal:
    return AppSigningKeyReveal(
        private_key=client_auth_service.reveal_signing_key(
            db,
            app_registration_id,
        )
    )


@router.post(
    "/{app_registration_id}/rotate-signing-key",
    response_model=AppSigningKeyRotated,
)
@active_employee_required
@roles_required("super_admin")
async def rotate_client_application_signing_key(
    app_registration_id: int,
    http_request: Request,
    db: Session = Depends(get_db),
    current_employee: Employee | None = None,
) -> AppSigningKeyRotated:
    assert current_employee is not None
    app = client_auth_service.rotate_signing_key(
        db,
        app_registration_id,
        current_employee.employee_code,
    )
    return AppSigningKeyRotated(
        message="Client application signing key was rotated.",
        updated_at=app.updated_at,
    )
