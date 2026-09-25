from __future__ import annotations

import json
import logging

from fastapi import status
from sqlalchemy.exc import (
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
            _logger.exception("Database pool timeout during request")
            await self._send_error(
                send,
                status.HTTP_503_SERVICE_UNAVAILABLE,
                DATABASE_ERROR_CONNECTION_FAILED,
            )
            return

        except (OperationalError, InterfaceError) as e:
            await self._handle_connection_error(send, e)
            return

        except DBAPIError as e:
            if e.connection_invalidated:
                await self._handle_connection_error(send, e)
                return

            _logger.exception("Database DBAPI query error during request: %s", e)
            await self._send_error(
                send,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                DATABASE_ERROR_QUERY_ERROR,
            )
            return

    @classmethod
    async def _handle_connection_error(cls, send: Send, error: Exception) -> None:
        error_msg = str(error).lower()
        _logger.exception("Database connection error during request: %s", error)

        # A database-backed audit entry here would create another failing
        # connection and amplify the outage.
        if "1129" in error_msg or "blocked" in error_msg:
            detail = DATABASE_ERROR_HOST_BLOCKED
        else:
            detail = DATABASE_ERROR_CONNECTION_FAILED

        await cls._send_error(send, status.HTTP_503_SERVICE_UNAVAILABLE, detail)

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
