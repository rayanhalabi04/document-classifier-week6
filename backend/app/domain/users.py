import uuid
from datetime import datetime

from pydantic import BaseModel


class CurrentUserProfile(BaseModel):
    """Authenticated user profile returned by GET /users/me."""

    id: uuid.UUID
    email: str
    is_active: bool
    roles: list[str]


class AdminUserProfile(BaseModel):
    """Safe user representation returned by admin user-management endpoints."""

    id: uuid.UUID
    email: str
    is_active: bool
    is_verified: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None
    last_login_at: datetime | None = None
    roles: list[str]
