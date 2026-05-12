from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import (
    audit,
    auth,
    batches,
    health,
    predictions,
    roles,
    users,
)
from app.services.auth import load_jwt_secret
from app.db.session import SessionFactory
from app.services.startup_authorization import validate_authorization_startup


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    load_jwt_secret()
    with SessionFactory() as session:
        validate_authorization_startup(session)
    yield


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
