from typing import Optional

from sqlalchemy import func, select

from app.core.db.session import get_session
from app.models.audit_logs import AuditLog
from app.schemas.audit_logs import AuditLogCreate


class AuditLogService:
    def create(self, payload: AuditLogCreate | dict) -> dict:
        """Persist a single audit log entry and return it as a dict."""
        with get_session() as session:
            # Handle both Pydantic schema and raw dictionary input for Clean Architecture compliance
            data = payload.model_dump() if hasattr(payload, "model_dump") else payload
            log = AuditLog(**data)
            session.add(log)
            try:
                session.commit()
                session.refresh(log)
            except Exception:
                session.rollback()
                raise
            return {k: v for k, v in log.__dict__.items() if not k.startswith("_")}

    def list_logs(
        self,
        employee_code: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict:
        """Return a paginated list of audit logs, newest first."""
        with get_session() as session:
            stmt = select(AuditLog)
            if employee_code:
                stmt = stmt.where(AuditLog.employee_code == employee_code)

            total: int = session.execute(
                select(func.count()).select_from(stmt.subquery())
            ).scalar_one()

            rows = (
                session.execute(
                    stmt.order_by(AuditLog.timestamp.desc()).limit(limit).offset(offset)
                )
                .scalars()
                .all()
            )

            return {
                "total": total,
                "items": [
                    {k: v for k, v in r.__dict__.items() if not k.startswith("_")}
                    for r in rows
                ],
            }

    def get(self, log_id: int) -> Optional[dict]:
        """Return a single audit log entry by primary key."""
        with get_session() as session:
            row = session.execute(
                select(AuditLog).where(AuditLog.log_id == log_id)
            ).scalar_one_or_none()
            if row is None:
                return None
            return {k: v for k, v in row.__dict__.items() if not k.startswith("_")}
