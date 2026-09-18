from __future__ import annotations

import copy
import json
import math
import threading
import uuid
from pathlib import Path
from typing import Any

from fastapi import HTTPException


BACKEND_ROOT = Path(__file__).resolve().parents[2]
CONFIG_ROOT = BACKEND_ROOT / "ai" / "config"
REGISTER_MODEL_SETTINGS_PATH = CONFIG_ROOT / "register_model_setting.json"
VERIFICATION_MODEL_SETTINGS_PATH = CONFIG_ROOT / "verification_model_setting.json"
GROUPS = {"backend_models", "frontend_models"}
MODE_PATHS = {
    "register": REGISTER_MODEL_SETTINGS_PATH,
    "verify": VERIFICATION_MODEL_SETTINGS_PATH,
}
REQUIRED_MODELS_BY_MODE = {
    "register": {"scrfd_detector", "arcface_recognizer", "face_landmarker"},
    "verify": {"scrfd_detector", "arcface_recognizer", "face_detector", "face_landmarker"},
}
FIXED_SETTINGS = {("frontend_models", "minifasnet_v2", "required_samples")}
_lock = threading.RLock()


def _mode_path(mode: str | None) -> Path:
    if mode is None:
        raise HTTPException(status_code=422, detail="Model settings mode is required")
    if mode not in MODE_PATHS:
        raise HTTPException(status_code=404, detail="Unknown model settings mode")
    return MODE_PATHS[mode]


def _mode_name(mode: str | None) -> str:
    _mode_path(mode)
    return str(mode)


def _read_group_file(group: str, mode: str | None = None) -> list[dict[str, Any]]:
    if group not in GROUPS:
        raise HTTPException(status_code=404, detail="Unknown model group")
    path = _mode_path(mode)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Unable to load {path.name}") from exc
    schemas = data.get("model_schemas")
    if not isinstance(schemas, dict) or not isinstance(schemas.get(group), list):
        raise RuntimeError(f"Invalid model settings file: {path.name}")
    return schemas[group]


def _read_files(mode: str | None = None) -> dict[str, Any]:
    data = {
        "model_schemas": {
            "backend_models": copy.deepcopy(_read_group_file("backend_models", mode)),
            "frontend_models": copy.deepcopy(_read_group_file("frontend_models", mode)),
        }
    }
    _validate_document(data, mode)
    return data


def _models(data: dict[str, Any], group: str) -> list[dict[str, Any]]:
    if group not in GROUPS:
        raise HTTPException(status_code=404, detail="Unknown model group")
    return data["model_schemas"][group]


def _find_model(data: dict[str, Any], group: str, model_key: str) -> dict[str, Any]:
    model = next((item for item in _models(data, group) if item["model_key"] == model_key), None)
    if model is None:
        raise HTTPException(status_code=404, detail="Unknown model")
    return model


def _validate_document(data: dict[str, Any], mode: str | None = None) -> None:
    schemas = data.get("model_schemas")
    if not isinstance(schemas, dict):
        raise ValueError("model_schemas must be an object")
    seen_ids: set[int] = set()
    seen_keys: set[str] = set()
    for group in GROUPS:
        models = schemas.get(group)
        if not isinstance(models, list):
            raise ValueError(f"{group} must be a list")
        for model in models:
            if not isinstance(model, dict):
                raise ValueError("model entry must be an object")
            model_id = model.get("id")
            model_key = model.get("model_key")
            if not isinstance(model_id, int) or model_id in seen_ids:
                raise ValueError("model ids must be unique integers")
            if not isinstance(model_key, str) or not model_key or model_key in seen_keys:
                raise ValueError("model keys must be unique strings")
            seen_ids.add(model_id)
            seen_keys.add(model_key)
            if not isinstance(model.get("active"), bool):
                raise ValueError("active must be boolean")
            if not isinstance(model.get("default_active"), bool):
                raise ValueError("default_active must be boolean")
            settings = model.get("settings_values")
            if not isinstance(settings, dict):
                raise ValueError("settings_values must be an object")
            for setting in settings.values():
                if not isinstance(setting, dict):
                    raise ValueError("setting metadata must be an object")
                for key in ("value", "default", "min", "max", "step"):
                    if not isinstance(setting.get(key), (int, float)):
                        raise ValueError(f"setting {key} must be numeric")
                if setting["min"] > setting["max"] or setting["step"] <= 0:
                    raise ValueError("invalid setting range")
                if not setting["min"] <= setting["value"] <= setting["max"]:
                    raise ValueError("setting value is outside its range")

    compliance = [
        model
        for model in schemas["frontend_models"]
        if model.get("model_role") == "face_compliance" and model.get("active")
    ]
    if len(compliance) > 1:
        raise ValueError("only one frontend compliance model can be active")
    default_compliance = [
        model
        for model in schemas["frontend_models"]
        if model.get("model_role") == "face_compliance" and model.get("default_active")
    ]
    if len(default_compliance) > 1:
        raise ValueError("only one frontend compliance model can be active by default")

    for required in REQUIRED_MODELS_BY_MODE[_mode_name(mode)]:
        model = next(
            (item for group in GROUPS for item in schemas[group] if item["model_key"] == required),
            None,
        )
        if model is None or not model["active"]:
            raise ValueError(f"required model {required} must be active")
        if not model["default_active"]:
            raise ValueError(f"required model {required} must be active by default")


def get_model_settings(mode: str | None = None) -> dict[str, Any]:
    with _lock:
        data = _read_files(mode)
        return copy.deepcopy(data)


def get_frontend_model_settings(mode: str | None = None) -> dict[str, Any]:
    with _lock:
        data = _read_files(mode)
        return {"frontend_models": copy.deepcopy(data["model_schemas"]["frontend_models"])}


def get_model_value(
    group: str,
    model_key: str,
    setting_key: str,
    fallback: float | int,
    mode: str | None = None,
) -> float | int:
    with _lock:
        try:
            data = _read_files(mode)
            return _find_model(data, group, model_key)["settings_values"][setting_key]["value"]
        except (HTTPException, KeyError, TypeError):
            return fallback


def is_model_active(
    group: str,
    model_key: str,
    fallback: bool = True,
    mode: str | None = None,
) -> bool:
    with _lock:
        try:
            data = _read_files(mode)
            return bool(_find_model(data, group, model_key)["active"])
        except HTTPException:
            return fallback


def _matches_step(value: float, minimum: float, step: float) -> bool:
    quotient = (value - minimum) / step
    return math.isclose(quotient, round(quotient), abs_tol=1e-8)


def _requires_integer_value(metadata: dict[str, Any]) -> bool:
    return all(
        isinstance(metadata[key], int) and not isinstance(metadata[key], bool)
        for key in ("default", "min", "max", "step")
    )


def _write_mode_locked(data: dict[str, Any], mode: str) -> None:
    path = MODE_PATHS[mode]
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(data, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def update_model_settings(
    group: str,
    model_key: str,
    *,
    active: bool | None,
    values: dict[str, float | int],
    mode: str | None = None,
) -> dict[str, Any]:
    with _lock:
        updated = _read_files(mode)
        model = _find_model(updated, group, model_key)
        if active is not None:
            if model_key in REQUIRED_MODELS_BY_MODE[_mode_name(mode)] and not active:
                raise HTTPException(status_code=422, detail="This model is required and cannot be disabled")
            if active and group == "frontend_models" and model.get("model_role") == "face_compliance":
                for candidate in _models(updated, group):
                    if candidate.get("model_role") == "face_compliance":
                        candidate["active"] = candidate["model_key"] == model_key
            else:
                model["active"] = active

        for key, value in values.items():
            metadata = model["settings_values"].get(key)
            if metadata is None:
                raise HTTPException(status_code=422, detail=f"Unknown setting: {key}")
            if (group, model_key, key) in FIXED_SETTINGS and value != metadata["value"]:
                raise HTTPException(status_code=422, detail=f"{key} is fixed and cannot be changed")
            if _requires_integer_value(metadata):
                if not isinstance(value, int) or isinstance(value, bool):
                    raise HTTPException(status_code=422, detail=f"{key} must be an integer")
            numeric = float(value)
            if numeric < metadata["min"] or numeric > metadata["max"]:
                raise HTTPException(status_code=422, detail=f"{key} is outside its allowed range")
            if not _matches_step(numeric, float(metadata["min"]), float(metadata["step"])):
                raise HTTPException(status_code=422, detail=f"{key} does not match the allowed step")
            metadata["value"] = value

        try:
            _validate_document(updated, mode)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        _write_mode_locked(updated, _mode_name(mode))
        return copy.deepcopy(model)


def reset_model_settings(
    group: str | None = None,
    model_key: str | None = None,
    mode: str | None = None,
) -> dict[str, Any]:
    with _lock:
        updated = _read_files(mode)
        groups = [group] if group else sorted(GROUPS)
        for current_group in groups:
            for model in _models(updated, current_group):
                if model_key is not None and model["model_key"] != model_key:
                    continue
                model["active"] = model["default_active"]
                for metadata in model["settings_values"].values():
                    metadata["value"] = metadata["default"]
            if model_key is not None:
                reset_model = _find_model(updated, current_group, model_key)
                if reset_model.get("model_role") == "face_compliance":
                    default_compliance = next(
                        (
                            candidate
                            for candidate in _models(updated, current_group)
                            if candidate.get("model_role") == "face_compliance"
                            and candidate.get("default_active")
                        ),
                        None,
                    )
                    for candidate in _models(updated, current_group):
                        if candidate.get("model_role") == "face_compliance":
                            candidate["active"] = candidate is default_compliance

        _validate_document(updated, mode)
        _write_mode_locked(updated, _mode_name(mode))
        return copy.deepcopy(updated)
