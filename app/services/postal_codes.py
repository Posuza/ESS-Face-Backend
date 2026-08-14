from fastapi import HTTPException
from sqlalchemy import func, select, update

from app.core.orm import get_session
from app.models.postal_codes import PostalCode
from app.schemas.postal_codes import PostalCodeCreate, PostalCodeUpdate


class PostalCodeService:
    def list_postal_codes(self) -> list[dict]:
        with get_session() as session:
            rows = session.execute(
                select(PostalCode).order_by(PostalCode.postal_code_id.desc())
            ).scalars().all()
            return [row.__dict__ for row in rows]

    def create_postal_code(self, payload: PostalCodeCreate) -> dict:
        p = payload.model_dump()
        
        with get_session() as session:
            postal_code_entry = PostalCode(
                postal_code=p["postal_code"],
                sub_district_id=p["sub_district_id"],
                created_by=p["created_by"],
                updated_by=p["created_by"],
                created_at=func.now(),
                updated_at=func.now()
            )
            session.add(postal_code_entry)
            session.commit()
            session.refresh(postal_code_entry)
            return postal_code_entry.__dict__

    def get_postal_code(self, postal_code_id: int) -> dict:
        with get_session() as session:
            row = session.execute(
                select(PostalCode).where(PostalCode.postal_code_id == postal_code_id)
            ).scalars().first()
        if not row:
            raise HTTPException(status_code=404, detail="Postal Code not found")
        return row.__dict__

    def update_postal_code(self, postal_code_id: int, payload: PostalCodeUpdate) -> dict:
        with get_session() as session:
            existing = session.execute(
                select(PostalCode.postal_code_id).where(PostalCode.postal_code_id == postal_code_id)
            ).first()
            if not existing:
                raise HTTPException(status_code=404, detail="Postal Code not found")

        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        updates["updated_at"] = func.now()

        with get_session() as session:
            session.execute(update(PostalCode).where(PostalCode.postal_code_id == postal_code_id).values(**updates))
            session.commit()

        return self.get_postal_code(postal_code_id)

    def delete_postal_code(self, postal_code_id: int) -> dict:
        with get_session() as session:
            postal_code_entry = session.execute(
                select(PostalCode).where(PostalCode.postal_code_id == postal_code_id)
            ).scalars().first()
            
            if not postal_code_entry:
                raise HTTPException(status_code=404, detail="Postal Code not found")
                
            session.delete(postal_code_entry)
            session.commit()
            
        return {"detail": "Postal Code deleted successfully"}
