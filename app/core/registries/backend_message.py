from __future__ import annotations

from typing import Final

# =========================================================
# BACKEND — 5xx Server Errors
# =========================================================
BACKEND_ERROR_INTERNAL: Final[str] = (
    "An unexpected internal server error occurred. Plase contact to GutsEssCenter"
)

BACKEND_ERROR_NOT_IMPLEMENTED: Final[str] = (
    "This feature is not yet implemented. Plase contact to GutsEssCenter"
)

BACKEND_ERROR_BAD_GATEWAY: Final[str] = (
    "Received an invalid response from the upstream server. Plase contact to GutsEssCenter"
)

BACKEND_ERROR_SERVICE_UNAVAILABLE: Final[str] = (
    "Server is temporarily offline for maintenance. Plase contact to GutsEssCenter"
)

BACKEND_ERROR_GATEWAY_TIMEOUT: Final[str] = (
    "Upstream server timed out. Plase contact to GutsEssCenter"
)

BACKEND_ERROR_HTTP_VERSION_NOT_SUPPORTED: Final[str] = (
    "HTTP version used is not supported. Plase contact to GutsEssCenter"
)

BACKEND_ERROR_VARIANT_ALSO_NEGOTIATES: Final[str] = (
    "Internal configuration error in content negotiation. Plase contact to GutsEssCenter"
)

BACKEND_ERROR_INSUFFICIENT_STORAGE: Final[str] = (
    "Server is out of storage space. Plase contact to GutsEssCenter"
)

BACKEND_ERROR_LOOP_DETECTED: Final[str] = (
    "Infinite loop detected during processing. Plase contact to GutsEssCenter"
)
