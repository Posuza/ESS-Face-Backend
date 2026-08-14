import logging
from typing import Optional
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.employee_permissions import EmployeePermission
from app.schemas.employee_permissions import EmployeePermissionCreate, EmployeePermissionUpdate

logger = logging.getLogger(__name__)

class EmployeePermissionService:
    @staticmethod
    def create(db: Session, permission_in: EmployeePermissionCreate) -> EmployeePermission:
        db_obj = EmployeePermission(**permission_in.model_dump())
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    @staticmethod
    def get_by_employee_code(db: Session, employee_code: str) -> list[EmployeePermission]:
        stmt = select(EmployeePermission).where(EmployeePermission.employee_code == employee_code)
        return list(db.scalars(stmt).all())

    @staticmethod
    def get_specific_permission(
        db: Session, employee_code: str, permissions_name: str
    ) -> Optional[EmployeePermission]:
        stmt = select(EmployeePermission).where(
            EmployeePermission.employee_code == employee_code,
            EmployeePermission.permissions_name == permissions_name
        )
        return db.scalars(stmt).first()

    @staticmethod
    def update(
        db: Session, employee_code: str, permissions_name: str, permission_in: EmployeePermissionUpdate
    ) -> Optional[EmployeePermission]:
        db_obj = EmployeePermissionService.get_specific_permission(db, employee_code, permissions_name)
        if not db_obj:
            return None

        update_data = permission_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    @staticmethod
    def delete(db: Session, employee_code: str, permissions_name: str) -> bool:
        db_obj = EmployeePermissionService.get_specific_permission(db, employee_code, permissions_name)
        if not db_obj:
            return False

        db.delete(db_obj)
        db.commit()
        return True
