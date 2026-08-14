from app.core import response
from app.core.orm import get_session
from app.models.departments import Department
from app.schemas.departments import DepartmentCreate, DepartmentUpdate
from sqlalchemy import func, select, update


class DepartmentService:
    def list_departments(self) -> list[dict]:
        with get_session() as session:
            rows = (
                session.execute(
                    select(Department).order_by(Department.department_id.desc())
                )
                .scalars()
                .all()
            )
            return [row.__dict__ for row in rows]

    def create_department(self, payload: DepartmentCreate) -> dict:
        p = payload.model_dump()

        with get_session() as session:
            department_entry = Department(
                department_name=p["department_name"],
                field_id=p["field_id"],
                is_active=p["is_active"],
                created_by=p["created_by"],
                updated_by=p["created_by"],  # Can mirror created_by initially
                created_at=func.now(),
                updated_at=func.now(),
            )
            session.add(department_entry)
            session.commit()
            session.refresh(department_entry)
            return department_entry.__dict__

    def get_department(self, department_id: int) -> dict:
        with get_session() as session:
            row = (
                session.execute(
                    select(Department).where(Department.department_id == department_id)
                )
                .scalars()
                .first()
            )
        if not row:
            raise response.error("CLIENT.ER_CLIENT_2002")
        return row.__dict__

    def update_department(self, department_id: int, payload: DepartmentUpdate) -> dict:
        with get_session() as session:
            existing = session.execute(
                select(Department.department_id).where(
                    Department.department_id == department_id
                )
            ).first()
            if not existing:
                raise response.error("CLIENT.ER_CLIENT_2002")

        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            raise response.error("CLIENT.ER_CLIENT_2001")

        updates["updated_at"] = func.now()

        with get_session() as session:
            session.execute(
                update(Department)
                .where(Department.department_id == department_id)
                .values(**updates)
            )
            session.commit()

        return self.get_department(department_id)

    def delete_department(self, department_id: int) -> dict:
        with get_session() as session:
            department_entry = (
                session.execute(
                    select(Department).where(Department.department_id == department_id)
                )
                .scalars()
                .first()
            )

            if not department_entry:
                raise response.error("CLIENT.ER_CLIENT_2002")

            session.delete(department_entry)
            session.commit()

        return {"detail": "Department deleted successfully"}
