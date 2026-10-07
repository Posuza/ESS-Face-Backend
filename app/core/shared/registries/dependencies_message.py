from __future__ import annotations

from typing import Final

# =========================================================
# Dependencies — Role & permission checks
# =========================================================
ACCESS_DENIED_ROLE: Final[str] = "Access denied: insufficient role"
ACCESS_DENIED_PERMISSION: Final[str] = "Access denied: insufficient permissions"

# =========================================================
# Dependencies — Employee checks
# =========================================================
EMPLOYEE_NOT_FOUND: Final[str] = "Employee not found"
ACCOUNT_INACTIVE: Final[str] = "Account is inactive"

# =========================================================
# Dependencies — Scope active checks (position / department / division)
# =========================================================
POSITION_NOT_FOUND: Final[str] = "Position not found"
POSITION_INACTIVE: Final[str] = "Position is inactive"
DEPARTMENT_NOT_FOUND: Final[str] = "Department not found"
DEPARTMENT_INACTIVE: Final[str] = "Department is inactive"
DIVISION_NOT_FOUND: Final[str] = "Division not found"
DIVISION_INACTIVE: Final[str] = "Division is inactive"
