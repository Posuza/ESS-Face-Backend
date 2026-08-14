"""
Seed script: Load JSON data files into the database (SQLite or MySQL).

Usage:
    cd backEnd
    python scripts/seed_data.py
"""

import json
import sys
from datetime import date, datetime, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings
from app.core.db.engine import Base, SessionLocal, engine

# ── Model classes ──
from app.models.addresses import Address
from app.models.audit_logs import AuditLog
from app.models.departments import Department
from app.models.districts import District
from app.models.divisions import Division
from app.models.employee_permissions import EmployeePermission
from app.models.employees import Employee
from app.models.fields import FieldModel as Field
from app.models.mo_daily_transaction_details import MoDailyTransactionDetail1
from app.models.mo_daily_transaction_project import MoDailyTransactionProject
from app.models.mo_daily_transactions import MoDailyTransaction
from app.models.mo_transaction_discipline_warning import MoTransactionDisciplineWarning
from app.models.name_prefixs import NamePrefix
from app.models.position_change_logs import PositionChangeLog
from app.models.positions import Position
from app.models.postal_codes import PostalCode
from app.models.provinces import Province
from app.models.roles import Role
from app.models.route_change_logs import RouteChangeLog
from app.models.routes import Route
from app.models.shifts import Shift
from app.models.sub_districts import SubDistrict
from sqlalchemy import Date, DateTime, Time

# ── Insertion order (respects foreign-key dependencies) ──
SEED_ORDER = [
    (Role, "roles"),
    (NamePrefix, "name_prefixs"),
    (Field, "fields"),
    (Province, "provinces"),
    (Position, "positions"),
    (Route, "routes"),
    (Shift, "shifts"),
    (Department, "departments"),
    (District, "districts"),
    (SubDistrict, "sub_districts"),
    (PostalCode, "postal_codes"),
    (Division, "divisions"),
    (Employee, "employees"),
    (Address, "addresses"),
    (EmployeePermission, "employee_permissions"),
    (AuditLog, "audit_logs"),
    (MoDailyTransaction, "mo_daily_transactions"),
    (MoDailyTransactionDetail1, "mo_daily_transaction_details"),
    (MoDailyTransactionProject, "mo_daily_transaction_project"),
    (MoTransactionDisciplineWarning, "mo_transaction_discipline_warning"),
    (PositionChangeLog, "position_change_logs"),
    (RouteChangeLog, "route_change_logs"),
]


def _convert_row(row: dict, table) -> dict:
    """Convert string values to Python objects based on column types."""
    result = {}
    for key, val in row.items():
        if val is None:
            result[key] = None
            continue

        col = table.columns.get(key)
        if col is None:
            result[key] = val
            continue

        col_type = col.type

        if isinstance(col_type, DateTime) and isinstance(val, str):
            try:
                s = val.replace("Z", "+00:00")
                result[key] = datetime.fromisoformat(s)
            except (ValueError, TypeError):
                result[key] = val

        elif isinstance(col_type, Date) and isinstance(val, str):
            try:
                result[key] = date.fromisoformat(val[:10])
            except (ValueError, TypeError):
                result[key] = val

        elif isinstance(col_type, Time) and isinstance(val, str):
            try:
                parts = val.split(":")
                h, m = int(parts[0]), int(parts[1])
                s = int(parts[2]) if len(parts) > 2 else 0
                result[key] = time(h, m, s)
            except (ValueError, IndexError, TypeError):
                result[key] = val

        else:
            result[key] = val

    return result


def load_rows(name: str) -> list[dict]:
    """Load JSON data file and return rows."""
    path = Path(__file__).parent.parent / "jsons" / "data" / f"{name}_data.json"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def seed():
    print(f"🌱  Seeding database: {settings.DB_ENGINE}")
    print()

    # Ensure all tables exist
    Base.metadata.create_all(bind=engine)
    print("✓ Tables created/verified")
    print()

    db = SessionLocal()
    try:
        total = 0
        for model_cls, name in SEED_ORDER:
            table_name = model_cls.__tablename__
            rows = load_rows(name)

            if not rows:
                print(f"  - {table_name}: 0 rows (empty)")
                continue

            # Convert strings to proper Python types based on column types
            converted = [_convert_row(r, model_cls.__table__) for r in rows]

            # Insert rows individually, skipping any that violate constraints
            inserted = 0
            skipped = 0
            for row_data in converted:
                try:
                    db.execute(model_cls.__table__.insert(), row_data)
                    db.commit()
                    inserted += 1
                except Exception:
                    db.rollback()
                    skipped += 1

            total += inserted
            label = f"  ✓ {table_name}: {inserted} rows"
            if skipped:
                label += f" (⚠ {skipped} skipped due to missing data)"
            print(label)

        print()
        print(f"✅  Done! {total} total rows inserted.")
    except Exception as e:
        db.rollback()
        print(f"\n❌  Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
