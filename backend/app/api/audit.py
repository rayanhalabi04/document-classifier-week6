import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import require_permission
from app.domain.audit import AuditEventRead
from app.domain.roles import Action, Resource
from app.infra.db import get_session
from app.services.audit_log import AuditLogService

router = APIRouter(prefix="/audit-events", tags=["audit"])


def get_audit_log_service(
    session: Session = Depends(get_session),
) -> AuditLogService:
    """Build the audit log service for API routes."""
    return AuditLogService(session)


@router.get("", response_model=list[AuditEventRead])
def list_audit_events(
    _user=Depends(require_permission(Resource.AUDIT_LOGS, Action.READ)),
    audit_service: AuditLogService = Depends(get_audit_log_service),
    actor_user_id: uuid.UUID | None = None,
    action: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[AuditEventRead]:
    return audit_service.list_events(
        actor_user_id=actor_user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        limit=limit,
        offset=offset,
    )
