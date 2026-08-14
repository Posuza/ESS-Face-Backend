"""Create a safe system admin and associated shift without toggling FK checks.

Usage: python3 create_admin.py

This script runs an ALTER-based sequence (make employees.shift_id nullable,
insert admin without shift, insert shift referencing admin, update admin.shift_id,
restore NOT NULL). It is idempotent and uses your project's DB engine.
"""
import os
import sys
from datetime import datetime, date

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from sqlalchemy import text
from app.core.orm import engine


def run():
    dialect = engine.dialect.name.lower()
    if dialect not in ("mysql", "mariadb"):
        print(f"Warning: this script targets MySQL/MariaDB (detected: {dialect}). Proceeding may fail.")

    with engine.connect() as conn:
        # verify database selected
        current_db = conn.execute(text("SELECT DATABASE()")).scalar()
        if not current_db:
            print("No database selected. Please run this script when connected to the correct DB or set a default database.")
            return
        print(f"Connected to database: {current_db}")

        # find or create admin role
        admin_role = conn.execute(text("SELECT role_id FROM roles WHERE role_name = 'admin' LIMIT 1")).scalar()
        if admin_role is None:
            print("Creating 'admin' role...")
            conn.execute(text("INSERT INTO roles (role_name, created_at, created_by) VALUES ('admin', NOW(), 'SYSTEM')"))
            admin_role = conn.execute(text("SELECT role_id FROM roles WHERE role_name = 'admin' LIMIT 1")).scalar()
        print(f"admin role_id = {admin_role}")

        # helper to get or create a placeholder id for small FK tables
        def ensure_placeholder(table, col_name, value):
            q = text(f"SELECT {col_name} FROM {table} LIMIT 1")
            res = conn.execute(q).scalar()
            if res is None:
                print(f"Inserting placeholder into {table}...")
                conn.execute(text(f"INSERT INTO {table} ({col_name}, created_at, created_by) VALUES (:val, NOW(), 'SYSTEM')"), {"val": value})
                res = conn.execute(q).scalar()
            return res

        prefix_id = ensure_placeholder("name_prefixs", "prefix_id", "SYS")
        field_id = ensure_placeholder("fields", "field_id", "SYSTEM")
        department_id = ensure_placeholder("departments", "department_id", "SYSTEM")
        division_id = ensure_placeholder("divisions", "division_id", "SYSTEM")
        position_id = ensure_placeholder("positions", "position_id", "SYSTEM")

        # begin safe sequence in a transaction
        trans = conn.begin()
        try:
            print("Making employees.shift_id nullable temporarily...")
            conn.execute(text("ALTER TABLE employees MODIFY COLUMN shift_id INT NULL"))

            # insert admin without shift if not exists
            admin_code = 'ADM001'
            exists = conn.execute(text("SELECT 1 FROM employees WHERE employee_code = :code LIMIT 1"), {"code": admin_code}).scalar()
            if not exists:
                print("Inserting admin employee (shift_id=NULL)...")
                conn.execute(
                    text(
                        "INSERT INTO employees (employee_code,password,role_id,name_prefix_id,first_name,last_name,birth_date,field_id,department_id,division_id,position_id,shift_id,is_active,created_at,created_by)"
                        " VALUES (:code,:pwd,:role,:pref,:fn,:ln,:bd,:field,:dept,:div,:pos,NULL,1,NOW(),:created_by)"
                    ),
                    {
                        "code": admin_code,
                        "pwd": "adm001",
                        "role": admin_role,
                        "pref": prefix_id,
                        "fn": "Super",
                        "ln": "Admin",
                        "bd": date(1980, 1, 1),
                        "field": field_id,
                        "dept": department_id,
                        "div": division_id,
                        "pos": position_id,
                        "created_by": "SYSTEM",
                    },
                )
            else:
                print("Admin already exists; skipping insert.")

            # insert shift that references admin as created_by
            print("Inserting shift that references admin as created_by...")
            # ensure we do not duplicate shifts by name+creator
            shift_exists = conn.execute(
                text("SELECT 1 FROM shifts WHERE shift_name_en = 'System' AND created_by = :code LIMIT 1"), {"code": admin_code}
            ).scalar()
            if not shift_exists:
                conn.execute(
                    text(
                        "INSERT INTO shifts (shift_name_en, shift_name_th, start_time, end_time, crosses_midnight, break_minutes, work_minutes, is_active, effective_from, created_at, created_by)"
                        " VALUES ('System','System','00:00:00','00:00:00',0,0,480,1,CURDATE(),NOW(),:code)"
                    ),
                    {"code": admin_code},
                )
            else:
                print("Shift already exists; skipping insert.")

            # update admin to set shift_id
            print("Updating admin.shift_id to the newly created shift...")
            conn.execute(
                text(
                    "UPDATE employees SET shift_id = (SELECT shift_id FROM shifts WHERE created_by = :code ORDER BY shift_id DESC LIMIT 1) WHERE employee_code = :code"
                ),
                {"code": admin_code},
            )

            # restore NOT NULL on employees.shift_id
            print("Restoring employees.shift_id to NOT NULL...")
            conn.execute(text("ALTER TABLE employees MODIFY COLUMN shift_id INT NOT NULL"))

            trans.commit()
            print("Admin creation completed successfully.")

        except Exception as exc:
            trans.rollback()
            print("Error during admin creation, rolled back:", exc)


if __name__ == "__main__":
    run()
