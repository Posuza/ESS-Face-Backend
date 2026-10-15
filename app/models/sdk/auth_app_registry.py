from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.shared.orm import Base


class AuthAppRegistry(Base):
    """External application allowed to request employee verification tickets."""

    __tablename__ = "auth_app_registry"

    app_registration_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    app_name: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    public_key: Mapped[str] = mapped_column(
        String(128), nullable=False, unique=True, index=True
    )
    private_key: Mapped[str] = mapped_column(String(255), nullable=False)
    allowed_callback_origin: Mapped[str | None] = mapped_column(
        String(2048), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("1"),
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
    created_by: Mapped[str | None] = mapped_column(
        String(6),
        ForeignKey("employees.employee_code"),
        nullable=True,
    )
    updated_by: Mapped[str | None] = mapped_column(
        String(6),
        ForeignKey("employees.employee_code"),
        nullable=True,
    )
