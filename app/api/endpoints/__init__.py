from fastapi import APIRouter

from .auth import router as auth_router
from .mo_daily_transactions import router as mo_daily_transactions_router
from .mo_daily_transactions_helpers import router as mo_daily_transactions_helpers_router
from .mo_report_export import router as mo_report_export_router
from .mo_workplace import router as workplace_router
from app.job_assigner.router import router as job_assigner_router

api_router = APIRouter()

api_router.include_router(auth_router,
    prefix="/auth",
    tags=["auth"])
api_router.include_router(
    workplace_router,
    prefix="/workplace",
    tags=["workplace"],
)
api_router.include_router(
    mo_daily_transactions_helpers_router,
    prefix="/mo-daily-transactions",
    tags=["mo_daily_transactions"],
)
api_router.include_router(
    mo_daily_transactions_router,
    prefix="/mo-daily-transactions",
    tags=["mo_daily_transactions"],
)
api_router.include_router(
    mo_report_export_router,
    prefix="/mo-report-exports",
    tags=["mo_report_exports"],
)
api_router.include_router(
    job_assigner_router,
    prefix="/job-assigner",
    tags=["job_assigner"],
)
