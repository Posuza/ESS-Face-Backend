"""
app.api.dependencies
--------------------
Decorator-based auth, role and permission guards.

Usage (same as before — backward compatible):
    from app.api.dependencies import active_employee_required

"""

from app.api.dependencies.base import (  # noqa: F401
    admin_user_manager_required,
    active_employee_required,
    permissions_required,
    roles_required,
)
__all__ = [
    "admin_user_manager_required",
    "active_employee_required",
    "permissions_required",
    "roles_required",
]
