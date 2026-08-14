import os
import json
import datetime
from decimal import Decimal
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy import inspect

# Ensure the app context can be imported (adjust pythonpath if run from this scripts folder)
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.db.engine import engine


EXPORT_TABLES = [
    "departments",
    "divisions",
    "employee_permissions",
    "employees",
    "fields",
    "mo_daily_transaction_details",
    "mo_daily_transaction_discipline_warnings",
    "mo_daily_transaction_projects",
    "mo_daily_transactions",
    "mo_report_export_job",
    "name_prefixs",
    "positions",
    "roles",
    "routes",
    "shifts",
]


class CustomEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle dates, datetimes, timedeltas, decimals, and bytes."""
    def default(self, obj):
        if isinstance(obj, (datetime.date, datetime.datetime)):
            return obj.isoformat()
        if isinstance(obj, datetime.timedelta):
            return str(obj)  # Format timedelta as "H:MM:SS" string
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, bytes):
            return obj.decode('utf-8', errors='ignore')
        return super().default(obj)


def export_tables():
    # Target directories
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../jsons"))
    headers_dir = os.path.join(base_dir, "headers")
    data_dir = os.path.join(base_dir, "data")
    
    os.makedirs(headers_dir, exist_ok=True)
    os.makedirs(data_dir, exist_ok=True)
    
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    try:
        # Use SQLAlchemy Inspector to get actual physical tables in the database
        inspector = inspect(engine)
        physical_tables = inspector.get_table_names()
        export_tables = [table for table in EXPORT_TABLES if table in physical_tables]
        missing_tables = [table for table in EXPORT_TABLES if table not in physical_tables]
        
        print(f"🔍 Found {len(physical_tables)} physical tables in the database.")
        print(f"📦 Exporting {len(export_tables)} configured tables.")
        if missing_tables:
            print(f"⚠️ Skipping missing tables: {', '.join(missing_tables)}")
        
        for table_name in export_tables:
            print(f"\nProcessing table: '{table_name}'...")
            
            # --- 1. Export Columns & Schema Headers directly from Database Metadata ---
            columns_info = []
            pk_constraint = inspector.get_pk_constraint(table_name)
            primary_keys = pk_constraint.get("constrained_columns", []) if pk_constraint else []
            
            for col in inspector.get_columns(table_name):
                columns_info.append({
                    "column_name": col["name"],
                    "data_type": str(col["type"]),
                    "is_primary_key": col["name"] in primary_keys,
                    "is_nullable": col["nullable"],
                    "default_value": str(col["default"]) if col["default"] is not None else None
                })
                
            header_file = os.path.join(headers_dir, f"{table_name}_headers.json")
            with open(header_file, "w", encoding="utf-8") as f:
                json.dump(columns_info, f, indent=4, ensure_ascii=False)
            print(f"  👉 Saved schema headers to '{header_file}'")
            
            # --- 2. Export Actual Row Data dynamically ---
            try:
                # Query directly from the table name using raw SQL select
                stmt = sa.text(f"SELECT * FROM `{table_name}`")
                result = session.execute(stmt)
                
                # Convert rows to dicts mapping column name to value
                rows = [dict(row._mapping) for row in result]
                
                data_file = os.path.join(data_dir, f"{table_name}_data.json")
                with open(data_file, "w", encoding="utf-8") as f:
                    json.dump(rows, f, indent=4, cls=CustomEncoder, ensure_ascii=False)
                print(f"  👉 Exported {len(rows)} data rows to '{data_file}'")
            except Exception as data_err:
                print(f"  ⚠️ Could not export data for table '{table_name}': {data_err}")
                # Write an empty array for missing/error data
                data_file = os.path.join(data_dir, f"{table_name}_data.json")
                with open(data_file, "w", encoding="utf-8") as f:
                    json.dump([], f, indent=4)
            
        print("\n🎉 Direct DB Export completed successfully!")
        print(f"📁 Schema Headers: {headers_dir}")
        print(f"📁 Table Data:    {data_dir}")
        
    except Exception as e:
        print(f"\n❌ Error during direct DB inspection/export: {e}")
    finally:
        session.close()


if __name__ == "__main__":
    export_tables()
