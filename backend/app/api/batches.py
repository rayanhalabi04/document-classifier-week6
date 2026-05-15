import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_permission
from app.domain.batches import BatchRead
from app.domain.roles import Action, Resource
from app.infra.db import get_session
from app.repositories.batches import BatchRepository

router = APIRouter(prefix="/batches", tags=["batches"])


@router.get("", response_model=list[BatchRead])
def list_batches(
    _user=Depends(require_permission(Resource.BATCHES, Action.READ)),
    session: Session = Depends(get_session),
) -> list[BatchRead]:
    return BatchRepository(session).list()


@router.get("/{batch_id}", response_model=BatchRead)
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
    return batch
