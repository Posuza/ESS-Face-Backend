import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.endpoints import api_router
from app.core.audit_logger import clear_audit_context, set_audit_context
from app.core.config import settings
from app.core.db.db_error_handler import DatabaseErrorMiddleware
from app.core.db.engine import Base, engine

_logger = logging.getLogger(__name__)

from app.models import (  # noqa: F401
    addresses,
    audit_logs,
    departments,
    districts,
    divisions,
    employee_permissions,
    employees,
    fields,
    mo_daily_transaction_details,
    mo_daily_transaction_project,
    mo_daily_transactions,
    mo_report_export_job,
    mo_transaction_discipline_warning,
    name_prefixs,
    position_change_logs,
    positions,
    postal_codes,
    provinces,
    roles,
    route_change_logs,
    routes,
    shifts,
    sub_districts,
)
from app.job_assigner import models as job_assigner_models  # noqa: F401


class AuditContextMiddleware(BaseHTTPMiddleware):
    """Inject audit context so audit.action() works without repeating params."""

    async def dispatch(self, request: Request, call_next):
        set_audit_context(request=request, user_name="anonymous")
        response = await call_next(request)
        clear_audit_context()
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    _logger.info("Application startup: DB metadata auto-sync skipped")
    yield


app = FastAPI(
    title="GUTSESS Backend API",
    description="""
    GUTSESS Backend APIs

    ## api Levels

    | no | Name                | list | get1 | update | delete |
    |----|---------------------|------|------|--------|--------|
    | 14 | mo_daily_transactions | true | true | true   | true   |


    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inject audit context for endpoints
app.add_middleware(AuditContextMiddleware)

# Database Error Handler (catches all DB errors globally)
app.add_middleware(DatabaseErrorMiddleware)


# Custom HTTPException handler to support detail as object
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


# Include routers
app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "status": "healthy",
        "service": "PBAC Backend API",
        "version": "1.0.0",
        "architecture": "Brain/Nervous/Hands",
    }


@app.get("/api/v1/health")
async def health_check():
    return {"status": "ok"}
