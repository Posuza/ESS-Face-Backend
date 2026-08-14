from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.orm import Base


class EmployeePermission(Base):
    __tablename__ = "employee_permissions"

    employee_code: Mapped[str] = mapped_column(
        String(6), ForeignKey("employees.employee_code"), primary_key=True, index=True
    )
    permissions_name: Mapped[str] = mapped_column(
        String(255), primary_key=True, nullable=False
    )
    
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("1"), default=True
    )
    
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
    
    created_by: Mapped[Optional[str]] = mapped_column(
        String(6), ForeignKey("employees.employee_code"), nullable=False
    )
    updated_by: Mapped[Optional[str]] = mapped_column(
        String(6), ForeignKey("employees.employee_code"), nullable=True
    )
