from fastapi import HTTPException
from sqlalchemy import func, select, update

from app.core.orm import get_session
from app.models.provinces import Province
from app.schemas.provinces import ProvinceCreate, ProvinceUpdate


class ProvinceService:
    def list_provinces(self) -> list[dict]:
        with get_session() as session:
            rows = session.execute(
                select(Province).order_by(Province.province_id.desc())
            ).scalars().all()
            return [row.__dict__ for row in rows]

    def create_province(self, payload: ProvinceCreate) -> dict:
        p = payload.model_dump()
        
        with get_session() as session:
            province_entry = Province(
                province_name=p["province_name"],
                created_by=p["created_by"],
                updated_by=p["created_by"],
                created_at=func.now(),
                updated_at=func.now()
            )
            session.add(province_entry)
            session.commit()
            session.refresh(province_entry)
            return province_entry.__dict__

    def get_province(self, province_id: int) -> dict:
        with get_session() as session:
            row = session.execute(
                select(Province).where(Province.province_id == province_id)
            ).scalars().first()
        if not row:
            raise HTTPException(status_code=404, detail="Province not found")
        return row.__dict__

    def update_province(self, province_id: int, payload: ProvinceUpdate) -> dict:
        with get_session() as session:
            existing = session.execute(
                select(Province.province_id).where(Province.province_id == province_id)
            ).first()
            if not existing:
                raise HTTPException(status_code=404, detail="Province not found")

        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        updates["updated_at"] = func.now()

        with get_session() as session:
            session.execute(update(Province).where(Province.province_id == province_id).values(**updates))
            session.commit()

        return self.get_province(province_id)

    def delete_province(self, province_id: int) -> dict:
        with get_session() as session:
            province_entry = session.execute(
                select(Province).where(Province.province_id == province_id)
            ).scalars().first()
            
            if not province_entry:
                raise HTTPException(status_code=404, detail="Province not found")
                
            session.delete(province_entry)
            session.commit()
            
        return {"detail": "Province deleted successfully"}
