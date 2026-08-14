from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.orm import Base


class MoTransactionDisciplineWarning(Base):
    """
    Dynamic discipline/warning items from the daily report.

    Stores individual discipline violation or warning entries
    as dynamic key-value items (e.g. phone usage, belt, badge, uniform).
    """

    __tablename__ = "mo_daily_transaction_discipline_warnings"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, index=True
    )
    mo_daily_transaction_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("mo_daily_transactions.mo_daily_transaction_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="Item key, e.g. 'discipline_custom_1'"
    )
    label: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="Display label in Thai"
    )
    value: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Count/value of the discipline item",
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
            f"<MoTransactionDisciplineWarning(id={self.id}, "
            f"txn={self.mo_daily_transaction_id}, "
            f"key={self.key!r}, label={self.label!r}, value={self.value})>"
        )
