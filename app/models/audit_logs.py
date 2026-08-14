from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,  # ← MySQL production uses BIGINT — no DB change needed
    DateTime,
    ForeignKey,
    Integer,  # ← SQLite dev / local — INTEGER PRIMARY KEY auto-increments
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.orm import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    log_id: Mapped[int] = mapped_column(
        # BigInteger, Identity(always=True), primary_key=True, nullable=False
        Integer,
        primary_key=True,
        autoincrement=True,
        nullable=False,
    )
    # NULL when the action is performed by an unauthenticated user (e.g. failed login)
    employee_code: Mapped[Optional[str]] = mapped_column(
        String(6), ForeignKey("employees.employee_code"), nullable=True, index=True
    )
    user_name: Mapped[str] = mapped_column(String(150), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        default=func.now(),
        index=True,
    )
    ip_address: Mapped[str] = mapped_column(String(512), nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
