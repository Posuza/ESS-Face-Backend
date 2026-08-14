from fastapi import HTTPException
from sqlalchemy import func, select, update

from app.core.orm import get_session
from app.models.routes import Route
from app.schemas.routes import RouteCreate, RouteUpdate


class RouteService:
    def list_routes(self) -> list[dict]:
        with get_session() as session:
            rows = session.execute(
                select(Route).order_by(Route.route_id.desc())
            ).scalars().all()
            return [row.__dict__ for row in rows]

    def create_route(self, payload: RouteCreate) -> dict:
        p = payload.model_dump()
        
        with get_session() as session:
            route_entry = Route(
                route_name=p["route_name"],
                field_id=p["field_id"],
                department_id=p["department_id"],
                division_id=p["division_id"],
                is_active=p["is_active"],
                created_by=p["created_by"],
                updated_by=p["created_by"],  # Mirror created_by on init
                created_at=func.now(),
                updated_at=func.now()
            )
            session.add(route_entry)
            session.commit()
            session.refresh(route_entry)
            return route_entry.__dict__

    def get_route(self, route_id: int) -> dict:
        with get_session() as session:
            row = session.execute(
                select(Route).where(Route.route_id == route_id)
            ).scalars().first()
        if not row:
            raise HTTPException(status_code=404, detail="Route not found")
        return row.__dict__

    def update_route(self, route_id: int, payload: RouteUpdate) -> dict:
        with get_session() as session:
            existing = session.execute(
                select(Route.route_id).where(Route.route_id == route_id)
            ).first()
            if not existing:
                raise HTTPException(status_code=404, detail="Route not found")

        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        updates["updated_at"] = func.now()

        with get_session() as session:
            session.execute(update(Route).where(Route.route_id == route_id).values(**updates))
            session.commit()

        return self.get_route(route_id)

    def delete_route(self, route_id: int) -> dict:
        with get_session() as session:
            route_entry = session.execute(
                select(Route).where(Route.route_id == route_id)
            ).scalars().first()
            
            if not route_entry:
                raise HTTPException(status_code=404, detail="Route not found")
                
            session.delete(route_entry)
            session.commit()
            
        return {"detail": "Route deleted successfully"}
