from __future__ import annotations

from typing import Final

# =========================================================
# DB — Connection
# =========================================================
DATABASE_ERROR_CONNECTION_FAILED: Final[str] = (
    "Database connection failed. Please contact GutsEssCenter."
)

DATABASE_ERROR_HOST_BLOCKED: Final[str] = (
    "Database host is temporarily blocked due to connection errors. "
    "Please contact GutsEssCenter."
)


# =========================================================
# DB — Query
# =========================================================
DATABASE_ERROR_QUERY_ERROR: Final[str] = (
    "Database query execution failed. Please contact GutsEssCenter."
)


# =========================================================
# DB — Data integrity
# =========================================================
DATABASE_ERROR_DATA_CORRUPTION: Final[str] = (
    "Data integrity check failed. Please contact GutsEssCenter."
)
