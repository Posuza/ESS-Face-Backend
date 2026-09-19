from __future__ import annotations

import copy
import json
import math
import uuid
from typing import Any

from fastapi import HTTPException

from app.core.audit_logger import audit_logger
from app.core.config.model_settings import (
    FIXED_SETTINGS,
    GROUPS,
    MODE_PATHS,
    REQUIRED_MODELS_BY_MODE,
    find_model,
    mode_name,
    model_settings_lock,
    models,
    read_model_settings_document,
    validate_model_settings_document,
)
from app.core.registries import (
    MODEL_SETTINGS_ERROR_FIXED_SETTING,
    MODEL_SETTINGS_ERROR_INTEGER_SETTING,
    MODEL_SETTINGS_ERROR_RANGE_SETTING,
    MODEL_SETTINGS_ERROR_REQUIRED_MODEL,
    MODEL_SETTINGS_ERROR_STEP_SETTING,
    MODEL_SETTINGS_ERROR_UNKNOWN_SETTING,
    MODEL_SETTINGS_RESET_SUCCESS,
    MODEL_SETTINGS_UPDATE_SUCCESS,
)


def get_model_settings(mode: str | None = None) -> dict[str, Any]:
    with model_settings_lock:
        return copy.deepcopy(read_model_settings_document(mode))


def get_frontend_model_settings(mode: str | None = None) -> dict[str, Any]:
    with model_settings_lock:
        data = read_model_settings_document(mode)
        return {"frontend_models": copy.deepcopy(data["model_schemas"]["frontend_models"])}


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
    with model_settings_lock:
        updated = read_model_settings_document(mode)
        model = find_model(updated, group, model_key)
        if active is not None:
            if model_key in REQUIRED_MODELS_BY_MODE[mode_name(mode)] and not active:
                raise HTTPException(status_code=422, detail=MODEL_SETTINGS_ERROR_REQUIRED_MODEL)
            if active and group == "frontend_models" and model.get("model_role") == "face_compliance":
                for candidate in models(updated, group):
                    if candidate.get("model_role") == "face_compliance":
                        candidate["active"] = candidate["model_key"] == model_key
            else:
                model["active"] = active

        for key, value in values.items():
            metadata = model["settings_values"].get(key)
            if metadata is None:
                raise HTTPException(
                    status_code=422,
                    detail=MODEL_SETTINGS_ERROR_UNKNOWN_SETTING.format(setting_key=key),
                )
            if (group, model_key, key) in FIXED_SETTINGS and value != metadata["value"]:
                raise HTTPException(
                    status_code=422,
                    detail=MODEL_SETTINGS_ERROR_FIXED_SETTING.format(setting_key=key),
                )
            if _requires_integer_value(metadata):
                if not isinstance(value, int) or isinstance(value, bool):
                    raise HTTPException(
                        status_code=422,
                        detail=MODEL_SETTINGS_ERROR_INTEGER_SETTING.format(setting_key=key),
                    )
            numeric = float(value)
            if numeric < metadata["min"] or numeric > metadata["max"]:
                raise HTTPException(
                    status_code=422,
                    detail=MODEL_SETTINGS_ERROR_RANGE_SETTING.format(setting_key=key),
                )
            if not _matches_step(numeric, float(metadata["min"]), float(metadata["step"])):
                raise HTTPException(
                    status_code=422,
                    detail=MODEL_SETTINGS_ERROR_STEP_SETTING.format(setting_key=key),
                )
            metadata["value"] = value

        try:
            validate_model_settings_document(updated, mode)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        _write_mode_locked(updated, mode_name(mode))
        audit_logger.log(
            action=MODEL_SETTINGS_UPDATE_SUCCESS.format(
                mode=mode_name(mode),
                group=group,
                model_key=model_key,
            )
        )
        return copy.deepcopy(model)


def reset_model_settings(
    group: str | None = None,
    model_key: str | None = None,
    mode: str | None = None,
) -> dict[str, Any]:
    with model_settings_lock:
        updated = read_model_settings_document(mode)
        groups = [group] if group else sorted(GROUPS)
        for current_group in groups:
            for model in models(updated, current_group):
                if model_key is not None and model["model_key"] != model_key:
                    continue
                model["active"] = model["default_active"]
                for metadata in model["settings_values"].values():
                    metadata["value"] = metadata["default"]
            if model_key is not None:
                reset_model = find_model(updated, current_group, model_key)
                if reset_model.get("model_role") == "face_compliance":
                    default_compliance = next(
                        (
                            candidate
                            for candidate in models(updated, current_group)
                            if candidate.get("model_role") == "face_compliance"
                            and candidate.get("default_active")
                        ),
                        None,
                    )
                    for candidate in models(updated, current_group):
                        if candidate.get("model_role") == "face_compliance":
                            candidate["active"] = candidate is default_compliance

        validate_model_settings_document(updated, mode)
        _write_mode_locked(updated, mode_name(mode))
        scope = model_key or group or "all"
        audit_logger.log(
            action=MODEL_SETTINGS_RESET_SUCCESS.format(
                mode=mode_name(mode),
                scope=scope,
            )
        )
        return copy.deepcopy(updated)
