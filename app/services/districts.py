from fastapi import HTTPException
from sqlalchemy import func, select, update

from app.core.orm import get_session
from app.models.districts import District
from app.schemas.districts import DistrictCreate, DistrictUpdate


class DistrictService:
    def list_districts(self) -> list[dict]:
        with get_session() as session:
            rows = session.execute(
                select(District).order_by(District.district_id.desc())
            ).scalars().all()
            return [row.__dict__ for row in rows]

    def create_district(self, payload: DistrictCreate) -> dict:
        p = payload.model_dump()
        
        with get_session() as session:
            district_entry = District(
                district_name=p["district_name"],
                province_id=p["province_id"],
                created_by=p["created_by"],
                updated_by=p["created_by"],
                created_at=func.now(),
                updated_at=func.now()
            )
            session.add(district_entry)
            session.commit()
            session.refresh(district_entry)
            return district_entry.__dict__

    def get_district(self, district_id: int) -> dict:
        with get_session() as session:
            row = session.execute(
                select(District).where(District.district_id == district_id)
            ).scalars().first()
        if not row:
            raise HTTPException(status_code=404, detail="District not found")
        return row.__dict__

    def update_district(self, district_id: int, payload: DistrictUpdate) -> dict:
        with get_session() as session:
            existing = session.execute(
                select(District.district_id).where(District.district_id == district_id)
            ).first()
            if not existing:
                raise HTTPException(status_code=404, detail="District not found")

        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        updates["updated_at"] = func.now()

        with get_session() as session:
            session.execute(update(District).where(District.district_id == district_id).values(**updates))
            session.commit()

        return self.get_district(district_id)

    def delete_district(self, district_id: int) -> dict:
        with get_session() as session:
            district_entry = session.execute(
                select(District).where(District.district_id == district_id)
            ).scalars().first()
            
            if not district_entry:
                raise HTTPException(status_code=404, detail="District not found")
                
            session.delete(district_entry)
            session.commit()
            
        return {"detail": "District deleted successfully"}
