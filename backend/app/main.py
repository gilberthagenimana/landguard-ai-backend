from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api.v1.routes.audit import router as audit_router
from app.api.v1.routes.auth import router as auth_router
from app.api.v1.routes.cases import router as cases_router
from app.api.v1.routes.dashboard import router as dashboard_router
from app.api.v1.routes.owners import router as owners_router
from app.api.v1.routes.parcels import router as parcels_router
from app.api.v1.routes.reports import router as reports_router
from app.api.v1.routes.risk import router as risk_router
from app.api.v1.routes.transactions import router as transactions_router
from app.api.v1.routes.users import router as users_router
from app.api.v1.routes.verification import router as verification_router
from app.core.config import settings
from app.db.init_db import init_db

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="LandGuard AI",
    version="1.0.0",
    description=(
        "Academic decision-support system for land transaction verification and fraud-risk analysis in Rwanda. "
        "AI output is advisory, uses synthetic/demo data, and requires human review. "
        "This system does not legally determine ownership."
    ),
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_routers = [
    auth_router,
    users_router,
    dashboard_router,
    parcels_router,
    owners_router,
    transactions_router,
    verification_router,
    risk_router,
    cases_router,
    audit_router,
    reports_router,
]
for router in api_routers:
    app.include_router(router, prefix="/api")


@app.exception_handler(Exception)
def unhandled_error(_request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    return JSONResponse(status_code=500, content={"detail": "An unexpected server error occurred."})


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok", "service": "landguard-ai"}


@app.get("/")
def root() -> dict:
    return {
        "message": "LandGuard AI: An AI-Powered Land Transaction Verification and Fraud Risk Detection System",
        "status": "ready",
        "docs": "/docs",
        "note": "This prototype uses synthetic/demo data for academic development and testing. It is not an official government system.",
    }
