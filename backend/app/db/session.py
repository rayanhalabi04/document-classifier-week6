"""SQLAlchemy engine and session factory.

The engine is created once at import time using DATABASE_URL from the environment.
Workers and services use SessionFactory directly. The API uses the get_session
dependency from app.infra.db for request-scoped sessions.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

DATABASE_URL = settings.database_url

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    connect_args={
        "connect_timeout": settings.pg_connect_timeout,
        "options": f"-c statement_timeout={settings.pg_statement_timeout_ms}",
    },
)

SessionFactory: sessionmaker[Session] = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,  # keep objects usable after commit
)
