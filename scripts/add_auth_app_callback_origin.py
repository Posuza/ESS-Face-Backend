"""Add the callback-origin column to an existing auth application registry."""

import sys
from pathlib import Path

from sqlalchemy import inspect, text

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def main() -> None:
    from app.core.shared.db.engine import engine

    columns = {
        column["name"] for column in inspect(engine).get_columns("auth_app_registry")
    }
    if "allowed_callback_origin" in columns:
        print("auth_app_registry.allowed_callback_origin already exists")
        return

    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE auth_app_registry "
                "ADD COLUMN allowed_callback_origin VARCHAR(2048) NULL"
            )
        )
    print("Added auth_app_registry.allowed_callback_origin")


if __name__ == "__main__":
    main()
