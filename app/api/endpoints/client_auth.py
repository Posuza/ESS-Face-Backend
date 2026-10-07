from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.db.session import get_db
from app.schemas.client_auth import (
    ClientAuthProfile,
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
from app.services.client_auth import client_auth_service
from app.services.model_settings import get_frontend_model_settings


router = APIRouter()


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
