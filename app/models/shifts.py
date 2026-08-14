from __future__ import annotations

from datetime import date, datetime, time
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Integer,
    String,
    Time,
    func,
    ForeignKey,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.orm import Base


class Shift(Base):
    __tablename__ = "shifts"

    shift_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    shift_name_en: Mapped[str] = mapped_column(String(10), nullable=False)
    shift_name_th: Mapped[str] = mapped_column(String(10), nullable=False)
    start_time: Mapped[Optional[time]] = mapped_column(Time, nullable=False)
    end_time: Mapped[Optional[time]] = mapped_column(Time, nullable=False)

    crosses_midnight: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    break_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    work_minutes: Mapped[int] = mapped_column(Integer, default=480, nullable=False)
    grace_in_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    grace_out_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    checkin_open_before_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    checkin_open_after_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    checkout_open_before_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    checkout_open_after_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('1'))
    mark_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('0'))

    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text('CURRENT_TIMESTAMP'),
        default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text('CURRENT_TIMESTAMP'),
        server_onupdate=text('CURRENT_TIMESTAMP'),
        default=func.now(),
        onupdate=func.now(),
    )

    created_by: Mapped[str] = mapped_column(String(6), ForeignKey("employees.employee_code"), nullable=False)
    updated_by: Mapped[Optional[str]] = mapped_column(String(6), ForeignKey("employees.employee_code"), nullable=True)
