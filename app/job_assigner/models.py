from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.orm import Base


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    assigned_to: Mapped[Optional[str]] = mapped_column(
        String(6), ForeignKey("employees.employee_code"), nullable=True, index=True
    )
    assigned_by: Mapped[Optional[str]] = mapped_column(
        String(6), ForeignKey("employees.employee_code"), nullable=True
    )
    workflow_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="NEW", server_default="NEW", index=True
    )
    priority: Mapped[str] = mapped_column(
        String(20), nullable=False, default="MEDIUM", server_default="MEDIUM"
    )
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[str] = mapped_column(
        String(6), ForeignKey("employees.employee_code"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        default=func.now(),
        onupdate=func.now(),
    )

    history: Mapped[list["JobWorkflowHistory"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="JobWorkflowHistory.created_at",
    )


class JobWorkflowHistory(Base):
    __tablename__ = "job_workflow_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    to_status: Mapped[str] = mapped_column(String(30), nullable=False)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    changed_by: Mapped[str] = mapped_column(
        String(6), ForeignKey("employees.employee_code"), nullable=False
    )
    assigned_from: Mapped[Optional[str]] = mapped_column(String(6), nullable=True)
    assigned_to: Mapped[Optional[str]] = mapped_column(String(6), nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        default=func.now(),
    )

    job: Mapped[Job] = relationship(back_populates="history")
