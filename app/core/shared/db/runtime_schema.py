"""Create runtime-owned database tables that may be absent after upgrades."""

from __future__ import annotations

import logging

from app.core.shared.db.engine import engine
from app.models.sdk.auth_app_registry import AuthAppRegistry
from app.models.sdk.auth_callback_ip_limit import AuthCallbackIpLimit

_logger = logging.getLogger(__name__)


def ensure_runtime_schema() -> None:
    """Create missing SDK authentication tables without modifying existing data."""
    for table in (
        AuthAppRegistry.__table__,
        AuthCallbackIpLimit.__table__,
    ):
        table.create(bind=engine, checkfirst=True)
        _logger.info("Database table is ready: %s", table.name)
