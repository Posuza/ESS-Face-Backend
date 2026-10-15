from __future__ import annotations

import json
import threading
import uuid
from pathlib import Path

from app.core.shared.config.settings import BACKEND_ROOT


_SETTINGS_PATH = BACKEND_ROOT / "ai" / "model_settings" / "presence_setting.json"


class PresenceSettingsService:
    """Persistent, central control for optional SDK presence telemetry."""

    def __init__(self) -> None:
        self._lock = threading.RLock()

    def get(self) -> dict[str, bool]:
        with self._lock:
            try:
                payload = json.loads(_SETTINGS_PATH.read_text(encoding="utf-8"))
                enabled = payload.get("enabled")
                if isinstance(enabled, bool):
                    return {"enabled": enabled}
            except (OSError, json.JSONDecodeError):
                pass
            return {"enabled": False}

    def update(self, enabled: bool) -> dict[str, bool]:
        with self._lock:
            _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
            temporary = _SETTINGS_PATH.with_name(
                f".{_SETTINGS_PATH.name}.{uuid.uuid4().hex}.tmp"
            )
            try:
                temporary.write_text(
                    json.dumps({"enabled": enabled}, ensure_ascii=True, indent=2) + "\n",
                    encoding="utf-8",
                )
                temporary.replace(_SETTINGS_PATH)
            finally:
                temporary.unlink(missing_ok=True)
            return {"enabled": enabled}


presence_settings_service = PresenceSettingsService()
