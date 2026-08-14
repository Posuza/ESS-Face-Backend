from __future__ import annotations

from typing import Final

# =========================================================
# EMAIL — Errors
# =========================================================
AUTH_ERROR_NO_EMAIL_REGISTERED: Final[str] = (
    "ไม่พบอีเมลที่ลงทะเบียนไว้สำหรับรหัสพนักงานนี้ "
    "โปรดติดต่อฝ่ายทรัพยากรบุคคล. "
    "Plase contact to GutsEssCenter"
)

# =========================================================
# EMAIL — Generic send status (works for all email types)
# =========================================================
EMAIL_SEND_ATTEMPT: Final[str] = "{resource} Attempting to send email to {email}"
EMAIL_SEND_SUCCESS: Final[str] = "{resource} Email sent successfully to {email}"
EMAIL_SEND_FAILED: Final[str] = "{resource} Email FAILED for {email}"
