"""Add creator/updater attribution to an existing auth application registry."""

import argparse
import sys
from pathlib import Path

from sqlalchemy import inspect, text

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--backfill-employee-code",
        help="Employee code to record for existing rows when their creator is known.",
    )
    args = parser.parse_args()

    from app.core.shared.db.engine import engine

    columns = {
        column["name"] for column in inspect(engine).get_columns("auth_app_registry")
    }
    with engine.begin() as connection:
        if "created_by" not in columns:
            connection.execute(
                text(
                    "ALTER TABLE auth_app_registry "
                    "ADD COLUMN created_by VARCHAR(6) NULL"
                )
            )
            print("Added auth_app_registry.created_by")
        if "updated_by" not in columns:
            connection.execute(
                text(
                    "ALTER TABLE auth_app_registry "
                    "ADD COLUMN updated_by VARCHAR(6) NULL"
                )
            )
            print("Added auth_app_registry.updated_by")

        if args.backfill_employee_code:
            employee_exists = connection.execute(
                text(
                    "SELECT 1 FROM employees "
                    "WHERE employee_code = :employee_code LIMIT 1"
                ),
                {"employee_code": args.backfill_employee_code},
            ).scalar_one_or_none()
            if employee_exists is None:
                raise SystemExit("Backfill employee code does not exist.")
            connection.execute(
                text(
                    "UPDATE auth_app_registry "
                    "SET created_by = COALESCE(created_by, :employee_code), "
                    "updated_by = COALESCE(updated_by, :employee_code)"
                ),
                {"employee_code": args.backfill_employee_code},
            )
            print(
                "Backfilled auth_app_registry attribution with "
                f"{args.backfill_employee_code}"
            )


if __name__ == "__main__":
    main()
