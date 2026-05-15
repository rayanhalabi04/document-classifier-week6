from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.db.session import SessionFactory
from app.services.startup_validation import run_api_readiness_checks

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
def health_live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
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
