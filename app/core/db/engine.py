"""Database engine — URL builder, engine, session factory, and declarative Base.

Auto-detects SQLite if MySQL is not configured or unavailable.
"""

from __future__ import annotations

import os
from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings


def _mysql_available() -> bool:
    """Check if MySQL driver is installed."""
    try:
        import pymysql  # noqa: F401
    except ImportError:
        return False
    return True


def _sqlite_path() -> str:
    """Resolve the SQLite path relative to the project root."""
    path = settings.SQLITE_PATH
    if not os.path.isabs(path):
        # engine.py is at app/core/db/ → go up 4 levels to reach backEnd/
        base = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        )
        path = os.path.join(base, path)
    return path


def _build_database_url() -> str:
    """Build a database URL from settings.

    Resolution order:
      1. DB_ENGINE=sqlite       → explicit SQLite
      2. DB_ENGINE=mysql + driver installed → MySQL
      3. Default                 → MySQL (will fail with clear error if driver missing)
    """
    engine_setting = settings.DB_ENGINE.lower()

    # Explicit SQLite
    if engine_setting == "sqlite":
        return f"sqlite:///{_sqlite_path()}"

    # Explicit MySQL — warn if driver missing
    if engine_setting == "mysql":
        if not _mysql_available():
            raise ImportError(
                "DB_ENGINE=mysql but 'pymysql' is not installed. "
                "Run: pip install pymysql\n"
                "Or set DB_ENGINE=sqlite in your .env to use the local SQLite database."
            )
        user = quote_plus(settings.DB_USER)
        password = quote_plus(settings.DB_PASSWORD)
        host = settings.DB_HOST
        port = settings.DB_PORT
        db_name = settings.DB_NAME
        return f"mysql+pymysql://{user}:{password}@{host}:{port}/{db_name}"

    # Unknown engine
    raise ValueError(
        f"Unsupported DB_ENGINE={settings.DB_ENGINE!r}. Use 'mysql' or 'sqlite'."
    )


DATABASE_URL = _build_database_url()

# SQLite doesn't support pool_pre_ping or connect_timeout
_engine_kwargs = {"future": True}
if settings.DB_ENGINE.lower() != "sqlite":
    _engine_kwargs["pool_pre_ping"] = True
    _engine_kwargs["pool_size"] = 5
    _engine_kwargs["max_overflow"] = 10
    _engine_kwargs["connect_args"] = {"connect_timeout": 3}
else:
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **_engine_kwargs)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    future=True,
)

Base = declarative_base()
