from __future__ import annotations

from datetime import datetime, timezone
import math
import re

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.core.shared.db.session import get_db, get_session
from app.schemas.sdk.auth import (
    ClientAuthProfile,
    ClientCallbackValidationRequest,
    ClientCallbackValidationResponse,
    ClientFaceLoginRequest,
    ClientFaceLoginResponse,
    ClientFacePasswordRecoveryResponse,
    ClientPasswordLoginRequest,
    ClientPasswordLoginResponse,
    ClientFaceTicketRequest,
    ClientLogoutRequest,
    ClientLogoutResponse,
    ClientPasswordTicketRequest,
    ClientTicketIssued,
    ClientTicketVerifyRequest,
    ClientTicketVerifyResponse,
)
from app.services.sdk.auth import client_auth_service
from app.services.sdk.presence import client_presence_service
from app.services.sdk.presence_settings import presence_settings_service
from app.services.auth.model_settings import get_frontend_model_settings
from app.core.shared.audit_logger import get_client_ip


router = APIRouter()
PRESENCE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
EMPLOYEE_ID_PATTERN = re.compile(r"^\d{6}$")


def _presence_coordinates(message: dict) -> tuple[float | None, float | None]:
    latitude_value = message.get("latitude")
    longitude_value = message.get("longitude")
    if latitude_value is None and longitude_value is None:
        return None, None
    if latitude_value is None or longitude_value is None:
        raise ValueError("Incomplete coordinates")
    latitude = float(latitude_value)
    longitude = float(longitude_value)
    if (
        not math.isfinite(latitude)
        or not math.isfinite(longitude)
        or not -90 <= latitude <= 90
        or not -180 <= longitude <= 180
    ):
        raise ValueError("Invalid coordinates")
    return latitude, longitude


@router.post("/callback/validate", response_model=ClientCallbackValidationResponse)
def validate_client_callback(
    payload: ClientCallbackValidationRequest,
    http_request: Request,
    db: Session = Depends(get_db),
) -> ClientCallbackValidationResponse:
    return ClientCallbackValidationResponse(
        **client_auth_service.validate_callback(
            db=db,
            public_key=payload.public_key,
            return_to=payload.return_to,
            request=http_request,
        )
    )


@router.websocket("/presence/ws")
async def client_presence(
    websocket: WebSocket,
    public_key: str,
    employee_id: str | None = None,
    device_id: str | None = None,
) -> None:
    if not presence_settings_service.get()["enabled"]:
        await websocket.accept()
        await websocket.close(code=1008, reason="Presence monitoring disabled")
        return
    client_ip = get_client_ip(websocket)
    await websocket.accept()
    presence = None

    query_employee_id = (employee_id or "").strip()
    query_device_id = (device_id or "").strip()
    if query_employee_id or query_device_id:
        if (
            EMPLOYEE_ID_PATTERN.fullmatch(query_employee_id) is None
            or PRESENCE_ID_PATTERN.fullmatch(query_device_id) is None
        ):
            await websocket.close(code=1008, reason="Invalid presence identity")
            return
        try:
            with get_session() as db:
                presence = client_presence_service.connect(
                    db=db,
                    public_key=public_key,
                    client_ip=client_ip,
                    origin=websocket.headers.get("origin", ""),
                    user_agent=websocket.headers.get("user-agent", ""),
                    employee_id=query_employee_id,
                    device_id=query_device_id,
                    request=websocket,
                )
        except HTTPException:
            await websocket.close(code=1008, reason="Invalid client application")
            return

    try:
        while True:
            message = await websocket.receive_json()
            if not presence_settings_service.get()["enabled"]:
                await websocket.close(code=1008, reason="Presence monitoring disabled")
                return
            if message.get("type") != "heartbeat":
                await websocket.close(code=1003, reason="Unsupported presence message")
                return
            try:
                latitude, longitude = _presence_coordinates(message)
            except (TypeError, ValueError):
                await websocket.close(code=1008, reason="Invalid presence coordinates")
                return
            if presence is None:
                heartbeat_employee_id = str(message.get("employee_id", "")).strip()
                heartbeat_device_id = str(message.get("device_id", "")).strip()
                if (
                    EMPLOYEE_ID_PATTERN.fullmatch(heartbeat_employee_id) is None
                    or PRESENCE_ID_PATTERN.fullmatch(heartbeat_device_id) is None
                ):
                    await websocket.close(code=1008, reason="Invalid presence identity")
                    return
                try:
                    with get_session() as db:
                        presence = client_presence_service.connect(
                            db=db,
                            public_key=public_key,
                            client_ip=client_ip,
                            origin=websocket.headers.get("origin", ""),
                            user_agent=websocket.headers.get("user-agent", ""),
                            employee_id=heartbeat_employee_id,
                            device_id=heartbeat_device_id,
                            request=websocket,
                            latitude=latitude,
                            longitude=longitude,
                        )
                except HTTPException:
                    await websocket.close(code=1008, reason="Invalid client application")
                    return
            client_presence_service.heartbeat(
                presence.connection_id,
                latitude=latitude,
                longitude=longitude,
            )
            await websocket.send_json(
                {
                    "type": "heartbeat_ack",
                    "server_time": datetime.now(timezone.utc).isoformat(),
                }
            )
    except WebSocketDisconnect:
        pass
    finally:
        if presence is not None:
            client_presence_service.disconnect(presence.connection_id)


@router.get("/presence/settings")
def client_presence_settings() -> dict[str, bool]:
    """Public runtime setting used by the SDK before it starts telemetry."""
    return presence_settings_service.get()


@router.post("/tickets/password", response_model=ClientTicketIssued)
def issue_password_ticket(
    payload: ClientPasswordTicketRequest,
    http_request: Request,
    db: Session = Depends(get_db),
) -> ClientTicketIssued:
    return ClientTicketIssued(
        **client_auth_service.password_ticket(
            db=db,
            public_key=payload.public_key,
            employee_code=payload.employee_code,
            password=payload.password,
            return_to=payload.return_to,
            request=http_request,
        )
    )


@router.post("/tickets/face", response_model=ClientTicketIssued)
def issue_face_ticket(
    payload: ClientFaceTicketRequest,
    http_request: Request,
    db: Session = Depends(get_db),
) -> ClientTicketIssued:
    return ClientTicketIssued(
        **client_auth_service.face_ticket(
            db=db,
            public_key=payload.public_key,
            employee_code=payload.employee_code,
            image_data_url=payload.image_data_url,
            return_to=payload.return_to,
            request=http_request,
        )
    )


@router.post("/tickets/verify", response_model=ClientTicketVerifyResponse)
def verify_ticket(
    payload: ClientTicketVerifyRequest,
    http_request: Request,
    db: Session = Depends(get_db),
) -> ClientTicketVerifyResponse:
    return ClientTicketVerifyResponse(
        **client_auth_service.verify_ticket(
            db=db,
            public_key=payload.public_key,
            ticket=payload.ticket,
            request=http_request,
        )
    )


@router.post("/logout", response_model=ClientLogoutResponse)
def client_logout(
    payload: ClientLogoutRequest,
    http_request: Request,
    db: Session = Depends(get_db),
) -> ClientLogoutResponse:
    return ClientLogoutResponse(
        **client_auth_service.logout_notification(
            db=db,
            public_key=payload.public_key,
            employee_id=payload.employee_id,
            request=http_request,
        )
    )


@router.get("/employees/{employee_code}", response_model=ClientAuthProfile)
def get_client_auth_profile(
    employee_code: str,
    db: Session = Depends(get_db),
) -> ClientAuthProfile:
    return ClientAuthProfile(**client_auth_service.get_profile(db, employee_code))


@router.post("/login/password", response_model=ClientPasswordLoginResponse)
def client_password_login(
    payload: ClientPasswordLoginRequest,
    http_request: Request,
    db: Session = Depends(get_db),
) -> ClientPasswordLoginResponse:
    return ClientPasswordLoginResponse(
        **client_auth_service.password_login(
            db=db,
            employee_code=payload.employee_code,
            password=payload.password,
            request=http_request,
        )
    )


@router.post("/login/face", response_model=ClientFaceLoginResponse)
def client_face_login(
    payload: ClientFaceLoginRequest,
    db: Session = Depends(get_db),
) -> ClientFaceLoginResponse:
    return ClientFaceLoginResponse(
        **client_auth_service.face_login(
            db=db,
            employee_code=payload.employee_code,
            image_data_url=payload.image_data_url,
        )
    )


@router.post(
    "/password/recover/face",
    response_model=ClientFacePasswordRecoveryResponse,
)
def recover_client_password_with_face(
    payload: ClientFaceLoginRequest,
    db: Session = Depends(get_db),
) -> ClientFacePasswordRecoveryResponse:
    return ClientFacePasswordRecoveryResponse(
        **client_auth_service.recover_password_with_face(
            db=db,
            employee_code=payload.employee_code,
            image_data_url=payload.image_data_url,
        )
    )


@router.get("/model-settings/frontend")
def client_frontend_model_settings():
    return get_frontend_model_settings("verify")
