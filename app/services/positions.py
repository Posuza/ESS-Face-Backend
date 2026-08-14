from fastapi import HTTPException
from sqlalchemy import func, select, update

from app.core.orm import get_session
from app.models.positions import Position
from app.schemas.positions import PositionCreate, PositionUpdate


class PositionService:
    def list_positions(self) -> list[dict]:
        with get_session() as session:
            rows = session.execute(
                select(Position).order_by(Position.position_id.desc())
            ).scalars().all()
            return [row.__dict__ for row in rows]

    def create_position(self, payload: PositionCreate) -> dict:
        p = payload.model_dump()
        
        with get_session() as session:
            position_entry = Position(
                position_name=p["position_name"],
                is_active=p["is_active"],
                position_detail=p.get("position_detail"),
                created_by=p["created_by"],
                updated_by=p["created_by"],  # Mirror created_by on init
                created_at=func.now(),
                updated_at=func.now()
            )
            session.add(position_entry)
            session.commit()
            session.refresh(position_entry)
            return position_entry.__dict__

    def get_position(self, position_id: int) -> dict:
        with get_session() as session:
            row = session.execute(
                select(Position).where(Position.position_id == position_id)
            ).scalars().first()
        if not row:
            raise HTTPException(status_code=404, detail="Position not found")
        return row.__dict__

    def update_position(self, position_id: int, payload: PositionUpdate) -> dict:
        with get_session() as session:
            existing = session.execute(
                select(Position.position_id).where(Position.position_id == position_id)
            ).first()
            if not existing:
                raise HTTPException(status_code=404, detail="Position not found")

        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        updates["updated_at"] = func.now()

        with get_session() as session:
            session.execute(update(Position).where(Position.position_id == position_id).values(**updates))
            session.commit()

        return self.get_position(position_id)

    def delete_position(self, position_id: int) -> dict:
        with get_session() as session:
            position_entry = session.execute(
                select(Position).where(Position.position_id == position_id)
            ).scalars().first()
            
            if not position_entry:
                raise HTTPException(status_code=404, detail="Position not found")
                
            session.delete(position_entry)
            session.commit()
            
        return {"detail": "Position deleted successfully"}
