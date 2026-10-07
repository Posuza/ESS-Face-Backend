from __future__ import annotations

from typing import Final


CLIENT_AUTH_PROFILE_LOOKUP: Final[str] = (
    "Client authentication profile lookup (code={employee_code})"
)
CLIENT_AUTH_PASSWORD_LOGIN_ATTEMPT: Final[str] = (
    "Client password login attempt (code={employee_code})"
)
CLIENT_AUTH_PASSWORD_LOGIN_SUCCESS: Final[str] = (
    "Client password login successful (code={employee_code})"
)
CLIENT_AUTH_FACE_LOGIN_ATTEMPT: Final[str] = (
    "Client face login attempt (code={employee_code})"
)
CLIENT_AUTH_FACE_LOGIN_SUCCESS: Final[str] = (
    "Client face login successful (code={employee_code})"
)
CLIENT_AUTH_FACE_LOGIN_FAILED: Final[str] = (
    "Client face login failed (code={employee_code})"
)
CLIENT_AUTH_PASSWORD_RECOVERY_ATTEMPT: Final[str] = (
    "Client face password recovery attempt (code={employee_code})"
)
CLIENT_AUTH_PASSWORD_RECOVERY_SUCCESS: Final[str] = (
    "Client face password recovery successful (code={employee_code})"
)
CLIENT_AUTH_PASSWORD_RECOVERY_FAILED: Final[str] = (
    "Client face password recovery failed (code={employee_code})"
)
CLIENT_AUTH_LOGOUT: Final[str] = (
    "Client logout notification (app={app_name}, code={employee_code})"
)
CLIENT_AUTH_LOGIN_SUCCESS: Final[str] = (
    "Client login successful (app={app_name}, method={method}, code={employee_code})"
)
CLIENT_AUTH_LOGIN_FAILED: Final[str] = (
    "Client login failed (app={app_name}, method={method}, code={employee_code}, status={status_code})"
)
CLIENT_AUTH_TICKET_VERIFY_SUCCESS: Final[str] = (
    "Client ticket verification successful (app={app_name}, code={employee_code})"
)
CLIENT_AUTH_TICKET_VERIFY_FAILED: Final[str] = (
    "Client ticket verification failed (app={app_name})"
)
