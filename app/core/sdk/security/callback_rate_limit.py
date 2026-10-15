from __future__ import annotations

import math
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.sdk.auth_callback_ip_limit import AuthCallbackIpLimit


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


class CallbackAttemptStore:
    """Database-backed rolling failure counter and temporary IP block list."""

    def __init__(
        self,
        *,
        max_failures: int,
        window_seconds: int,
        block_seconds: int,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self.block_seconds = block_seconds
        self._clock = clock

    def retry_after(self, db: Session, client_ip: str) -> int:
        row = db.get(AuthCallbackIpLimit, client_ip)
        if row is None or row.blocked_until is None:
            return 0
        seconds = (_utc(row.blocked_until) - self._clock()).total_seconds()
        return max(0, math.ceil(seconds))

    def record_failure(self, db: Session, client_ip: str) -> int:
        for attempt in range(2):
            try:
                return self._record_failure(db, client_ip)
            except IntegrityError:
                db.rollback()
                if attempt:
                    raise
        return 0

    def _record_failure(self, db: Session, client_ip: str) -> int:
        now = self._clock()
        row = (
            db.query(AuthCallbackIpLimit)
            .filter(AuthCallbackIpLimit.ip_address == client_ip)
            .with_for_update()
            .first()
        )
        if row is None:
            row = AuthCallbackIpLimit(
                ip_address=client_ip,
                failure_count=0,
                window_started_at=now,
            )
            db.add(row)

        window_expired = (
            now - _utc(row.window_started_at)
        ) >= timedelta(seconds=self.window_seconds)
        block_expired = row.blocked_until is not None and _utc(row.blocked_until) <= now
        if window_expired or block_expired:
            row.failure_count = 0
            row.window_started_at = now
            row.blocked_until = None

        row.failure_count += 1
        retry_after = 0
        if row.failure_count >= self.max_failures:
            row.blocked_until = now + timedelta(seconds=self.block_seconds)
            row.block_reason = "Too many rejected callback attempts"
            retry_after = self.block_seconds

        db.commit()
        return retry_after
