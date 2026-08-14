from typing import List, Optional

from sqlalchemy import func, select, update

from app.core import response
from app.core.orm import get_session
from app.models.employees import Employee
from app.schemas.employees import EmployeeCreate, EmployeeUpdate


class EmployeeService:
    def list_employees(
        self,
        department_id: Optional[int] = None,
        division_id: Optional[int] = None,
        field_id: Optional[int] = None,
        role_id: Optional[int] = None,
        is_active: Optional[bool] = None,
    ) -> list[dict]:
        with get_session() as session:
            stmt = select(Employee)

            if department_id is not None:
                stmt = stmt.where(Employee.department_id == department_id)
            if division_id is not None:
                stmt = stmt.where(Employee.division_id == division_id)
            if field_id is not None:
                stmt = stmt.where(Employee.field_id == field_id)
            if role_id is not None:
                stmt = stmt.where(Employee.role_id == role_id)
            if is_active is not None:
                stmt = stmt.where(Employee.is_active == is_active)

            rows = (
                session.execute(stmt.order_by(Employee.created_at.desc()))
                .scalars()
                .all()
            )
            return [row.__dict__ for row in rows]

    def create_employee(self, payload: EmployeeCreate) -> dict:
        p = payload.model_dump()

        with get_session() as session:
            # Check for existing employee code
            existing = session.execute(
                select(Employee.employee_code).where(
                    Employee.employee_code == p["employee_code"]
                )
            ).first()
            if existing:
                raise response.error("CLIENT.ER_CLIENT_2004")

            # Check for existing email if provided
            if p.get("email"):
                existing_email = session.execute(
                    select(Employee.employee_code).where(Employee.email == p["email"])
                ).first()
                if existing_email:
                    raise response.error("CLIENT.ER_CLIENT_2004")

            employee = Employee(
                employee_code=p["employee_code"],
                password=p["password"],
                role_id=p["role_id"],
                name_prefix_id=p["name_prefix_id"],
                first_name=p["first_name"],
                last_name=p["last_name"],
                profile_image_path=p.get("profile_image_path"),
                birth_date=p["birth_date"],
                email=p.get("email"),
                phone_number=p.get("phone_number"),
                address_id=p.get("address_id"),
                field_id=p["field_id"],
                department_id=p["department_id"],
                division_id=p["division_id"],
                position_id=p["position_id"],
                routes_id=p.get("routes_id"),
                shift_id=p["shift_id"],
                is_active=p["is_active"],
                start_date=p.get("start_date"),
                leave_date=p.get("leave_date"),
                created_by=p["created_by"],
                updated_by=p["created_by"],  # Can mirror created_by initially
                created_at=func.now(),
                updated_at=func.now(),
            )
            session.add(employee)
            session.commit()
            session.refresh(employee)
            return employee.__dict__

    def get_employee(self, employee_code: str) -> dict:
        with get_session() as session:
            row = (
                session.execute(
                    select(Employee).where(Employee.employee_code == employee_code)
                )
                .scalars()
                .first()
            )
        if not row:
            raise response.error("CLIENT.ER_CLIENT_2002")
        return row.__dict__

    def update_employee(self, employee_code: str, payload: EmployeeUpdate) -> dict:
        with get_session() as session:
            existing = session.execute(
                select(Employee.employee_code).where(
                    Employee.employee_code == employee_code
                )
            ).first()
            if not existing:
                raise response.error("CLIENT.ER_CLIENT_2002")

        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            raise response.error("CLIENT.ER_CLIENT_2001")

        # Track profile picture update timestamp automatically
        if "profile_image_path" in updates:
            updates["profile_image_updated_at"] = func.now()

        updates["updated_at"] = func.now()

        with get_session() as session:
            session.execute(
                update(Employee)
                .where(Employee.employee_code == employee_code)
                .values(**updates)
            )
            session.commit()

        return self.get_employee(employee_code)

    def delete_employee(self, employee_code: str) -> dict:
        with get_session() as session:
            employee = (
                session.execute(
                    select(Employee).where(Employee.employee_code == employee_code)
                )
                .scalars()
                .first()
            )

            if not employee:
                raise response.error("CLIENT.ER_CLIENT_2002")

            session.delete(employee)
            session.commit()

        return {"detail": "Employee deleted successfully"}
