from __future__ import annotations

from typing import Final


# FACE — Audit actions
FACE_LOOKUP_ATTEMPT: Final[str] = "Employee face lookup attempt (code={employee_code})"
FACE_LOOKUP_SUCCESS: Final[str] = "Employee face lookup successful (code={employee_code})"
FACE_PROFILE_IMAGE_VIEW_SUCCESS: Final[str] = (
    "Employee face profile image viewed (code={employee_code})"
)
FACE_ENROLL_ATTEMPT: Final[str] = "Employee face enrollment attempt (code={employee_code})"
FACE_ENROLL_SUCCESS: Final[str] = "Employee face profile enrolled (code={employee_code})"
FACE_VERIFY_ATTEMPT: Final[str] = "Employee face verification attempt (code={employee_code})"
FACE_VERIFY_SUCCESS: Final[str] = (
    "Employee face verification successful (code={employee_code}, score={score}, threshold={threshold})"
)
FACE_VERIFY_FAILED: Final[str] = (
    "Employee face verification failed (code={employee_code}, score={score}, threshold={threshold})"
)

# FACE — Common errors
FACE_ERROR_EMPLOYEE_NOT_FOUND: Final[str] = "ไม่พบข้อมูลพนักงาน"
FACE_ERROR_ACCOUNT_INACTIVE: Final[str] = "บัญชีพนักงานถูกปิดใช้งาน"
FACE_ERROR_NO_REFERENCE_IMAGE: Final[str] = "ยังไม่มีรูปใบหน้าอ้างอิงสำหรับพนักงานคนนี้"
FACE_ERROR_INVALID_IMAGE_LOCATION: Final[str] = "ข้อมูลตำแหน่งไฟล์รูปใบหน้าไม่ถูกต้อง"
FACE_ERROR_REFERENCE_IMAGE_NOT_FOUND: Final[str] = "ไม่พบไฟล์รูปใบหน้าอ้างอิง: {image_path}"
