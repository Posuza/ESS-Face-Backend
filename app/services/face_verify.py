from __future__ import annotations

import base64
import io
import logging
import time
import uuid
from datetime import datetime
from pathlib import Path

import numpy as np
import onnxruntime as ort
from fastapi import HTTPException
from PIL import Image, ImageOps
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.face_constants import FaceConstants
from app.core.model_settings import get_model_value, is_model_active
from app.core.media_storage import (
    face_image_key,
    normalize_face_image_key,
    resolve_face_image_path,
)
from app.models.employees import Employee
from app.schemas.face_verify import FaceEnrollRequest, FaceVerifyRequest
from app.services.auth import employee_auth_service


_attempts: dict[str, list[float]] = {}
_detector_session: ort.InferenceSession | None = None
_recognizer_session: ort.InferenceSession | None = None
_attribute_session: ort.InferenceSession | None = None
_logger = logging.getLogger(__name__)

# Standard ArcFace 5-point template for a 112x112 aligned face.
_ARCFACE_DST = np.array(
    [
        [38.2946, 51.6963],
        [73.5318, 51.5014],
        [56.0252, 71.7366],
        [41.5493, 92.3655],
        [70.7299, 92.2041],
    ],
    dtype=np.float32,
)


def _session(path: str, kind: str) -> ort.InferenceSession:
    global _attribute_session, _detector_session, _recognizer_session

    model_path = Path(path)
    if not model_path.exists():
        raise HTTPException(
            status_code=500,
            detail=f"Missing {kind} ONNX model: {model_path}",
        )

    providers = ["CPUExecutionProvider"]
    options = ort.SessionOptions()
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

    if kind == "face detector":
        if _detector_session is None:
            _detector_session = ort.InferenceSession(
                str(model_path), sess_options=options, providers=providers
            )
        return _detector_session

    if kind == "face attribute classifier":
        if _attribute_session is None:
            _attribute_session = ort.InferenceSession(
                str(model_path), sess_options=options, providers=providers
            )
        return _attribute_session

    if _recognizer_session is None:
        _recognizer_session = ort.InferenceSession(
            str(model_path), sess_options=options, providers=providers
        )
    return _recognizer_session


def _detector() -> ort.InferenceSession:
    return _session(FaceConstants.FACE_DETECTOR_MODEL, "face detector")


def _recognizer() -> ort.InferenceSession:
    return _session(FaceConstants.FACE_RECOGNIZER_MODEL, "face recognizer")


def _attribute_classifier() -> ort.InferenceSession:
    return _session(
        FaceConstants.FACE_ATTRIBUTE_MODEL, "face attribute classifier"
    )


def _rate(code: str) -> None:
    now = time.time()
    attempts = [
        t
        for t in _attempts.get(code, [])
        if t > now - FaceConstants.VERIFY_WINDOW_SECONDS
    ]
    if len(attempts) >= FaceConstants.VERIFY_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=429,
            detail="พยายามยืนยันใบหน้าบ่อยเกินไป กรุณารอสักครู่แล้วลองใหม่",
        )
    attempts.append(now)
    _attempts[code] = attempts


def _decode(data_url: str) -> Image.Image:
    try:
        raw = data_url.split(",", 1)[1] if "," in data_url else data_url
        image_bytes = base64.b64decode(raw, validate=True)
        image = Image.open(io.BytesIO(image_bytes))
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.load()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="รูปภาพไม่ถูกต้อง") from exc

    if image.width < 80 or image.height < 80:
        raise HTTPException(status_code=400, detail="รูปภาพมีขนาดเล็กเกินไป")
    return image


def _load_image(path: str | Path) -> Image.Image:
    try:
        image = Image.open(path)
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.load()
        return image
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail="ไม่สามารถอ่านรูปใบหน้าอ้างอิงได้"
        ) from exc


def _gray(image: Image.Image) -> np.ndarray:
    return np.asarray(image.convert("L"), dtype=np.float32)


def _blur_score(gray: np.ndarray) -> float:
    """Variance of a small discrete Laplacian, implemented with NumPy only."""
    if gray.shape[0] < 3 or gray.shape[1] < 3:
        return 0.0
    center = gray[1:-1, 1:-1]
    lap = (
        gray[:-2, 1:-1]
        + gray[2:, 1:-1]
        + gray[1:-1, :-2]
        + gray[1:-1, 2:]
        - 4.0 * center
    )
    return float(np.var(lap))


def _mode_quality_value(mode: str, key: str, fallback: float) -> float:
    return float(
        get_model_value(
            "backend_models",
            "backend_image_quality",
            key,
            fallback,
            mode=mode,
        )
    )


def _quality(image: Image.Image, mode: str = "verify") -> None:
    # Registration is intentionally stricter. Verification is more tolerant
    # while preserving enough quality for SCRFD + ArcFace.
    sample = image.copy()
    sample.thumbnail((320, 320), Image.Resampling.BILINEAR)
    gray = _gray(sample)
    brightness = float(gray.mean())
    blur = _blur_score(gray)

    min_brightness = _mode_quality_value(mode, "min_brightness", FaceConstants.MIN_BRIGHTNESS)
    max_brightness = _mode_quality_value(mode, "max_brightness", FaceConstants.MAX_BRIGHTNESS)
    min_blur = _mode_quality_value(mode, "min_blur_score", FaceConstants.MIN_BLUR_SCORE)

    if brightness < min_brightness:
        raise HTTPException(status_code=400, detail="ภาพมืดเกินไป กรุณาเพิ่มแสงแล้วลองใหม่")
    if brightness > max_brightness:
        raise HTTPException(status_code=400, detail="ภาพสว่างเกินไป กรุณาหลีกเลี่ยงแสงจ้า")
    if blur < min_blur:
        raise HTTPException(status_code=400, detail="ภาพเบลอเกินไป กรุณาถ่ายใหม่")


def _letterbox(image: Image.Image, size: int) -> tuple[np.ndarray, float]:
    width, height = image.size
    scale = min(size / width, size / height)
    resized_w = max(1, int(round(width * scale)))
    resized_h = max(1, int(round(height * scale)))

    resized = image.resize((resized_w, resized_h), Image.Resampling.BILINEAR)
    canvas = Image.new("RGB", (size, size), (0, 0, 0))
    # SCRFD implementations conventionally place the resized image at 0,0.
    canvas.paste(resized, (0, 0))

    array = np.asarray(canvas, dtype=np.float32)
    tensor = (array - 127.5) / 128.0
    tensor = np.transpose(tensor, (2, 0, 1))[None, ...].astype(np.float32)
    return tensor, scale


def _distance2bbox(points: np.ndarray, distance: np.ndarray) -> np.ndarray:
    x1 = points[:, 0] - distance[:, 0]
    y1 = points[:, 1] - distance[:, 1]
    x2 = points[:, 0] + distance[:, 2]
    y2 = points[:, 1] + distance[:, 3]
    return np.stack([x1, y1, x2, y2], axis=1)


def _distance2kps(points: np.ndarray, distance: np.ndarray) -> np.ndarray:
    result = []
    for i in range(0, distance.shape[1], 2):
        result.append(points[:, 0] + distance[:, i])
        result.append(points[:, 1] + distance[:, i + 1])
    return np.stack(result, axis=1).reshape(-1, 5, 2)


def _nms(boxes: np.ndarray, scores: np.ndarray, threshold: float) -> list[int]:
    if len(boxes) == 0:
        return []

    x1, y1, x2, y2 = boxes.T
    areas = np.maximum(0.0, x2 - x1 + 1) * np.maximum(0.0, y2 - y1 + 1)
    order = scores.argsort()[::-1]
    keep: list[int] = []

    while order.size > 0:
        i = int(order[0])
        keep.append(i)
        if order.size == 1:
            break

        rest = order[1:]
        xx1 = np.maximum(x1[i], x1[rest])
        yy1 = np.maximum(y1[i], y1[rest])
        xx2 = np.minimum(x2[i], x2[rest])
        yy2 = np.minimum(y2[i], y2[rest])
        w = np.maximum(0.0, xx2 - xx1 + 1)
        h = np.maximum(0.0, yy2 - yy1 + 1)
        inter = w * h
        union = areas[i] + areas[rest] - inter + 1e-12
        iou = inter / union
        order = rest[np.where(iou <= threshold)[0]]

    return keep


def _reshape_scores(output: np.ndarray) -> np.ndarray:
    arr = np.asarray(output)
    return arr.reshape(-1).astype(np.float32)


def _reshape_pred(output: np.ndarray, columns: int) -> np.ndarray:
    arr = np.asarray(output)
    return arr.reshape(-1, columns).astype(np.float32)


def _detect_faces(image: Image.Image, mode: str = "verify") -> list[tuple[np.ndarray, np.ndarray, float]]:
    """Run a standard SCRFD ONNX model with 5-point keypoints.

    Expected model family: 3 FPN strides (8,16,32) and 9 outputs grouped as
    [scores...][bbox...][kps...], which is the normal InsightFace SCRFD export.
    """
    session = _detector()
    input_meta = session.get_inputs()[0]
    input_name = input_meta.name
    input_shape = input_meta.shape

    configured_size = FaceConstants.FACE_DETECTOR_INPUT_SIZE
    if (
        len(input_shape) == 4
        and isinstance(input_shape[2], int)
        and isinstance(input_shape[3], int)
        and input_shape[2] == input_shape[3]
    ):
        input_size = int(input_shape[2])
    else:
        input_size = configured_size

    tensor, scale = _letterbox(image, input_size)
    outputs = session.run(None, {input_name: tensor})

    if len(outputs) % 3 != 0:
        raise HTTPException(
            status_code=500,
            detail="Unsupported face detector ONNX output format. Use a standard SCRFD model with keypoints.",
        )

    fmc = len(outputs) // 3
    if fmc == 3:
        strides = [8, 16, 32]
    elif fmc == 5:
        strides = [8, 16, 32, 64, 128]
    else:
        raise HTTPException(
            status_code=500,
            detail="Unsupported SCRFD feature-map count.",
        )

    all_boxes: list[np.ndarray] = []
    all_scores: list[np.ndarray] = []
    all_kps: list[np.ndarray] = []

    for idx, stride in enumerate(strides):
        scores = _reshape_scores(outputs[idx])
        bbox_preds = _reshape_pred(outputs[idx + fmc], 4) * stride
        kps_preds = _reshape_pred(outputs[idx + fmc * 2], 10) * stride

        height = input_size // stride
        width = input_size // stride
        anchor_centers = np.stack(
            np.mgrid[:height, :width][::-1], axis=-1
        ).astype(np.float32)
        anchor_centers = (anchor_centers * stride).reshape((-1, 2))

        # Standard SCRFD exports use two anchors per location for these models.
        num_anchors = max(1, scores.shape[0] // anchor_centers.shape[0])
        anchor_centers = np.repeat(anchor_centers, num_anchors, axis=0)

        count = min(
            scores.shape[0],
            bbox_preds.shape[0],
            kps_preds.shape[0],
            anchor_centers.shape[0],
        )
        scores = scores[:count]
        bbox_preds = bbox_preds[:count]
        kps_preds = kps_preds[:count]
        anchor_centers = anchor_centers[:count]

        score_threshold = float(
            get_model_value(
                "backend_models",
                "scrfd_detector",
                "score_threshold",
                FaceConstants.FACE_DETECTOR_SCORE_THRESHOLD,
                mode=mode,
            )
        )
        positive = np.where(scores >= score_threshold)[0]
        if positive.size == 0:
            continue

        boxes = _distance2bbox(anchor_centers, bbox_preds)[positive] / scale
        kps = _distance2kps(anchor_centers, kps_preds)[positive] / scale
        all_boxes.append(boxes)
        all_scores.append(scores[positive])
        all_kps.append(kps)

    if not all_boxes:
        return []

    boxes = np.concatenate(all_boxes, axis=0)
    scores = np.concatenate(all_scores, axis=0)
    kps = np.concatenate(all_kps, axis=0)

    nms_threshold = float(
            get_model_value(
                "backend_models",
                "scrfd_detector",
                "nms_threshold",
                FaceConstants.FACE_DETECTOR_NMS_THRESHOLD,
                mode=mode,
            )
        )
    keep = _nms(boxes, scores, nms_threshold)
    results = [(boxes[i], kps[i], float(scores[i])) for i in keep]
    return results


def _similarity_transform(src: np.ndarray, dst: np.ndarray) -> np.ndarray:
    """Return a 2x3 similarity transform mapping src -> dst (Umeyama-style)."""
    src = np.asarray(src, dtype=np.float64)
    dst = np.asarray(dst, dtype=np.float64)

    src_mean = src.mean(axis=0)
    dst_mean = dst.mean(axis=0)
    src_centered = src - src_mean
    dst_centered = dst - dst_mean

    covariance = (dst_centered.T @ src_centered) / src.shape[0]
    u, s, vt = np.linalg.svd(covariance)

    d = np.ones(2)
    if np.linalg.det(u) * np.linalg.det(vt) < 0:
        d[-1] = -1

    rotation = u @ np.diag(d) @ vt
    src_variance = np.mean(np.sum(src_centered**2, axis=1))
    if src_variance <= 1e-12:
        raise HTTPException(status_code=400, detail="ตำแหน่งใบหน้าไม่ถูกต้อง")

    scale = float(np.sum(s * d) / src_variance)
    translation = dst_mean - scale * (rotation @ src_mean)

    matrix = np.zeros((2, 3), dtype=np.float64)
    matrix[:, :2] = scale * rotation
    matrix[:, 2] = translation
    return matrix


def _align_face(image: Image.Image, keypoints: np.ndarray) -> Image.Image:
    size = FaceConstants.FACE_RECOGNIZER_INPUT_SIZE
    dst = _ARCFACE_DST.copy()
    if size != 112:
        dst *= size / 112.0

    forward = _similarity_transform(keypoints, dst)
    homogeneous = np.vstack([forward, [0.0, 0.0, 1.0]])
    inverse = np.linalg.inv(homogeneous)[:2, :]

    coeffs = tuple(float(x) for x in inverse.reshape(-1))
    return image.transform(
        (size, size),
        Image.Transform.AFFINE,
        coeffs,
        resample=Image.Resampling.BILINEAR,
    )


def _attribute_face_crop(image: Image.Image, box: np.ndarray) -> Image.Image:
    x1, y1, x2, y2 = (float(value) for value in box)
    width = max(1.0, x2 - x1)
    height = max(1.0, y2 - y1)
    side = max(width, height) * 1.24
    center_x = (x1 + x2) / 2.0
    center_y = (y1 + y2) / 2.0
    left = int(round(center_x - side / 2.0))
    top = int(round(center_y - side / 2.0))
    right = int(round(center_x + side / 2.0))
    bottom = int(round(center_y + side / 2.0))
    crop = image.crop((left, top, right, bottom))
    return crop.resize(
        (FaceConstants.FACE_ATTRIBUTE_INPUT_SIZE,) * 2,
        Image.Resampling.BILINEAR,
    )


def _validate_face_attributes(image: Image.Image, box: np.ndarray, mode: str = "verify") -> None:
    session = _attribute_classifier()
    crop = _attribute_face_crop(image, box)
    array = np.asarray(crop.convert("RGB"), dtype=np.uint8)
    tensor = np.transpose(array, (2, 0, 1))[None, ...]
    output = session.run(None, {session.get_inputs()[0].name: tensor})[0]
    probabilities = np.asarray(output, dtype=np.float32).reshape(-1) / 256.0

    if probabilities.size != 5:
        raise HTTPException(
            status_code=500,
            detail="รูปแบบผลลัพธ์ของโมเดลตรวจสิ่งปกปิดใบหน้าไม่ถูกต้อง",
        )

    left_eye_open, right_eye_open, glasses, mask, sunglasses = probabilities
    glasses_threshold = float(
        get_model_value(
            "backend_models", "backend_face_attrib", "glasses_threshold", FaceConstants.EYEGLASSES_THRESHOLD, mode=mode
        )
    )
    sunglasses_threshold = float(
        get_model_value(
            "backend_models", "backend_face_attrib", "sunglasses_threshold", FaceConstants.SUNGLASSES_THRESHOLD, mode=mode
        )
    )
    mask_threshold = float(
        get_model_value(
            "backend_models", "backend_face_attrib", "mask_threshold", FaceConstants.FACE_MASK_THRESHOLD, mode=mode
        )
    )
    eye_openness = float(
        get_model_value(
            "backend_models", "backend_face_attrib", "minimum_eye_openness", FaceConstants.MIN_EYE_OPENNESS, mode=mode
        )
    )

    if glasses >= glasses_threshold or sunglasses >= sunglasses_threshold:
        raise HTTPException(
            status_code=400,
            detail="กรุณาถอดแว่นตาทุกชนิดก่อนถ่ายภาพ",
        )
    if mask >= mask_threshold:
        raise HTTPException(
            status_code=400,
            detail="กรุณาถอดหน้ากากก่อนถ่ายภาพ",
        )
    if (
        left_eye_open < eye_openness
        or right_eye_open < eye_openness
    ):
        raise HTTPException(
            status_code=400,
            detail="กรุณาลืมตาทั้งสองข้างและอย่าให้มีสิ่งปิดบังดวงตา",
        )


def _recognition_embedding(aligned: Image.Image) -> np.ndarray:
    session = _recognizer()
    input_meta = session.get_inputs()[0]
    input_name = input_meta.name

    array = np.asarray(aligned.convert("RGB"), dtype=np.float32)
    # Common ArcFace ONNX preprocessing: RGB, [-1, 1], NCHW.
    tensor = (array - 127.5) / 127.5
    tensor = np.transpose(tensor, (2, 0, 1))[None, ...].astype(np.float32)

    output = session.run(None, {input_name: tensor})[0]
    embedding = np.asarray(output, dtype=np.float32).reshape(-1)
    norm = float(np.linalg.norm(embedding))
    if embedding.size == 0 or norm <= 1e-12:
        raise HTTPException(status_code=400, detail="ไม่สามารถสร้างข้อมูลใบหน้าได้")
    return embedding / norm


def _validate_face(image: Image.Image, mode: str = "verify") -> tuple[np.ndarray, np.ndarray]:
    """Validate a face image without generating an ArcFace embedding.

    Registration stores the reference image itself, so it only needs the
    quality, detection, face-size, and face-attribute checks.
    """
    _quality(image, mode)
    faces = _detect_faces(image, mode)

    if len(faces) == 0:
        raise HTTPException(status_code=400, detail="ไม่พบใบหน้าในรูปภาพ")
    if len(faces) > 1:
        raise HTTPException(
            status_code=400,
            detail="พบมากกว่าหนึ่งใบหน้า กรุณาถ่ายเฉพาะพนักงานคนเดียว",
        )

    box, keypoints, _score = faces[0]
    x1, y1, x2, y2 = box
    face_area = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    image_area = float(image.width * image.height)
    min_face_area_ratio = _mode_quality_value(
        mode, "min_face_area_ratio", FaceConstants.MIN_FACE_AREA_RATIO
    )
    if image_area <= 0 or face_area / image_area < min_face_area_ratio:
        raise HTTPException(
            status_code=400, detail="ใบหน้าอยู่ไกลเกินไป กรุณาเข้าใกล้กล้อง"
        )

    if is_model_active("backend_models", "backend_face_attrib", mode=mode):
        _validate_face_attributes(image, box, mode)

    return box, keypoints


def _embedding(image: Image.Image, mode: str = "verify") -> np.ndarray:
    """Validate the image and create an ArcFace embedding for comparison."""
    _box, keypoints = _validate_face(image, mode)
    aligned = _align_face(image, keypoints)
    return _recognition_embedding(aligned)


def _employee(db: Session, code: str) -> Employee:
    employee = db.scalar(
        select(Employee).where(Employee.employee_code == code.strip())
    )
    if employee is None:
        raise HTTPException(status_code=404, detail="ไม่พบข้อมูลพนักงาน")
    return employee


def _reference_image(employee: Employee) -> str:
    if not employee.profile_image_path:
        raise HTTPException(
            status_code=404,
            detail="ยังไม่มีรูปใบหน้าอ้างอิงสำหรับพนักงานคนนี้",
        )
    return employee.profile_image_path


def _save_image(code: str, image: Image.Image) -> tuple[str, Path | None]:
    key = face_image_key(code)
    path = resolve_face_image_path(key)
    folder = path.parent
    temporary_path = folder / f".{path.name}.{uuid.uuid4().hex}.tmp"
    backup_path: Path | None = None
    try:
        folder.mkdir(parents=True, exist_ok=True)
        image.save(temporary_path, format="JPEG", quality=95, optimize=True)
        if path.exists():
            backup_path = folder / f".{path.name}.{uuid.uuid4().hex}.bak"
            path.replace(backup_path)
        temporary_path.replace(path)
    except Exception as exc:
        temporary_path.unlink(missing_ok=True)
        if backup_path is not None and backup_path.is_file() and not path.exists():
            backup_path.replace(path)
        raise HTTPException(status_code=500, detail="บันทึกรูปใบหน้าไม่สำเร็จ") from exc
    return key, backup_path


def _restore_replaced_image(filename: str, backup_path: Path | None) -> None:
    current_path = resolve_face_image_path(filename)
    current_path.unlink(missing_ok=True)
    if backup_path is not None:
        backup_path.replace(current_path)


def _discard_image_backup(backup_path: Path | None) -> None:
    if backup_path is not None:
        try:
            backup_path.unlink(missing_ok=True)
        except OSError as exc:
            _logger.warning("Unable to remove face image backup %s: %s", backup_path, exc)


def _delete_stored_image(stored_value: str) -> None:
    try:
        resolve_face_image_path(stored_value).unlink(missing_ok=True)
    except (OSError, ValueError) as exc:
        _logger.warning("Unable to remove replaced face image %r: %s", stored_value, exc)


class FaceVerifyService:
    @staticmethod
    def get_employee(db: Session, employee_code: str) -> Employee:
        employee = _employee(db, employee_code)
        if not employee.is_active:
            raise HTTPException(status_code=403, detail="บัญชีพนักงานถูกปิดใช้งาน")
        return employee

    @staticmethod
    def get_employee_profile(db: Session, employee_code: str) -> dict:
        """Return the same non-sensitive employee details used after login."""

        employee = FaceVerifyService.get_employee(db, employee_code)
        profile = employee_auth_service.build_login_response(db, employee)["employee"]
        return {
            **profile,
            "has_face_profile": bool(employee.profile_image_path),
        }

    @staticmethod
    def get_profile_image_path(db: Session, employee_code: str) -> Path:
        employee = FaceVerifyService.get_employee(db, employee_code)
        try:
            image_path = resolve_face_image_path(_reference_image(employee))
        except ValueError as exc:
            raise HTTPException(
                status_code=500, detail="ข้อมูลตำแหน่งไฟล์รูปใบหน้าไม่ถูกต้อง"
            ) from exc
        if not image_path.is_file():
            raise HTTPException(
                status_code=404,
                detail=f"ไม่พบไฟล์รูปใบหน้าอ้างอิง: {image_path}",
            )
        return image_path

    @staticmethod
    def enroll_face(db: Session, payload: FaceEnrollRequest) -> Employee:
        code = payload.employee_code.strip()
        employee = FaceVerifyService.get_employee(db, code)
        image = _decode(payload.image_data_url)

        # Validate the registration photo without generating an ArcFace embedding.
        # The reference image is stored and embeddings are generated later during verification.
        _validate_face(image, "register")
        previous_image = employee.profile_image_path
        image_key, backup_path = _save_image(code, image)

        employee.profile_image_path = image_key
        employee.profile_image_updated_at = datetime.now()
        employee.updated_by = payload.created_by or employee.employee_code
        try:
            db.commit()
        except Exception:
            db.rollback()
            _restore_replaced_image(image_key, backup_path)
            raise

        _discard_image_backup(backup_path)
        if previous_image and normalize_face_image_key(previous_image) != image_key:
            _delete_stored_image(previous_image)
        db.refresh(employee)
        return employee

    @staticmethod
    def verify_face(db: Session, payload: FaceVerifyRequest) -> dict[str, object]:
        code = payload.employee_code.strip()
        _rate(code)
        employee = FaceVerifyService.get_employee(db, code)
        try:
            reference_image = resolve_face_image_path(_reference_image(employee))
        except ValueError as exc:
            raise HTTPException(
                status_code=500, detail="ข้อมูลตำแหน่งไฟล์รูปใบหน้าไม่ถูกต้อง"
            ) from exc

        incoming = _embedding(_decode(payload.image_data_url), "verify")
        # Stored reference was captured under registration rules.
        stored = _embedding(_load_image(reference_image), "register")

        # Both vectors are L2-normalized, so dot product == cosine similarity.
        score = float(np.dot(stored, incoming))
        threshold = float(
            get_model_value(
                "backend_models",
                "arcface_recognizer",
                "cosine_threshold",
                FaceConstants.FACE_VERIFY_COSINE_THRESHOLD,
                mode="verify",
            )
        )
        is_match = score >= threshold

        return {
            "is_match": is_match,
            "message": (
                "ยืนยันใบหน้าสำเร็จ"
                if is_match
                else "ใบหน้าไม่ตรงกับข้อมูลพนักงาน"
            ),
            "score": round(score, 6),
            "threshold": threshold,
        }


face_verify_service = FaceVerifyService()
