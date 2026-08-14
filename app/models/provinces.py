from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, func, ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.orm import Base


class Province(Base):
    __tablename__ = "provinces"

    province_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    province_name: Mapped[str] = mapped_column(String(225), nullable=False)
    
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
