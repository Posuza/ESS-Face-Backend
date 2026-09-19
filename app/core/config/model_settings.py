from __future__ import annotations

import copy
import json
import threading
from pathlib import Path
from typing import Any

from fastapi import HTTPException


BACKEND_ROOT = Path(__file__).resolve().parents[3]
CONFIG_ROOT = BACKEND_ROOT / "ai" / "model_settings"
FACE_MODEL_ROOT = BACKEND_ROOT / "ai" / "models" / "face"
MODEL_MANIFEST_PATH = FACE_MODEL_ROOT / "model_manifest.json"
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
model_settings_lock = threading.RLock()


def read_manifest() -> dict[str, Any]:
    try:
        data = json.loads(MODEL_MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Unable to load {MODEL_MANIFEST_PATH.name}") from exc
    backend_models = data.get("backend_models")
    if not isinstance(backend_models, dict):
        raise RuntimeError(f"Invalid model manifest file: {MODEL_MANIFEST_PATH.name}")
    return data


def mode_path(mode: str | None) -> Path:
    if mode is None:
        raise HTTPException(status_code=422, detail="Model settings mode is required")
    if mode not in MODE_PATHS:
        raise HTTPException(status_code=404, detail="Unknown model settings mode")
    return MODE_PATHS[mode]


def mode_name(mode: str | None) -> str:
    mode_path(mode)
    return str(mode)


def read_group_settings(group: str, mode: str | None = None) -> list[dict[str, Any]]:
    if group not in GROUPS:
        raise HTTPException(status_code=404, detail="Unknown model group")
    path = mode_path(mode)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Unable to load {path.name}") from exc
    schemas = data.get("model_schemas")
    if not isinstance(schemas, dict) or not isinstance(schemas.get(group), list):
        raise RuntimeError(f"Invalid model settings file: {path.name}")
    return schemas[group]


def models(data: dict[str, Any], group: str) -> list[dict[str, Any]]:
    if group not in GROUPS:
        raise HTTPException(status_code=404, detail="Unknown model group")
    return data["model_schemas"][group]


def find_model(data: dict[str, Any], group: str, model_key: str) -> dict[str, Any]:
    model = next((item for item in models(data, group) if item["model_key"] == model_key), None)
    if model is None:
        raise HTTPException(status_code=404, detail="Unknown model")
    return model


def validate_model_settings_document(data: dict[str, Any], mode: str | None = None) -> None:
    schemas = data.get("model_schemas")
    if not isinstance(schemas, dict):
        raise ValueError("model_schemas must be an object")
    seen_ids: set[int] = set()
    seen_keys: set[str] = set()
    for group in GROUPS:
        group_models = schemas.get(group)
        if not isinstance(group_models, list):
            raise ValueError(f"{group} must be a list")
        for model in group_models:
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

    for required in REQUIRED_MODELS_BY_MODE[mode_name(mode)]:
        model = next(
            (item for group in GROUPS for item in schemas[group] if item["model_key"] == required),
            None,
        )
        if model is None or not model["active"]:
            raise ValueError(f"required model {required} must be active")
        if not model["default_active"]:
            raise ValueError(f"required model {required} must be active by default")


def read_model_settings_document(mode: str | None = None) -> dict[str, Any]:
    data = {
        "model_schemas": {
            "backend_models": copy.deepcopy(read_group_settings("backend_models", mode)),
            "frontend_models": copy.deepcopy(read_group_settings("frontend_models", mode)),
        }
    }
    validate_model_settings_document(data, mode)
    return data


def get_required_model_value(
    group: str,
    model_key: str,
    setting_key: str,
    mode: str | None = None,
) -> float | int:
    with model_settings_lock:
        try:
            data = read_model_settings_document(mode)
            return find_model(data, group, model_key)["settings_values"][setting_key]["value"]
        except (HTTPException, KeyError, TypeError) as exc:
            raise RuntimeError(
                f"Missing model setting: {group}.{model_key}.{setting_key}"
            ) from exc


def get_required_model_metadata(
    group: str,
    model_key: str,
    metadata_key: str,
) -> Any:
    with model_settings_lock:
        try:
            return read_manifest()[group][model_key][metadata_key]
        except KeyError as exc:
            raise RuntimeError(
                f"Missing model metadata: {group}.{model_key}.{metadata_key}"
            ) from exc


def get_backend_model_path(model_key: str) -> Path:
    model_file = get_required_model_metadata(
        "backend_models", model_key, "model_file"
    )
    if not isinstance(model_file, str) or not model_file:
        raise RuntimeError(f"Invalid model file metadata: {model_key}.model_file")
    return FACE_MODEL_ROOT / model_file


def get_backend_model_input_size(model_key: str) -> int:
    input_size = get_required_model_metadata(
        "backend_models", model_key, "input_size"
    )
    if not isinstance(input_size, int) or isinstance(input_size, bool):
        raise RuntimeError(f"Invalid model input metadata: {model_key}.input_size")
    return input_size


def is_model_active(
    group: str,
    model_key: str,
    fallback: bool = True,
    mode: str | None = None,
) -> bool:
    with model_settings_lock:
        try:
            data = read_model_settings_document(mode)
            return bool(find_model(data, group, model_key)["active"])
        except HTTPException:
            return fallback
