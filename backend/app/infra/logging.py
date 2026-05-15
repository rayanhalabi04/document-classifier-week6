"""Structured logging configuration.

Sets up structlog with JSON output for production and pretty console output
for local development. All log records include:
- timestamp, log level, logger name
- request_id  (set per API request via context var)
- job_id      (set per RQ job via context var)
- Safe contextual IDs: batch_id, document_id, prediction_id, user_id

Never log: passwords, tokens, secrets, file-system paths beyond filenames,
raw exception tracebacks in user-facing responses.
"""

import contextvars
import logging
from app.config import settings
import sys

import structlog

# Context variables — set at request/job boundary, read by all log calls
_request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default=""
)
_job_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("job_id", default="")


def set_request_id(request_id: str) -> None:
    """Bind request_id for the current async context (API middleware)."""
    _request_id_var.set(request_id)


def set_job_id(job_id: str) -> None:
    """Bind job_id for the current worker job."""
    _job_id_var.set(job_id)


def _add_context_ids(
    logger: logging.Logger,
    method: str,
    event_dict: structlog.types.EventDict,
) -> structlog.types.EventDict:
    """Inject request_id and job_id from context vars into every log record."""
    request_id = _request_id_var.get()
    job_id = _job_id_var.get()
    if request_id:
        event_dict["request_id"] = request_id
    if job_id:
        event_dict["job_id"] = job_id
    return event_dict


def configure_logging() -> None:
    """Configure structlog and stdlib logging.

    Call once at application startup (main.py and each worker entry point).
    Uses JSON renderer in production (LOG_FORMAT=json) and colored console
    output otherwise.
    """
    log_level_name = settings.log_level.upper()
    log_level = getattr(logging, log_level_name, logging.INFO)
    log_format = settings.log_format

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        _add_context_ids,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if log_format == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processor=renderer,
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    # Silence noisy third-party loggers
    for noisy in ("uvicorn.access", "sqlalchemy.engine", "alembic"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger bound to the given name.

    Usage:
        logger = get_logger(__name__)
        logger.info("document.ingested", document_id=str(doc.id))
    """
    return structlog.get_logger(name)
