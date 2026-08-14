from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func, text
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.orm import Base


class ApprovedStatusEnum(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class MoDailyTransaction(Base):
    __tablename__ = "mo_daily_transactions"

    mo_daily_transaction_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, index=True
    )
    department_id: Mapped[int] = mapped_column(Integer, nullable=False)
    department_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        default="",
        comment="Snapshot of department name at creation",
    )
    division_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    division_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        default="",
        comment="Snapshot of division name at creation",
    )
    workflow_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="WAITING_DIRECTOR",
    )
    approved_by: Mapped[Optional[str]] = mapped_column(
        String(6), nullable=True, comment="Approver employee code (snapshot)"
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    approved_status: Mapped[ApprovedStatusEnum] = mapped_column(
        SQLAlchemyEnum(ApprovedStatusEnum),
        nullable=False,
        default=ApprovedStatusEnum.PENDING,
    )
    approved_remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
        default=func.now(),
        onupdate=func.now(),
    )

    created_by: Mapped[str] = mapped_column(
        String(6), nullable=False, comment="Creator employee code (snapshot)"
    )
    updated_by: Mapped[Optional[str]] = mapped_column(
        String(6), nullable=True, comment="Last updater employee code (snapshot)"
    )
