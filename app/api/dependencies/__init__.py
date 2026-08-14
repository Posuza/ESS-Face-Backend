"""
app.api.dependencies
--------------------
Decorator-based auth, role & permission guards.

Usage (same as before — backward compatible):
    from app.api.dependencies import active_employee_required

Or use MO-specific shorthand:
    from app.api.dependencies import mo_active_required
"""

from app.api.dependencies.base import (  # noqa: F401
    active_employee_required,
    permissions_required,
    roles_required,
)
from app.api.dependencies.mo import mo_active_required  # noqa: F401

__all__ = [
    "active_employee_required",
    "mo_active_required",
    "permissions_required",
    "roles_required",
]
