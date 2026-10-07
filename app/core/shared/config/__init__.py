"""Application configuration package."""

from app.core.shared.config.settings import BACKEND_ROOT, ENV_FILE, Settings, get_settings, settings

__all__ = [
    "BACKEND_ROOT",
    "ENV_FILE",
    "Settings",
    "get_settings",
    "settings",
]
