from __future__ import annotations

import contextvars
import logging
import threading
from typing import Optional

from fastapi import Request

from app.schemas.audit_logs import AuditLogCreate
from app.services.audit_logs import AuditLogService

_logger = logging.getLogger(__name__)
_service = AuditLogService()


# ─── Request context (auto-injected from middleware) ────────────────────────

_current_request: contextvars.ContextVar[Optional[Request]] = contextvars.ContextVar(
    "current_request", default=None
)
_current_user_name: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "current_user_name", default=None
)
_current_employee_code: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "current_employee_code", default=None
)


def set_audit_context(
    *, request: Request, user_name: str, employee_code: Optional[str] = None
) -> None:
    """Called by middleware to set the current audit context for this request."""
    _current_request.set(request)
    _current_user_name.set(user_name)
    _current_employee_code.set(employee_code)


def clear_audit_context() -> None:
    """Called by middleware after the request completes."""
    _current_request.set(None)
    _current_user_name.set(None)
    _current_employee_code.set(None)


# ─── Request context helpers ──────────────────────────────────────────────────


def get_client_ip(request: Request) -> str:
    """Extract the real client IP, respecting X-Forwarded-For proxies."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def get_geo_info(
    request: Request,
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Return (latitude, longitude, geo_status) from request headers.
    Frontend sends X-Latitude / X-Longitude on success, or X-Geo-Status on denial.
    """
    lat = request.headers.get("X-Latitude")
    lng = request.headers.get("X-Longitude")
    status = request.headers.get("X-Geo-Status") or None
    if lat and lng:
        return lat, lng, "available"
    return None, None, status


_UA_DEVICE_MAP = [
    ("iPad", "iPad"),
    ("iPhone", "iPhone"),
    ("Android", "Android"),
]
_UA_OS_MAP = [
    ("Windows NT", "Windows"),
    ("Macintosh", "macOS"),
    ("iPhone", "iOS"),
    ("iPad", "iOS"),
    ("Android", "Android"),
    ("Linux", "Linux"),
]


def get_device_info(request: Request) -> tuple[str, str]:
    """Return (device_name, os_name) by parsing the User-Agent header."""
    ua = request.headers.get("User-Agent", "")
    device = next((d for kw, d in _UA_DEVICE_MAP if kw in ua), "Desktop")
    os_name = next((o for kw, o in _UA_OS_MAP if kw in ua), "Unknown")
    return device, os_name


def _extract_request_context(request: Optional[Request]) -> dict:
    """
    Build a combined ip_address string: {ip}/{geo}/{device}
    Examples:
      171.6.207.133/Latitude : 13.726 Longitude : 100.595/iPhone
      49.230.145.155/User denied the request for Geolocation./Windows
      1.2.3.4/unavailable/Desktop
    Returns {"ip_address": "unknown/unavailable/Desktop"} if no request.
    """
    if request is None:
        return {"ip_address": "unknown/unavailable/Desktop"}

    ip = get_client_ip(request)
    lat, lng, geo_status = get_geo_info(request)
    device, _os = get_device_info(request)

    if lat and lng:
        geo_part = f"Latitude : {lat} Longitude : {lng}"
    elif geo_status:
        geo_part = geo_status
    else:
        geo_part = "unavailable"

    return {"ip_address": f"{ip}/{geo_part}/{device}"}


# ─── Audit wrapper ────────────────────────────────────────────────────────────


class _AuditWrapper:
    """Fire-and-forget audit writer. Context auto-resolved from middleware."""

    def log(
        self,
        *,
        action: str,
    ) -> None:
        """Write one audit entry (fire-and-forget). All context auto-resolved."""
        user_name = _current_user_name.get() or "anonymous"
        employee_code = _current_employee_code.get()
        req = _current_request.get()
        ip_address = _extract_request_context(req)["ip_address"]

        payload = AuditLogCreate(
            employee_code=employee_code,
            user_name=user_name,
            ip_address=ip_address,
            action=action,
        )

        def _worker(p: AuditLogCreate) -> None:
            try:
                _service.create(p)
            except Exception as exc:  # pragma: no cover - audit must not raise
                _logger.error(
                    "audit.log failed in background thread: %s", exc, exc_info=True
                )

        try:
            t = threading.Thread(target=_worker, args=(payload,), daemon=True)
            t.start()
        except Exception as exc:  # pragma: no cover
            _logger.error(
                "failed to start audit background thread: %s", exc, exc_info=True
            )


# ─── Singleton ────────────────────────────────────────────────────────────────
audit_logger = _AuditWrapper()
