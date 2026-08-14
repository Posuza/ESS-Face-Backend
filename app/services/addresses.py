from fastapi import HTTPException
from sqlalchemy import func, select, update

from app.core.orm import get_session
from app.models.addresses import Address
from app.schemas.addresses import AddressCreate, AddressUpdate


class AddressService:
    def list_addresses(self) -> list[dict]:
        with get_session() as session:
            rows = session.execute(
                select(Address).order_by(Address.address_id.desc())
            ).scalars().all()
            return [row.__dict__ for row in rows]

    def create_address(self, payload: AddressCreate) -> dict:
        p = payload.model_dump()
        
        with get_session() as session:
            address_entry = Address(
                address_detail=p["address_detail"],
                sub_district_id=p["sub_district_id"],
                district_id=p["district_id"],
                province_id=p["province_id"],
                postal_code_id=p["postal_code_id"],
                is_active=p["is_active"],
                created_by=p["created_by"],
                updated_by=p["created_by"],
                created_at=func.now(),
                updated_at=func.now()
            )
            session.add(address_entry)
            session.commit()
            session.refresh(address_entry)
            return address_entry.__dict__

    def get_address(self, address_id: int) -> dict:
        with get_session() as session:
            row = session.execute(
                select(Address).where(Address.address_id == address_id)
            ).scalars().first()
        if not row:
            raise HTTPException(status_code=404, detail="Address not found")
        return row.__dict__

    def update_address(self, address_id: int, payload: AddressUpdate) -> dict:
        with get_session() as session:
            existing = session.execute(
                select(Address.address_id).where(Address.address_id == address_id)
            ).first()
            if not existing:
                raise HTTPException(status_code=404, detail="Address not found")

        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        updates["updated_at"] = func.now()

        with get_session() as session:
            session.execute(update(Address).where(Address.address_id == address_id).values(**updates))
            session.commit()

        return self.get_address(address_id)

    def delete_address(self, address_id: int) -> dict:
        with get_session() as session:
            address_entry = session.execute(
                select(Address).where(Address.address_id == address_id)
            ).scalars().first()
            
            if not address_entry:
                raise HTTPException(status_code=404, detail="Address not found")
                
            session.delete(address_entry)
            session.commit()
            
        return {"detail": "Address deleted successfully"}
