"""Create only the app_registrations table without modifying other schema."""

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

def main() -> None:
    from app.core.db.engine import engine
    from app.models.app_registrations import AppRegistration

    AppRegistration.__table__.create(bind=engine, checkfirst=True)
    print("app_registrations table is ready")


if __name__ == "__main__":
    main()
