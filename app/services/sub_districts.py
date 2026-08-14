from fastapi import HTTPException
from sqlalchemy import func, select, update

from app.core.orm import get_session
from app.models.sub_districts import SubDistrict
from app.schemas.sub_districts import SubDistrictCreate, SubDistrictUpdate


class SubDistrictService:
    def list_sub_districts(self) -> list[dict]:
        with get_session() as session:
            rows = session.execute(
                select(SubDistrict).order_by(SubDistrict.sub_district_id.desc())
            ).scalars().all()
            return [row.__dict__ for row in rows]

    def create_sub_district(self, payload: SubDistrictCreate) -> dict:
        p = payload.model_dump()
        
        with get_session() as session:
            sub_district_entry = SubDistrict(
                sub_district_name=p["sub_district_name"],
                province_id=p["province_id"],
                district_id=p["district_id"],
                created_by=p["created_by"],
                updated_by=p["created_by"],
                created_at=func.now(),
                updated_at=func.now()
            )
            session.add(sub_district_entry)
            session.commit()
            session.refresh(sub_district_entry)
            return sub_district_entry.__dict__

    def get_sub_district(self, sub_district_id: int) -> dict:
        with get_session() as session:
            row = session.execute(
                select(SubDistrict).where(SubDistrict.sub_district_id == sub_district_id)
            ).scalars().first()
        if not row:
            raise HTTPException(status_code=404, detail="Sub District not found")
        return row.__dict__

    def update_sub_district(self, sub_district_id: int, payload: SubDistrictUpdate) -> dict:
        with get_session() as session:
            existing = session.execute(
                select(SubDistrict.sub_district_id).where(SubDistrict.sub_district_id == sub_district_id)
            ).first()
            if not existing:
                raise HTTPException(status_code=404, detail="Sub District not found")

        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        updates["updated_at"] = func.now()

        with get_session() as session:
            session.execute(update(SubDistrict).where(SubDistrict.sub_district_id == sub_district_id).values(**updates))
            session.commit()

        return self.get_sub_district(sub_district_id)

    def delete_sub_district(self, sub_district_id: int) -> dict:
        with get_session() as session:
            sub_district_entry = session.execute(
                select(SubDistrict).where(SubDistrict.sub_district_id == sub_district_id)
            ).scalars().first()
            
            if not sub_district_entry:
                raise HTTPException(status_code=404, detail="Sub District not found")
                
            session.delete(sub_district_entry)
            session.commit()
            
        return {"detail": "Sub District deleted successfully"}
