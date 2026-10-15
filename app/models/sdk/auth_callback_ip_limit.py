from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.shared.orm import Base


class AuthCallbackIpLimit(Base):
    """Shared callback-failure state used by every backend worker."""

    __tablename__ = "auth_callback_ip_limits"

    ip_address: Mapped[str] = mapped_column(String(45), primary_key=True)
    failure_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    window_started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=text("CURRENT_TIMESTAMP"),
    )
    blocked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    block_reason: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        onupdate=func.now(),
        server_default=text("CURRENT_TIMESTAMP"),
    )
