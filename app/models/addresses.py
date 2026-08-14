from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.orm import Base


class Address(Base):
    __tablename__ = "addresses"

    address_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, index=True
    )
    address_detail: Mapped[str] = mapped_column(String(225), nullable=False)
    sub_district_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sub_districts.sub_district_id"), nullable=False
    )
    district_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("districts.district_id"), nullable=False
    )
    province_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("provinces.province_id"), nullable=False
    )
    postal_code_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("postal_codes.postal_code_id"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("1")
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
    created_by: Mapped[str] = mapped_column(
        String(6), ForeignKey("employees.employee_code"), nullable=False
    )
    updated_by: Mapped[Optional[str]] = mapped_column(
        String(6), ForeignKey("employees.employee_code"), nullable=True
    )
