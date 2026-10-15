from fastapi import APIRouter

from .auth.admin import router as admin_router
from .auth.auth import router as auth_router
from .auth.face import router as face_router
from .sdk.applications import router as client_applications_router
from .sdk.auth import router as client_auth_router
from .sdk.blocked_ips import router as blocked_client_ips_router

api_router = APIRouter()

api_router.include_router(
    auth_router,
    prefix="/auth",
    tags=["auth"],
)
api_router.include_router(
    face_router,
    prefix="/faces",
    tags=["faces"],
)
api_router.include_router(
    client_auth_router,
    prefix="/client-auth",
    tags=["client-auth"],
)
api_router.include_router(
    client_applications_router,
    prefix="/admin/client-applications",
    tags=["client-applications"],
)
api_router.include_router(
    blocked_client_ips_router,
    prefix="/admin/blocked-client-ips",
    tags=["blocked-client-ips"],
)
api_router.include_router(admin_router, tags=["admin"])
