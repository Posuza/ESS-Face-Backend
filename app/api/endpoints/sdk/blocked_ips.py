from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.api.dependencies import active_employee_required, roles_required
from app.core.shared.db.session import get_db
from app.models.auth.employees import Employee
from app.schemas.sdk.auth import BlockedClientIpSummary, ClientIpBlockCreate
from app.services.sdk.blocked_ips import blocked_client_ip_service


router = APIRouter()


@router.get("", response_model=list[BlockedClientIpSummary])
@active_employee_required
@roles_required("super_admin")
async def list_blocked_client_ips(
    http_request: Request,
    db: Session = Depends(get_db),
    current_employee: Employee | None = None,
) -> list[BlockedClientIpSummary]:
    return blocked_client_ip_service.list_entries(db)


@router.post(
    "",
    response_model=BlockedClientIpSummary,
    status_code=status.HTTP_201_CREATED,
)
@active_employee_required
@roles_required("super_admin")
async def block_client_ip(
    payload: ClientIpBlockCreate,
    http_request: Request,
    db: Session = Depends(get_db),
    current_employee: Employee | None = None,
) -> BlockedClientIpSummary:
    return blocked_client_ip_service.block(db, payload)


@router.patch("/{ip_address}/unblock", response_model=BlockedClientIpSummary)
@active_employee_required
@roles_required("super_admin")
async def unblock_client_ip(
    ip_address: str,
    http_request: Request,
    db: Session = Depends(get_db),
    current_employee: Employee | None = None,
) -> BlockedClientIpSummary:
    return blocked_client_ip_service.unblock(db, ip_address)


@router.delete("/{ip_address}", status_code=status.HTTP_204_NO_CONTENT)
@active_employee_required
@roles_required("super_admin")
async def delete_client_ip_record(
    ip_address: str,
    http_request: Request,
    db: Session = Depends(get_db),
    current_employee: Employee | None = None,
) -> None:
    blocked_client_ip_service.delete(db, ip_address)
