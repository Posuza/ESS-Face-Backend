from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.orm import Base


class MoDailyTransactionProject(Base):
    """
    Detail table storing project/meeting/activity data from the daily report.
    """

    __tablename__ = "mo_daily_transaction_projects"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, index=True
    )
    mo_daily_transaction_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("mo_daily_transactions.mo_daily_transaction_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_name: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="Project name"
    )
    detail: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Meeting/detail description"
    )
    status: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="group3: normal/warning/danger | group4: predefined or custom text",
    )
    note: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Additional note"
    )

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

    def __repr__(self) -> str:
        return (
            f"<MoDailyTransactionProject(id={self.id}, "
            f"txn={self.mo_daily_transaction_id}, "
            f"name={self.project_name!r})"
        )
