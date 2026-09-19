from __future__ import annotations

from typing import Final


# ADMIN — Employee management audit actions
ADMIN_EMPLOYEE_CREATE_SUCCESS: Final[str] = "Admin created employee (code={employee_code})"
ADMIN_EMPLOYEE_UPDATE_SUCCESS: Final[str] = "Admin updated employee (code={employee_code})"
ADMIN_EMPLOYEE_PASSWORD_RESET_SUCCESS: Final[str] = (
    "Admin reset employee password (code={employee_code})"
)
ADMIN_EMPLOYEE_DELETE_SUCCESS: Final[str] = "Admin deleted employee (code={employee_code})"
ADMIN_FACE_PROFILE_REPLACE_SUCCESS: Final[str] = (
    "Admin replaced employee face profile (code={employee_code})"
)
ADMIN_FACE_PROFILE_DELETE_SUCCESS: Final[str] = (
    "Admin deleted employee face profile (code={employee_code})"
)

# ADMIN — Common errors
ADMIN_ERROR_EMPLOYEE_NOT_FOUND: Final[str] = "Employee not found"
ADMIN_ERROR_EMPLOYEE_CODE_EXISTS: Final[str] = "Employee code already exists"
ADMIN_ERROR_EMPLOYEE_DATA_CONFLICT: Final[str] = (
    "Employee data conflicts with existing records"
)
ADMIN_ERROR_DELETE_SELF: Final[str] = "You cannot delete your own admin account"
ADMIN_ERROR_EMPLOYEE_REFERENCED: Final[str] = (
    "This employee is referenced by other records. Deactivate the account instead."
)
ADMIN_ERROR_FACE_PROFILE_NOT_FOUND: Final[str] = "Employee has no face profile"
