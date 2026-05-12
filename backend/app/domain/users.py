import uuid

from pydantic import BaseModel


class CurrentUserProfile(BaseModel):
    """Authenticated user profile returned by GET /users/me."""

    id: uuid.UUID
    email: str
    is_active: bool
    roles: list[str]
