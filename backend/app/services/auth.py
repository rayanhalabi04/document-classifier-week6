"""fastapi-users authentication setup.

This module owns auth wiring so API routers can stay HTTP-only. SQL access goes
through UserRepository and JWT signing material comes from Vault.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator, Generator
from typing import Any, Optional

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin, schemas
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)
from fastapi_users.db import BaseUserDatabase
from sqlalchemy.orm import Session

from app.db.models import User
from app.infra.db import get_session
from app.infra.vault import VaultAdapter
from app.repositories.users import UserRepository


JWT_LIFETIME_SECONDS = 60 * 60
_jwt_secret: str | None = None


class UserRead(schemas.BaseUser[uuid.UUID]):
    """Public user representation returned by auth endpoints."""


class UserCreate(schemas.BaseUserCreate):
    """Email/password registration payload."""


class UserUpdate(schemas.BaseUserUpdate):
    """User update payload for fastapi-users compatibility."""


class SyncUserDatabase(BaseUserDatabase[User, uuid.UUID]):
    """fastapi-users database adapter backed by the sync repository layer."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._users = UserRepository(session)

    async def get(self, id: uuid.UUID) -> Optional[User]:
        return self._users.get_by_id(id)

    async def get_by_email(self, email: str) -> Optional[User]:
        return self._users.get_by_email(email)

    async def get_by_oauth_account(
        self,
        oauth: str,
        account_id: str,
    ) -> Optional[User]:
        return None

    async def create(self, create_dict: dict[str, Any]) -> User:
        user = User(**create_dict)
        self._users.create(user)
        self._session.commit()
        return user

    async def update(self, user: User, update_dict: dict[str, Any]) -> User:
        for field, value in update_dict.items():
            setattr(user, field, value)
        self._users.update(user)
        self._session.commit()
        return user

    async def delete(self, user: User) -> None:
        self._users.delete(user)
        self._session.commit()

    async def add_oauth_account(
        self,
        user: User,
        create_dict: dict[str, Any],
    ) -> User:
        return user

    async def update_oauth_account(
        self,
        user: User,
        oauth_account: Any,
        update_dict: dict[str, Any],
    ) -> User:
        return user


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    """fastapi-users manager for local email/password accounts."""

    @property
    def reset_password_token_secret(self) -> str:
        return get_jwt_secret()

    @property
    def verification_token_secret(self) -> str:
        return get_jwt_secret()


def load_jwt_secret() -> str:
    """Resolve and cache the JWT signing secret from Vault."""
    global _jwt_secret
    _jwt_secret = VaultAdapter().read_secret("jwt", "secret")
    return _jwt_secret


def get_jwt_secret() -> str:
    """Return the cached JWT signing secret, loading it from Vault if needed."""
    if _jwt_secret is None:
        return load_jwt_secret()
    return _jwt_secret


def get_user_db(
    session: Session = Depends(get_session),
) -> Generator[SyncUserDatabase, None, None]:
    yield SyncUserDatabase(session)


async def get_user_manager(
    user_db: SyncUserDatabase = Depends(get_user_db),
) -> AsyncGenerator[UserManager, None]:
    yield UserManager(user_db)


bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/jwt/login")


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=get_jwt_secret(), lifetime_seconds=JWT_LIFETIME_SECONDS)


auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

fastapi_users = FastAPIUsers[User, uuid.UUID](
    get_user_manager,
    [auth_backend],
)

_fastapi_current_active_user = fastapi_users.current_user(active=True)


async def current_active_user(
    _token: str = Depends(oauth2_scheme),
    user: User = Depends(_fastapi_current_active_user),
) -> User:
    """Require a bearer token before invoking fastapi-users JWT validation."""
    return user
