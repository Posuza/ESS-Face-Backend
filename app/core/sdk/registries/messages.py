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
CLIENT_AUTH_APP_REJECTED: Final[str] = (
    "Client application rejected (reason=invalid or inactive public key)"
)
CLIENT_AUTH_CALLBACK_ACCEPTED: Final[str] = (
    "Client callback accepted (app={app_name}, origin={origin})"
)
CLIENT_AUTH_CALLBACK_REJECTED: Final[str] = (
    "Client callback rejected (reason={reason}, public_key={public_key}, origin={origin})"
)
CLIENT_AUTH_CALLBACK_IP_BLOCKED: Final[str] = (
    "Client callback IP blocked (retry_after_seconds={retry_after_seconds})"
)
CLIENT_AUTH_CALLBACK_IP_MANUALLY_BLOCKED: Final[str] = (
    "Client callback IP manually blocked (ip_address={ip_address}, duration_minutes={duration_minutes})"
)
CLIENT_AUTH_CALLBACK_IP_UNBLOCKED: Final[str] = (
    "Client callback IP unblocked (ip_address={ip_address})"
)
CLIENT_AUTH_CALLBACK_IP_REMOVED: Final[str] = (
    "Client callback IP history removed (ip_address={ip_address})"
)
CLIENT_AUTH_APP_CREATED: Final[str] = (
    "Client application created (app={app_name}, public_key={public_key})"
)
CLIENT_AUTH_APP_UPDATED: Final[str] = (
    "Client application updated (app={app_name}, fields={fields})"
)
CLIENT_AUTH_SIGNING_KEY_ROTATED: Final[str] = (
    "Client application signing key rotated (app={app_name})"
)
CLIENT_AUTH_SIGNING_KEY_REVEALED: Final[str] = (
    "Client application signing key revealed (app={app_name})"
)
CLIENT_AUTH_APP_DELETED: Final[str] = (
    "Client application deleted (app={app_name}, public_key={public_key})"
)
