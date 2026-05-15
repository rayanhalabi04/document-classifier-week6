from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi_cache import FastAPICache

from app.api import audit, auth, batches, health, predictions, roles, users
from app.db.session import SessionFactory, engine
from app.infra.cache import init_cache
from app.infra.logging import get_logger
from app.infra.authz.casbin_enforcer import spawn_policy_listener
from app.infra.rate_limiter import auth_rate_limit_middleware
from app.services.auth import load_jwt_secret
from app.services.startup_authorization import validate_authorization_startup
from app.services.startup_validation import run_api_readiness_checks

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    fail_fast = True
    try:
        logger.info("API starting — loading JWT secret...")
        load_jwt_secret()

        logger.info("Validating authorization policies...")
        with SessionFactory() as session:
            validate_authorization_startup(session)

        logger.info("Running full API readiness checks...")
        failures = run_api_readiness_checks(SessionFactory)
        if failures:
            raise RuntimeError(
                "API readiness checks failed:\n  "
                + "\n  ".join(f"{k}: {v}" for k, v in failures.items())
            )

        logger.info("Initializing cache backend...")
        await init_cache()

        logger.info("Starting Casbin policy listener...")
        spawn_policy_listener()

        fail_fast = False
        logger.info("API started successfully")
        yield
    finally:
        if not fail_fast:
            logger.info("API shutting down — cleaning up resources...")
        try:
            await FastAPICache.clear()
        except Exception:
            pass
        try:
            engine.dispose()
        except Exception:
            pass
        logger.info("API shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Document Classifier API",
        version="0.1.0-week6",
        description="Authenticated internal document classification service API.",
        lifespan=lifespan,
    )

    # ── Rate limiting ────────────────────────────────────────
    app.middleware("http")(auth_rate_limit_middleware)

    # ── Security headers ──────────────────────────────────────
    @app.middleware("http")
    async def add_security_headers(request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        return response

    # ── CORS ──────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Request logging ───────────────────────────────────────
    @app.middleware("http")
    async def log_requests(request: Request, call_next: Callable) -> Response:
        start = time.monotonic()
        response = await call_next(request)
        elapsed = time.monotonic() - start
        logger.info(
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            elapsed_ms=round(elapsed * 1000, 2),
        )
        return response

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(roles.router)
    app.include_router(batches.router)
    app.include_router(predictions.router)
    app.include_router(audit.router)

    # ── Prometheus metrics ────────────────────────────────────
    from prometheus_fastapi_instrumentator import Instrumentator
    Instrumentator().instrument(app).expose(app)

    return app


app = create_app()
