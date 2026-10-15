"""Create the shared callback IP failure/block table."""

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def main() -> None:
    from app.core.shared.db.engine import engine
    from app.models.sdk.auth_callback_ip_limit import AuthCallbackIpLimit

    AuthCallbackIpLimit.__table__.create(bind=engine, checkfirst=True)
    print("auth_callback_ip_limits table is ready")


if __name__ == "__main__":
    main()
