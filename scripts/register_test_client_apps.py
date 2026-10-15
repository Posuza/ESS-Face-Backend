"""Create two local client registrations used by the browser test apps."""

import secrets
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


TEST_APPS = (
    ("ESSMO", "Tg2wbdIU3C0JRfSX", "http://127.0.0.1:4101"),
    ("ESS Report", "2Bq2BxIiUsNukyiX", "http://127.0.0.1:4102"),
)


def main() -> None:
    from app.core.shared.db.engine import SessionLocal, engine
    from app.models.sdk.auth_app_registry import AuthAppRegistry

    AuthAppRegistry.__table__.create(bind=engine, checkfirst=True)
    with SessionLocal() as db:
        for app_name, public_key, allowed_callback_origin in TEST_APPS:
            app = (
                db.query(AuthAppRegistry)
                .filter(AuthAppRegistry.app_name == app_name)
                .first()
            )
            if not app:
                app = AuthAppRegistry(
                    app_name=app_name,
                    public_key=public_key,
                    private_key=secrets.token_urlsafe(48),
                    allowed_callback_origin=allowed_callback_origin,
                )
                db.add(app)
            else:
                app.public_key = public_key
                app.allowed_callback_origin = allowed_callback_origin
                app.is_active = True
        db.commit()

    for app_name, public_key, allowed_callback_origin in TEST_APPS:
        print(f"{app_name}: {public_key} -> {allowed_callback_origin}")


if __name__ == "__main__":
    main()
