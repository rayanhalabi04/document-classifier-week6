from typing import Any

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.db.session import SessionFactory
from app.services.startup_validation import run_api_readiness_checks

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def health_live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def health_ready() -> Any:
    failures = run_api_readiness_checks(SessionFactory)
    if not failures:
        return {"status": "ready"}

    content: dict[str, Any] = {
        "status": "not_ready",
        "checks": failures,
        "message": "One or more readiness checks failed.",
    }
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=content,
    )
