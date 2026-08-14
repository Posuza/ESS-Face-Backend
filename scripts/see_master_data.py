"""
Create a fresh SQLite database with all tables matching current models.
Use this to test the updated schema (shift_* columns as INT, etc.)
Run from the backEnd/ directory.
"""

import os
import sys

# Add parent dir to path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Force SQLite
os.environ["DB_ENGINE"] = "sqlite"
os.environ["SQLITE_PATH"] = "fresh_test.db"

from app.core.orm import Base

# Import ALL models so they register with Base.metadata
from app.models import (  # noqa: F401
    addresses,
    audit_logs,
    departments,
    districts,
    divisions,
    employee_permissions,
    employees,
    fields,
    mo_daily_transaction_details,
    mo_daily_transaction_project,
    mo_daily_transactions,
    mo_transaction_discipline_warning,
    name_prefixs,
    position_change_logs,
    positions,
    postal_codes,
    provinces,
    roles,
    route_change_logs,
    routes,
    shifts,
    sub_districts,
)
from sqlalchemy import create_engine

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fresh_test.db")

if __name__ == "__main__":
    # Remove old db if exists
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"  Removed existing: {DB_PATH}")

    engine = create_engine(f"sqlite:///{DB_PATH}")
    Base.metadata.create_all(bind=engine)

    # Show created tables
    from sqlalchemy import inspect

    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"\n  Created SQLite database: {DB_PATH}")
    print(f"  Tables ({len(tables)}):")
    for t in tables:
        cols = [c["name"] for c in inspector.get_columns(t)]
        print(f"    - {t}")
        print(f"      Columns: {', '.join(cols[:8])}{'...' if len(cols) > 8 else ''}")
    print("\n  Done! The schema matches current models exactly.")
