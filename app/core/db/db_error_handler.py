from __future__ import annotations

import logging
import json

from fastapi import status
from sqlalchemy.exc import (
    DatabaseError,
    DataError,
    DBAPIError,
    IntegrityError,
    InterfaceError,
    OperationalError,
)
from sqlalchemy.exc import TimeoutError as SQLTimeoutError
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.audit_logger import audit_logger
from app.core.registries import (
    DATABASE_ERROR_CONNECTION_FAILED,
    DATABASE_ERROR_DATA_CORRUPTION,
    DATABASE_ERROR_HOST_BLOCKED,
    DATABASE_ERROR_QUERY_ERROR,
)

_logger = logging.getLogger(__name__)


class DatabaseErrorMiddleware:
    """
    Middleware to catch database errors and convert to proper HTTP responses.

    This prevents database errors from crashing the backend and provides
    consistent error responses to the frontend.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        try:
            await self.app(scope, receive, send)

        except (OperationalError, InterfaceError, DBAPIError, DatabaseError) as e:
            # Database connection errors, timeouts, host blocked
            error_msg = str(e).lower()
            _logger.exception("Database DBAPI error during request: %s", e)

            # Check if it's a timeout
            if "timeout" in error_msg or "timed out" in error_msg:
                audit_logger.log(
                    action="[DATABASE_ERROR_CONNECTION_FAILED] Database timeout during request",
                )

                await self._send_error(send, status.HTTP_503_SERVICE_UNAVAILABLE, DATABASE_ERROR_CONNECTION_FAILED)
                return

            # Check if host is blocked (MySQL error 1129)
            if "1129" in error_msg or "blocked" in error_msg:
                audit_logger.log(
                    action="[DATABASE_ERROR_HOST_BLOCKED] Host blocked by MySQL due to connection errors",
                )

                await self._send_error(send, status.HTTP_503_SERVICE_UNAVAILABLE, DATABASE_ERROR_HOST_BLOCKED)
                return

            # Generic connection error
            audit_logger.log(
                action="[DATABASE_ERROR_CONNECTION_FAILED] Database connection failed",
            )

            await self._send_error(send, status.HTTP_503_SERVICE_UNAVAILABLE, DATABASE_ERROR_CONNECTION_FAILED)
            return

        except IntegrityError as e:
            # Constraint violations (unique, foreign key, etc.)
            error_msg = str(e).lower()

            # Check if it's a duplicate entry
            if "duplicate" in error_msg or "unique" in error_msg:
                audit_logger.log(
                    action="[ER_CLIENT_2004] Duplicate entry detected",
                )

                await self._send_error(send, status.HTTP_409_CONFLICT, "Duplicate entry detected")
                return

            # Other integrity errors (foreign key, etc.)
            audit_logger.log(
                action="[DATABASE_ERROR_DATA_CORRUPTION] Data integrity violation",
            )

            await self._send_error(send, status.HTTP_500_INTERNAL_SERVER_ERROR, DATABASE_ERROR_DATA_CORRUPTION)
            return

        except DataError:
            # Query errors, data type errors
            audit_logger.log(
                action="[DATABASE_ERROR_QUERY_ERROR] Database query execution failed",
            )

            await self._send_error(send, status.HTTP_500_INTERNAL_SERVER_ERROR, DATABASE_ERROR_QUERY_ERROR)
            return

        except SQLTimeoutError:
            # Explicit timeout errors
            audit_logger.log(
                action="[DATABASE_ERROR_CONNECTION_FAILED] Database operation timeout",
            )

            await self._send_error(send, status.HTTP_503_SERVICE_UNAVAILABLE, DATABASE_ERROR_CONNECTION_FAILED)
            return

    @staticmethod
    async def _send_error(send: Send, status_code: int, detail: str) -> None:
        body = json.dumps({"detail": detail}).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": status_code,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
