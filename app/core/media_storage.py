from __future__ import annotations

import re
from pathlib import Path

from app.core.config import settings


BACKEND_ROOT = Path(__file__).resolve().parents[2]
_FACE_IMAGE_FILENAME = re.compile(r"^[A-Za-z0-9_-]+\.(?:jpg|jpeg)$")
FACE_IMAGE_PREFIX = "employee-faces"


def media_storage_root() -> Path:
    configured = Path(settings.MEDIA_STORAGE_PATH).expanduser()
    if not configured.is_absolute():
        configured = BACKEND_ROOT / configured
    return configured.resolve()


def normalize_face_image_key(stored_value: str) -> str:
    """Return an environment-independent key from current or legacy data."""
    filename = Path(stored_value.strip()).name
    if not filename or not _FACE_IMAGE_FILENAME.fullmatch(filename):
        raise ValueError("Invalid stored face image filename")
    return f"{FACE_IMAGE_PREFIX}/{filename}"


def face_image_key(employee_code: str) -> str:
    safe_code = re.sub(r"[^A-Za-z0-9_-]", "_", employee_code.strip())
    if not safe_code:
        raise ValueError("Employee code cannot produce a safe image filename")
    return f"{FACE_IMAGE_PREFIX}/{safe_code}.jpeg"


def resolve_face_image_path(stored_value: str) -> Path:
    root = media_storage_root()
    image_key = normalize_face_image_key(stored_value)
    filename = Path(image_key).name
    image_path = (
        root / filename
        if root.name == FACE_IMAGE_PREFIX
        else root / image_key
    ).resolve()
    try:
        image_path.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            "Face image path escapes the media storage directory"
        ) from exc
    expected_parent = root if root.name == FACE_IMAGE_PREFIX else root / FACE_IMAGE_PREFIX
    if image_path.parent != expected_parent:
        raise ValueError("Face image path escapes the media storage directory")
    return image_path
