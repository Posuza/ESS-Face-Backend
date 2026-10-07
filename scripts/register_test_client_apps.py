"""Create two local client registrations used by the browser test apps."""

import secrets
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


TEST_APPS = (
    ("ESSMO", "Tg2wbdIU3C0JRfSX"),
    ("ESS Report", "2Bq2BxIiUsNukyiX"),
)


def main() -> None:
    from app.core.db.engine import SessionLocal, engine
    from app.models.app_registrations import AppRegistration

    AppRegistration.__table__.create(bind=engine, checkfirst=True)
    with SessionLocal() as db:
        for app_name, public_key in TEST_APPS:
            app = (
                db.query(AppRegistration)
                .filter(AppRegistration.app_name == app_name)
                .first()
            )
            if not app:
                app = AppRegistration(
                    app_name=app_name,
                    public_key=public_key,
                    private_key=secrets.token_urlsafe(48),
                )
                db.add(app)
            else:
                app.public_key = public_key
                app.is_active = True
        db.commit()

    for app_name, public_key in TEST_APPS:
        print(f"{app_name}: {public_key}")


if __name__ == "__main__":
    main()
