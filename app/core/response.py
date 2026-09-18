"""Compatibility helpers for service-layer HTTP errors."""

from fastapi import HTTPException, status

from app.core.registries.client_message import (
    CLIENT_ERROR_BAD_REQUEST,
    CLIENT_ERROR_NOT_FOUND,
)


_ERRORS: dict[str, tuple[int, str]] = {
    "CLIENT.ER_CLIENT_2001": (status.HTTP_400_BAD_REQUEST, CLIENT_ERROR_BAD_REQUEST),
    "CLIENT.ER_CLIENT_2002": (status.HTTP_404_NOT_FOUND, CLIENT_ERROR_NOT_FOUND),
    "CLIENT.ER_CLIENT_2004": (
        status.HTTP_409_CONFLICT,
        "The requested resource already exists. Please contact GutsEssCenter",
    ),
}


def error(code: str) -> HTTPException:
    """Build the legacy HTTP error expected by master-data services."""

    status_code, message = _ERRORS.get(
        code,
        (status.HTTP_400_BAD_REQUEST, CLIENT_ERROR_BAD_REQUEST),
    )
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
    )
