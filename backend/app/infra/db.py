"""FastAPI database session dependency.

Routes declare `session: Session = Depends(get_session)` to receive a
request-scoped session that commits on success and rolls back on error.
Workers do not use this — they call SessionFactory directly.
"""

from collections.abc import Generator

from sqlalchemy.orm import Session

from app.db.session import SessionFactory


def get_session() -> Generator[Session, None, None]:
    """Yield a SQLAlchemy session for the duration of one API request.

    The session is committed by the service layer. This dependency rolls back
    on any unhandled exception and always closes the session on exit.
    """
    session = SessionFactory()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
