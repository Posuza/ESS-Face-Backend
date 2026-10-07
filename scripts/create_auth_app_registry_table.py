"""Create only the auth_app_registry table without modifying other schema."""

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def main() -> None:
    from app.core.shared.db.engine import engine
    from app.models.sdk.auth_app_registry import AuthAppRegistry

    AuthAppRegistry.__table__.create(bind=engine, checkfirst=True)
    print("auth_app_registry table is ready")


if __name__ == "__main__":
    main()
