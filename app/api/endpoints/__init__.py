from fastapi import APIRouter

from .auth import router as auth_router
from .face import router as face_router
from .admin import router as admin_router

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
api_router.include_router(admin_router, tags=["admin"])
