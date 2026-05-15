import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi_cache.decorator import cache
from sqlalchemy.orm import Session

from app.api.dependencies import require_permission
from app.db.models import Batch
from app.domain.batches import BatchRead
from app.domain.roles import Action, Resource
from app.infra.db import get_session
from app.repositories.batches import BatchRepository

router = APIRouter(prefix="/batches", tags=["batches"])


def _batch_to_read(batch: Batch) -> BatchRead:
    return BatchRead(
        id=batch.id,
        source=batch.source,
        status=str(batch.status) if batch.status else None,
        document_count=batch.document_count or 0,
        reviewable_count=batch.reviewable_count or 0,
        created_at=batch.created_at,
        updated_at=batch.updated_at,
        completed_at=batch.completed_at,
    )


@router.get("", response_model=list[BatchRead])
@cache(expire=60)
def list_batches(
    _user=Depends(require_permission(Resource.BATCHES, Action.READ)),
    session: Session = Depends(get_session),
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[BatchRead]:
    return [_batch_to_read(b) for b in BatchRepository(session).list(limit=limit, offset=offset)]


@router.get("/{batch_id}", response_model=BatchRead)
@cache(expire=60)
def get_batch(
    batch_id: uuid.UUID,
    _user=Depends(require_permission(Resource.BATCHES, Action.READ)),
    session: Session = Depends(get_session),
) -> BatchRead:
    batch = BatchRepository(session).get_by_id(batch_id)
    if batch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found.",
        )
    return _batch_to_read(batch)
