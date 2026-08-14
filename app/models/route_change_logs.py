from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.orm import Base


class RouteChangeLog(Base):
    __tablename__ = "route_change_logs"

    route_log_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, index=True
    )

    route_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("routes.route_id"), nullable=False
    )

    from_field: Mapped[str] = mapped_column(String(50), nullable=False)
    from_department: Mapped[str] = mapped_column(String(50), nullable=False)
    from_division: Mapped[str] = mapped_column(String(50), nullable=False)
    from_routes: Mapped[str] = mapped_column(String(50), nullable=False)
    from_shift: Mapped[str] = mapped_column(String(50), nullable=False)

    to_field: Mapped[str] = mapped_column(String(50), nullable=False)
    to_department: Mapped[str] = mapped_column(String(50), nullable=False)
    to_division: Mapped[str] = mapped_column(String(50), nullable=False)
    to_routes: Mapped[str] = mapped_column(String(50), nullable=False)
    to_shift: Mapped[str] = mapped_column(String(50), nullable=False)

    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        default=func.now(),
    )
    created_by: Mapped[str] = mapped_column(
        String(6), ForeignKey("employees.employee_code"), nullable=False
    )
