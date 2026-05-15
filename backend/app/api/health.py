from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.db.session import SessionFactory
from app.services.startup_validation import run_api_readiness_checks

router = APIRouter(prefix="/health", tags=["health"])


class HealthLiveResponse(BaseModel):
    status: str


class HealthReadyResponse(BaseModel):
    status: str
    checks: dict[str, str] | None = None
    message: str | None = None


@router.get("/live", response_model=HealthLiveResponse)
def health_live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", response_model=HealthReadyResponse)
def health_ready() -> JSONResponse:
    failures = run_api_readiness_checks(SessionFactory)
    if not failures:
        return JSONResponse(status_code=200, content={"status": "ready"})

    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "not_ready",
            "checks": failures,
            "message": "One or more readiness checks failed.",
        },
    )
