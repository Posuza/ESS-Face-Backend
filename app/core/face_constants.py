from __future__ import annotations

from pathlib import Path
from typing import Final


BACKEND_ROOT = Path(__file__).resolve().parents[2]
FACE_MODEL_ROOT = BACKEND_ROOT / "ai" / "models" / "face"


class FaceConstants:
    # Recognition / retry policy. Calibrate these values with real cameras.
    FACE_VERIFY_COSINE_THRESHOLD: Final[float] = 0.42
    VERIFY_MAX_ATTEMPTS: Final[int] = 5
    VERIFY_WINDOW_SECONDS: Final[int] = 60

    # Lightweight ONNX model files. Add licensed models at these paths.
    FACE_DETECTOR_MODEL: Final[str] = str(FACE_MODEL_ROOT / "scrfd.onnx")
    FACE_RECOGNIZER_MODEL: Final[str] = str(FACE_MODEL_ROOT / "arcface.onnx")
    FACE_ATTRIBUTE_MODEL: Final[str] = str(FACE_MODEL_ROOT / "face_attrib_net.onnx")
    FACE_DETECTOR_INPUT_SIZE: Final[int] = 640
    FACE_DETECTOR_SCORE_THRESHOLD: Final[float] = 0.50
    FACE_DETECTOR_NMS_THRESHOLD: Final[float] = 0.40
    FACE_RECOGNIZER_INPUT_SIZE: Final[int] = 112
    FACE_ATTRIBUTE_INPUT_SIZE: Final[int] = 128

    # Qualcomm FaceAttribNet output policy. Calibrate with production cameras.
    MIN_EYE_OPENNESS: Final[float] = 0.25
    EYEGLASSES_THRESHOLD: Final[float] = 0.05
    FACE_MASK_THRESHOLD: Final[float] = 0.35
    SUNGLASSES_THRESHOLD: Final[float] = 0.25

    # Authoritative backend image-quality checks.
    MIN_BRIGHTNESS: Final[float] = 50.0
    MAX_BRIGHTNESS: Final[float] = 215.0
    MIN_BLUR_SCORE: Final[float] = 55.0
    MIN_FACE_AREA_RATIO: Final[float] = 0.035
