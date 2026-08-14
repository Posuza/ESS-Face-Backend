from fastapi import HTTPException
from sqlalchemy import func, select, update

from app.core.orm import get_session
from app.models.name_prefixs import NamePrefix
from app.schemas.name_prefixs import NamePrefixCreate, NamePrefixUpdate


class NamePrefixService:
    def list_prefixes(self) -> list[dict]:
        with get_session() as session:
            rows = session.execute(
                select(NamePrefix).order_by(NamePrefix.prefix_id.desc())
            ).scalars().all()
            return [row.__dict__ for row in rows]

    def create_prefix(self, payload: NamePrefixCreate) -> dict:
        p = payload.model_dump()
        
        with get_session() as session:
            prefix_entry = NamePrefix(
                prefix_name=p["prefix_name"],
                is_active=p["is_active"],
                created_by=p["created_by"],
                updated_by=p["created_by"],
                created_at=func.now(),
                updated_at=func.now()
            )
            session.add(prefix_entry)
            session.commit()
            session.refresh(prefix_entry)
            return prefix_entry.__dict__

    def get_prefix(self, prefix_id: int) -> dict:
        with get_session() as session:
            row = session.execute(
                select(NamePrefix).where(NamePrefix.prefix_id == prefix_id)
            ).scalars().first()
        if not row:
            raise HTTPException(status_code=404, detail="Name Prefix not found")
        return row.__dict__

    def update_prefix(self, prefix_id: int, payload: NamePrefixUpdate) -> dict:
        with get_session() as session:
            existing = session.execute(
                select(NamePrefix.prefix_id).where(NamePrefix.prefix_id == prefix_id)
            ).first()
            if not existing:
                raise HTTPException(status_code=404, detail="Name Prefix not found")

        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        updates["updated_at"] = func.now()

        with get_session() as session:
            session.execute(update(NamePrefix).where(NamePrefix.prefix_id == prefix_id).values(**updates))
            session.commit()

        return self.get_prefix(prefix_id)

    def delete_prefix(self, prefix_id: int) -> dict:
        with get_session() as session:
            prefix_entry = session.execute(
                select(NamePrefix).where(NamePrefix.prefix_id == prefix_id)
            ).scalars().first()
            
            if not prefix_entry:
                raise HTTPException(status_code=404, detail="Name Prefix not found")
                
            session.delete(prefix_entry)
            session.commit()
            
        return {"detail": "Name Prefix deleted successfully"}
