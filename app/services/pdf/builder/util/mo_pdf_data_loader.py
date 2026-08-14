from __future__ import annotations

from datetime import datetime, time
from typing import Any, Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.mo_daily_transactions import ApprovedStatusEnum, MoDailyTransaction
from app.services.mo_daily_transactions import MoDailyTransactionService


class MoPdfDataLoader:
    @classmethod
    def load_rows(cls, *, db: Session, filters: Mapping[str, Any]) -> list[dict[str, Any]]:
        stmt = select(MoDailyTransaction)

        ids = filters.get("mo_daily_transaction_ids") or filters.get("ids")
        if ids:
            stmt = stmt.where(MoDailyTransaction.mo_daily_transaction_id.in_(ids))

        department_id = filters.get("department_id")
        if department_id not in (None, ""):
            stmt = stmt.where(MoDailyTransaction.department_id == int(department_id))

        division_id = filters.get("division_id")
        if division_id not in (None, ""):
            stmt = stmt.where(MoDailyTransaction.division_id == int(division_id))

        created_by = filters.get("created_by")
        if created_by:
            stmt = stmt.where(MoDailyTransaction.created_by == str(created_by))

        status = filters.get("status") or filters.get("approved_status")
        if status:
            stmt = stmt.where(MoDailyTransaction.approved_status == ApprovedStatusEnum(str(status)))

        start_date = cls.parse_datetime(filters.get("start_date"))
        if start_date:
            stmt = stmt.where(MoDailyTransaction.created_at >= start_date)

        end_date = cls.parse_datetime(filters.get("end_date"))
        if end_date:
            if end_date.time() == time(0, 0):
                end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
            stmt = stmt.where(MoDailyTransaction.created_at <= end_date)

        stmt = stmt.order_by(
            MoDailyTransaction.created_at.asc(),
            MoDailyTransaction.division_id.asc(),
            MoDailyTransaction.mo_daily_transaction_id.asc(),
        )
        transactions = db.execute(stmt).scalars().all()
        return [MoDailyTransactionService._build_response(row, db) for row in transactions]

    @staticmethod
    def parse_datetime(value: Any) -> datetime | None:
        if value in (None, ""):
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            normalized = value.replace("Z", "+00:00")
            try:
                return datetime.fromisoformat(normalized)
            except ValueError:
                try:
                    return datetime.strptime(value, "%Y-%m-%d")
                except ValueError:
                    return None
        return None
