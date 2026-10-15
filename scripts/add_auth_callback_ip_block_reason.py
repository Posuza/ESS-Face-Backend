"""Add the block reason column to the callback IP limit table."""

import sys
from pathlib import Path

from sqlalchemy import inspect, text

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def main() -> None:
    from app.core.shared.db.engine import engine

    columns = {
        column["name"]
        for column in inspect(engine).get_columns("auth_callback_ip_limits")
    }
    if "block_reason" in columns:
        print("auth_callback_ip_limits.block_reason already exists")
        return

    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE auth_callback_ip_limits "
                "ADD COLUMN block_reason VARCHAR(255) NULL"
            )
        )
    print("auth_callback_ip_limits.block_reason added")


if __name__ == "__main__":
    main()
