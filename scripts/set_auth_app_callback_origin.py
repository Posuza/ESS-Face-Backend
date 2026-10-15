"""Set the exact allowed callback origin for one registered client app."""

import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def main() -> None:
    from app.core.sdk.security.callback_origin import (
        InvalidCallbackUrl,
        normalize_allowed_origin,
    )
    from app.core.shared.db.engine import SessionLocal
    from app.models.sdk.auth_app_registry import AuthAppRegistry

    parser = argparse.ArgumentParser()
    parser.add_argument("public_key", help="16-character client public key")
    parser.add_argument("origin", help="Exact HTTPS origin, without a path")
    args = parser.parse_args()

    try:
        origin = normalize_allowed_origin(args.origin)
    except InvalidCallbackUrl as exc:
        parser.error(str(exc))

    with SessionLocal() as db:
        app = (
            db.query(AuthAppRegistry)
            .filter(AuthAppRegistry.public_key == args.public_key.strip())
            .first()
        )
        if not app:
            parser.error("No client application has that public key.")
        app.allowed_callback_origin = origin
        db.commit()
        print(f"{app.app_name}: {app.public_key} -> {origin}")


if __name__ == "__main__":
    main()
