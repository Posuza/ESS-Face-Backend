from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.orm import Base


class Employee(Base):
    __tablename__ = "employees"

    employee_code: Mapped[str] = mapped_column(String(6), primary_key=True, index=True)
    password: Mapped[str] = mapped_column(String(6), nullable=False)
    role_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("roles.role_id"), nullable=False
    )
    name_prefix_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("name_prefixs.prefix_id"), nullable=False
    )

    first_name: Mapped[str] = mapped_column(String(150), nullable=False)
    last_name: Mapped[str] = mapped_column(String(150), nullable=False)

    profile_image_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    profile_image_updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )

    birth_date: Mapped[date] = mapped_column(Date, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(
        String(100), unique=True, index=True, nullable=True
    )
    phone_number: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    address_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("addresses.address_id"), nullable=True
    )
    field_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("fields.field_id"), nullable=True
    )
    department_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("departments.department_id"), nullable=True
    )
    division_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("divisions.division_id"), nullable=True
    )
    position_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("positions.position_id"), nullable=True
    )

    routes_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("routes.route_id"), nullable=True
    )

    shift_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("shifts.shift_id"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("1")
    )

    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    leave_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

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
