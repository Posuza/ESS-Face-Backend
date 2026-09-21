import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app import models as models  # noqa: F401
from app.api.endpoints import api_router
from app.core.audit_logger import clear_audit_context, set_audit_context
from app.core.db.db_error_handler import DatabaseErrorMiddleware

_logger = logging.getLogger(__name__)


class AuditContextMiddleware:
    """Provide request context to service-layer audit logging."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request = Request(scope, receive=receive)
        set_audit_context(request=request, user_name="anonymous")
        try:
            await self.app(scope, receive, send)
        finally:
            clear_audit_context()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _logger.info("Application startup: DB metadata auto-sync skipped")
    yield


app = FastAPI(
    title="GUTSESS Backend API",
    description="Authentication, employee, and face verification APIs.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AuditContextMiddleware)
app.add_middleware(DatabaseErrorMiddleware)


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "status": "healthy",
        "service": "GUTSESS Backend API",
        "version": "1.0.0",
    }


@app.get("/api/v1/health")
async def health_check():
    return {"status": "ok"}
