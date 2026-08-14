from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.orm import Base


class MoDailyTransactionDetail1(Base):
    """
    Detail table storing the department personnel counts from group1&2 of the daily report.
    """

    __tablename__ = "mo_daily_transaction_details"

    # --- Key & Identity ---
    mo_daily_transaction_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("mo_daily_transactions.mo_daily_transaction_id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        index=True,
    )

    # --- Prefix: dept_ (Department & Personnel Metrics) ---
    dept_guard_post_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="จำนวนจุดตรวจ"
    )
    dept_current_personnel_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="กำลังพลปัจจุบัน"
    )
    dept_missing_regular_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="ขาดประจำการ"
    )
    dept_missing_personnel_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="กำลังพลขาด"
    )
    dept_supplement_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="กำลังพลแทน"
    )
    dept_recruitment_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="กำลังพลใหม่"
    )
    dept_reserve_units_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="หน่วยทหารพราน"
    )
    dept_reserve_personnel_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="กำลังพลทหารพราน"
    )
    dept_extra_1: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Extra department field 1"
    )
    dept_extra_2: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Extra department field 2"
    )
    dept_extra_3: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Extra department field 3"
    )
    dept_extra_4: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Extra department field 4"
    )
    dept_extra_5: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Extra department field 5"
    )

    # --- Prefix: leave_ (Leaves & Status Changes) ---
    leave_personal_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="ลากิจ"
    )
    leave_sick_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="ลาป่วย"
    )
    leave_absent_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="ลากิจขาด"
    )
    leave_deserted_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="หลบหนี"
    )
    leave_resigned_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="ลาออก"
    )
    leave_terminated_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="ส่ง รปภ. คืนฝ่ายบริหารงานบุคคล"
    )
    leave_extra_1: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Extra leave field 1"
    )
    leave_extra_2: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Extra leave field 2"
    )
    leave_extra_3: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Extra leave field 3"
    )
    leave_extra_4: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Extra leave field 4"
    )
    leave_extra_5: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Extra leave field 5"
    )

    # --- Prefix: shift_ (Work Shifts) ---
    shift_18_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="เวร18ชม"
    )
    shift_24_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="เวร24ชม"
    )
    shift_36_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="เวร36ชม"
    )
    shift_extra_1: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Extra shift field 1"
    )
    shift_extra_2: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Extra shift field 2"
    )
    shift_extra_3: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Extra shift field 3"
    )
    shift_extra_4: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Extra shift field 4"
    )
    shift_extra_5: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Extra shift field 5"
    )

    # --- Prefix: training_ (Training Records) ---
    training_shift_change_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="ฝึกปรับเวร"
    )
    training_planned_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="ฝึกตามแผน"
    )
    training_supervise_onsite_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="4.3 ควบคุมหน้างาน"
    )
    training_supervise_virtual_simulation_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="4.4 จำลองสถานการณ์เสมือนจริง"
    )
    training_extra_2: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Extra training field 2"
    )
    training_extra_3: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Extra training field 3"
    )

    # --- Prefix: employer_ (Employer Visit Summary) ---
    employer_number_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="เข้าพบผู้ว่าจ้าง"
    )
    employer_problem_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="พบปัญหา"
    )

    # --- Timestamps ---
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
            f"<MoDailyTransactionDetail1(txn={self.mo_daily_transaction_id}, "
            f"guard_post={self.dept_guard_post_count}, "
            f"personnel={self.dept_current_personnel_count})>"
        )
