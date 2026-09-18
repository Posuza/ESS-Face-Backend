from __future__ import annotations

from fastapi import APIRouter, Depends, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.db.session import get_db
from app.schemas.face_verify import (
    FaceEnrollRequest,
    FaceEnrollResponse,
    EmployeeLookupResponse,
    FaceVerifyRequest,
    FaceVerifyResponse,
)
from app.services.face_verify import face_verify_service

router = APIRouter()


@router.get(
    "/employees/{employee_code}",
    response_model=EmployeeLookupResponse,
)
def get_employee(
    employee_code: str,
    db: Session = Depends(get_db),
) -> EmployeeLookupResponse:
    profile = face_verify_service.get_employee_profile(
        db=db,
        employee_code=employee_code,
    )
    return EmployeeLookupResponse(**profile)


@router.get("/{employee_code}/profile-image", response_class=FileResponse)
def get_profile_image(
    employee_code: str,
    db: Session = Depends(get_db),
) -> FileResponse:
    image_path = face_verify_service.get_profile_image_path(
        db=db,
        employee_code=employee_code,
    )
    return FileResponse(
        path=image_path,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store"},
    )


@router.post(
    "/verify",
    response_model=FaceVerifyResponse,
    status_code=status.HTTP_200_OK,
)
def verify_face(
    payload: FaceVerifyRequest,
    db: Session = Depends(get_db),
) -> FaceVerifyResponse:
    result = face_verify_service.verify_face(db=db, payload=payload)
    return FaceVerifyResponse(**result)


@router.post(
    "/register",
    response_model=FaceEnrollResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_face(
    payload: FaceEnrollRequest,
    db: Session = Depends(get_db),
) -> FaceEnrollResponse:
    employee = face_verify_service.enroll_face(db=db, payload=payload)
    return FaceEnrollResponse.model_validate(employee)
