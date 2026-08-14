from typing import List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.mo.config import ACCESS_DIVISION_ONLY, get_access_level
from app.models.departments import Department
from app.models.divisions import Division
from app.models.employees import Employee


class MoWorkplaceService:
    """Queries for the workplace organization hierarchy."""

    @staticmethod
    def list_divisions(
        db: Session,
        department_id: int,
        field_id: int | None = None,
        current_employee: Employee | None = None,
    ) -> List[Division]:
        stmt = select(Division).where(
            Division.is_active,
            Division.department_id == department_id,
        )

        if field_id is not None:
            stmt = stmt.where(Division.field_id == field_id)

        if current_employee is not None:
            level = get_access_level(current_employee.position_id)
            if level == ACCESS_DIVISION_ONLY:
                stmt = stmt.where(
                    Division.division_id == current_employee.division_id
                )

        stmt = stmt.order_by(Division.division_name)
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def list_departments_by_field(
        db: Session,
        field_id: int,
    ) -> List[Department]:
        stmt = (
            select(Department)
            .where(
                Department.is_active,
                Department.field_id == field_id,
            )
            .order_by(Department.department_name)
        )
        return list(db.execute(stmt).scalars().all())
