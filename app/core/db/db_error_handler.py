from __future__ import annotations

import logging

from fastapi import HTTPException, Request, status
from sqlalchemy.exc import (
    DatabaseError,
    DataError,
    DBAPIError,
    IntegrityError,
    InterfaceError,
    OperationalError,
)
from sqlalchemy.exc import TimeoutError as SQLTimeoutError
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.audit_logger import audit_logger
from app.core.registries import (
    DATABASE_ERROR_CONNECTION_FAILED,
    DATABASE_ERROR_DATA_CORRUPTION,
    DATABASE_ERROR_HOST_BLOCKED,
    DATABASE_ERROR_QUERY_ERROR,
)

_logger = logging.getLogger(__name__)


class DatabaseErrorMiddleware(BaseHTTPMiddleware):
    """
    Middleware to catch database errors and convert to proper HTTP responses.

    This prevents database errors from crashing the backend and provides
    consistent error responses to the frontend.
    """

    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response

        except (OperationalError, InterfaceError, DBAPIError, DatabaseError) as e:
            # Database connection errors, timeouts, host blocked
            error_msg = str(e).lower()
            _logger.exception("Database DBAPI error during request: %s", e)

            # Check if it's a timeout
            if "timeout" in error_msg or "timed out" in error_msg:
                audit_logger.log(
                    action="[DATABASE_ERROR_CONNECTION_FAILED] Database timeout during request",
                )

                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=DATABASE_ERROR_CONNECTION_FAILED,
                )

            # Check if host is blocked (MySQL error 1129)
            if "1129" in error_msg or "blocked" in error_msg:
                audit_logger.log(
                    action="[DATABASE_ERROR_HOST_BLOCKED] Host blocked by MySQL due to connection errors",
                )

                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=DATABASE_ERROR_HOST_BLOCKED,
                )

            # Generic connection error
            audit_logger.log(
                action="[DATABASE_ERROR_CONNECTION_FAILED] Database connection failed",
            )

            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=DATABASE_ERROR_CONNECTION_FAILED,
            )

        except IntegrityError as e:
            # Constraint violations (unique, foreign key, etc.)
            error_msg = str(e).lower()

            # Check if it's a duplicate entry
            if "duplicate" in error_msg or "unique" in error_msg:
                audit_logger.log(
                    action="[ER_CLIENT_2004] Duplicate entry detected",
                )

                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Duplicate entry detected",
                )

            # Other integrity errors (foreign key, etc.)
            audit_logger.log(
                action="[DATABASE_ERROR_DATA_CORRUPTION] Data integrity violation",
            )

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=DATABASE_ERROR_DATA_CORRUPTION,
            )

        except DataError:
            # Query errors, data type errors
            audit_logger.log(
                action="[DATABASE_ERROR_QUERY_ERROR] Database query execution failed",
            )

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=DATABASE_ERROR_QUERY_ERROR,
            )

        except SQLTimeoutError:
            # Explicit timeout errors
            audit_logger.log(
                action="[DATABASE_ERROR_CONNECTION_FAILED] Database operation timeout",
            )

            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=DATABASE_ERROR_CONNECTION_FAILED,
            )

        except HTTPException:
            # Re-raise HTTP exceptions (already handled)
            raise

        except Exception as e:
            # Catch any other unexpected errors
            audit_logger.log(
                action=f"[DATABASE_ERROR_QUERY_ERROR] Unexpected error: {str(e)[:100]}",
            )

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=DATABASE_ERROR_QUERY_ERROR,
            )
