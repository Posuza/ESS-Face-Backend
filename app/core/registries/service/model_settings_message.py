from __future__ import annotations

from typing import Final


# MODEL SETTINGS — Audit actions
MODEL_SETTINGS_UPDATE_SUCCESS: Final[str] = (
    "Model settings updated (mode={mode}, group={group}, model={model_key})"
)
MODEL_SETTINGS_RESET_SUCCESS: Final[str] = (
    "Model settings reset (mode={mode}, scope={scope})"
)

# MODEL SETTINGS — Common errors
MODEL_SETTINGS_ERROR_REQUIRED_MODEL: Final[str] = (
    "This model is required and cannot be disabled"
)
MODEL_SETTINGS_ERROR_UNKNOWN_SETTING: Final[str] = "Unknown setting: {setting_key}"
MODEL_SETTINGS_ERROR_FIXED_SETTING: Final[str] = "{setting_key} is fixed and cannot be changed"
MODEL_SETTINGS_ERROR_INTEGER_SETTING: Final[str] = "{setting_key} must be an integer"
MODEL_SETTINGS_ERROR_RANGE_SETTING: Final[str] = "{setting_key} is outside its allowed range"
MODEL_SETTINGS_ERROR_STEP_SETTING: Final[str] = "{setting_key} does not match the allowed step"
