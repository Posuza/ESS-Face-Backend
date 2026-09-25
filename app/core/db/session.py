"""Database sessions — get_db dependency and get_session context manager."""

from __future__ import annotations

import logging
from contextlib import contextmanager

from fastapi import HTTPException, status
from sqlalchemy.exc import (
    IntegrityError,
    InterfaceError,
    OperationalError,
)
from sqlalchemy.exc import TimeoutError as SQLTimeoutError
from sqlalchemy.orm import Session

from app.core.db.engine import SessionLocal
from app.core.registries import (
    DATABASE_ERROR_CONNECTION_FAILED,
    DATABASE_ERROR_HOST_BLOCKED,
)

_logger = logging.getLogger(__name__)


def _raise_db_error(error_msg: str = "") -> None:
    """Map a DB connection error to the correct message and raise HTTPException.

    NOTE: IntegrityError is NOT handled here — it is caught separately in
    get_session/get_db so it can propagate to the middleware as-is.
    """
    msg_lower = error_msg.lower()
    if "1129" in msg_lower or "blocked" in msg_lower:
        detail = DATABASE_ERROR_HOST_BLOCKED
    else:
        detail = DATABASE_ERROR_CONNECTION_FAILED

    _logger.error("Database session error mapped to 503: %s", error_msg)

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=detail,
    )


def get_db():
    """FastAPI dependency for database session."""
    try:
        db = SessionLocal()
    except (OperationalError, InterfaceError, SQLTimeoutError) as e:
        _raise_db_error(str(e))

    try:
        yield db
    except IntegrityError:
        db.rollback()
        raise
    except (OperationalError, InterfaceError, SQLTimeoutError) as e:
        _raise_db_error(str(e))
    finally:
        db.close()


@contextmanager
def get_session() -> Session:
    """Get a SQLAlchemy session with automatic cleanup."""
    try:
        session = SessionLocal()
    except (OperationalError, InterfaceError, SQLTimeoutError) as e:
        _raise_db_error(str(e))

    try:
        yield session
    except IntegrityError:
        session.rollback()
        raise
    except (OperationalError, InterfaceError, SQLTimeoutError) as e:
        _raise_db_error(str(e))
    finally:
        session.close()
