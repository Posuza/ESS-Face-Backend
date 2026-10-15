from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.sdk.registries import (
    CLIENT_AUTH_CALLBACK_IP_MANUALLY_BLOCKED,
    CLIENT_AUTH_CALLBACK_IP_REMOVED,
    CLIENT_AUTH_CALLBACK_IP_UNBLOCKED,
)
from app.core.shared.audit_logger import audit_logger
from app.core.shared.config import settings
from app.models.sdk.auth_callback_ip_limit import AuthCallbackIpLimit
from app.schemas.sdk.auth import BlockedClientIpSummary, ClientIpBlockCreate


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


class BlockedClientIpService:
    @staticmethod
    def _get(db: Session, ip_address: str) -> AuthCallbackIpLimit:
        row = db.get(AuthCallbackIpLimit, ip_address)
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="The client IP record was not found.",
            )
        return row

    @staticmethod
    def _summary(row: AuthCallbackIpLimit, now: datetime) -> BlockedClientIpSummary:
        retry_after = 0
        if row.blocked_until is not None:
            retry_after = max(
                0,
                math.ceil((_utc(row.blocked_until) - now).total_seconds()),
            )
        return BlockedClientIpSummary(
            ip_address=row.ip_address,
            failure_count=row.failure_count,
            window_started_at=row.window_started_at,
            blocked_until=row.blocked_until,
            reason=row.block_reason,
            updated_at=row.updated_at,
            is_blocked=retry_after > 0,
            retry_after_seconds=retry_after,
        )

    @classmethod
    def list_entries(cls, db: Session) -> list[BlockedClientIpSummary]:
        now = datetime.now(timezone.utc)
        rows = (
            db.query(AuthCallbackIpLimit)
            .order_by(AuthCallbackIpLimit.updated_at.desc())
            .all()
        )
        return [cls._summary(row, now) for row in rows]

    @classmethod
    def block(
        cls,
        db: Session,
        payload: ClientIpBlockCreate,
    ) -> BlockedClientIpSummary:
        now = datetime.now(timezone.utc)
        row = db.get(AuthCallbackIpLimit, payload.ip_address)
        if row is None:
            row = AuthCallbackIpLimit(
                ip_address=payload.ip_address,
                failure_count=settings.CALLBACK_MAX_FAILED_ATTEMPTS,
                window_started_at=now,
            )
            db.add(row)
        else:
            row.failure_count = max(
                row.failure_count,
                settings.CALLBACK_MAX_FAILED_ATTEMPTS,
            )
            row.window_started_at = now
        row.blocked_until = now + timedelta(minutes=payload.duration_minutes)
        row.block_reason = payload.reason
        db.commit()
        db.refresh(row)
        audit_logger.log(
            action=CLIENT_AUTH_CALLBACK_IP_MANUALLY_BLOCKED.format(
                ip_address=row.ip_address,
                duration_minutes=payload.duration_minutes,
            )
        )
        return cls._summary(row, now)

    @classmethod
    def unblock(cls, db: Session, ip_address: str) -> BlockedClientIpSummary:
        now = datetime.now(timezone.utc)
        row = cls._get(db, ip_address)
        row.failure_count = 0
        row.window_started_at = now
        row.blocked_until = None
        db.commit()
        db.refresh(row)
        audit_logger.log(
            action=CLIENT_AUTH_CALLBACK_IP_UNBLOCKED.format(ip_address=ip_address)
        )
        return cls._summary(row, now)

    @classmethod
    def delete(cls, db: Session, ip_address: str) -> None:
        row = cls._get(db, ip_address)
        db.delete(row)
        db.commit()
        audit_logger.log(
            action=CLIENT_AUTH_CALLBACK_IP_REMOVED.format(ip_address=ip_address)
        )


blocked_client_ip_service = BlockedClientIpService()
