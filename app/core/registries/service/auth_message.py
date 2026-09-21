from __future__ import annotations

from typing import Final

# =========================================================
# AUTH — General errors
# =========================================================
AUTH_ERROR_UNAUTHORIZED: Final[str] = (
    "จำเป็นต้องยืนยันตัวตน โปรดเข้าสู่ระบบ. Plase contact to GutsEssCenter"
)
AUTH_ERROR_FORBIDDEN: Final[str] = (
    "Access denied. Insufficient permissions. Plase contact to GutsEssCenter"
)
AUTH_ERROR_TOKEN_EXPIRED: Final[str] = (
    "Session expired. Please refresh your token. Plase contact to GutsEssCenter"
)
AUTH_ERROR_PROXY_AUTH_REQUIRED: Final[str] = (
    "Proxy authentication required. Plase contact to GutsEssCenter"
)
AUTH_ERROR_NETWORK_AUTH_REQUIRED: Final[str] = (
    "Network authentication required to gain access. Plase contact to GutsEssCenter"
)

# =========================================================
# AUTH — Credential errors
# =========================================================
AUTH_ERROR_INVALID_CREDENTIALS: Final[str] = "รหัสผ่านไม่ถูกต้อง"

# =========================================================
# AUTH — Account status errors
# =========================================================
AUTH_ERROR_ACCOUNT_LOCKED: Final[str] = (
    "Account is locked due to multiple failed login attempts. "
    "Plase contact to GutsEssCenter"
)


# =========================================================
# AUTH — Audit: Login
# =========================================================
LOGIN_ATTEMPT: Final[str] = "{resource} Attempt to Login"
LOGIN_FAILED: Final[str] = "{resource} Login attempt failed"
LOGIN_FAILED_REASON: Final[str] = "{resource} Login attempt failed - {reason}"
LOGIN_SUCCESS: Final[str] = "{resource} Login successful"

# =========================================================
# AUTH — Audit:  Logout
# =========================================================
LOGOUT_ATTEMPT: Final[str] = "{resource} Attempt to Logout"
LOGOUT_FAILED: Final[str] = "{resource} Logout failed"
LOGOUT_SUCCESS: Final[str] = "{resource} Logout successful"

# =========================================================
# AUTH — Audit: Registration
# =========================================================
REGISTER: Final[str] = "{resource} registered successfully (code={employee_code})"
REGISTER_DUPLICATE: Final[str] = "{resource} registration failed - duplicate {field} ({value})"
