from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI

from app.api import audit, auth, batches, health, predictions, roles, users
from app.db.session import SessionFactory, engine
from app.infra.cache import init_cache
from app.services.auth import load_jwt_secret
from app.services.startup_authorization import validate_authorization_startup
from app.services.startup_validation import run_api_readiness_checks
from fastapi_cache import FastAPICache

logger = logging.getLogger(__name__)


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

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(roles.router)
    app.include_router(batches.router)
    app.include_router(predictions.router)
    app.include_router(audit.router)

    return app


app = create_app()
