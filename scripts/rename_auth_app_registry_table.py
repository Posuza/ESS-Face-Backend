"""Rename app_registrations to auth_app_registry without losing rows."""

import sys
from pathlib import Path

from sqlalchemy import inspect, text

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def main() -> None:
    from app.core.shared.db.engine import engine

    tables = set(inspect(engine).get_table_names())
    if "auth_app_registry" in tables:
        print("auth_app_registry already exists")
        return
    if "app_registrations" not in tables:
        raise RuntimeError("Neither auth_app_registry nor app_registrations exists")

    with engine.begin() as connection:
        connection.execute(
            text("ALTER TABLE app_registrations RENAME TO auth_app_registry")
        )
    print("Renamed app_registrations to auth_app_registry")


if __name__ == "__main__":
    main()
