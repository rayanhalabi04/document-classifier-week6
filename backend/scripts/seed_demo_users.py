"""Seed a set of demo users covering every role combination.

Creates one user per role plus a no-roles account, so the frontend can be
exercised end-to-end without hand-assigning roles through the API.

All users get the same password (override via DEMO_PASSWORD env var).
Idempotent — skips any user whose email already exists, and tops up any
missing role assignments for users that already exist.

Usage:
    python scripts/seed_demo_users.py
"""

from __future__ import annotations

import os
import uuid

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import RoleAssignment, User
from app.db.session import SessionFactory
from app.infra.authz import casbin_enforcer

DEFAULT_PASSWORD = os.environ.get("DEMO_PASSWORD", "demo1234")

# (email, roles) — roles is a list because some accounts may carry several.
DEMO_USERS: list[tuple[str, list[str]]] = [
    ("admin@example.com", ["admin"]),
    ("reviewer@example.com", ["reviewer"]),
    ("auditor@example.com", ["auditor"]),
    ("super@example.com", ["admin", "reviewer", "auditor"]),
    ("noroles@example.com", []),
]


def _ensure_user(session: Session, email: str, hashed_password: str) -> User:
    existing = session.execute(
        select(User).where(User.email == email)
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    user = User(
        id=uuid.uuid4(),
        email=email,
        hashed_password=hashed_password,
        is_active=True,
        is_verified=True,
    )
    session.add(user)
    session.flush()
    return user


def _ensure_role(session: Session, user_id: uuid.UUID, role: str) -> bool:
    """Add `role` to the user if not already active. Returns True if added."""
    existing = session.execute(
        select(RoleAssignment).where(
            RoleAssignment.user_id == user_id,
            RoleAssignment.role == role,
            RoleAssignment.revoked_at.is_(None),
        )
    ).scalar_one_or_none()
    if existing is not None:
        return False
    session.add(
        RoleAssignment(
            id=uuid.uuid4(),
            user_id=user_id,
            role=role,
            assigned_by_user_id=user_id,  # self-assigned at bootstrap
        )
    )
    return True


def main() -> None:
    pwd_context = CryptContext(schemes=["bcrypt"])
    hashed = pwd_context.hash(DEFAULT_PASSWORD)

    summary: list[str] = []
    session = SessionFactory()
    try:
        for email, roles in DEMO_USERS:
            user = _ensure_user(session, email, hashed)
            added_roles: list[str] = []
            for role in roles:
                if _ensure_role(session, user.id, role):
                    added_roles.append(role)
            # Always sync Casbin grouping rules — the SQL row alone is invisible
            # to the enforcer, so every role on every user must be registered
            # via casbin_enforcer.assign_role (idempotent).
            for role in roles:
                casbin_enforcer.assign_role(str(user.id), role)
            if added_roles:
                summary.append(f"  {email}: +{', '.join(added_roles)}")
            else:
                summary.append(f"  {email}: already had {roles or 'no roles'}")
        session.commit()
    finally:
        session.close()

    print("Seeded demo users (password = " + DEFAULT_PASSWORD + ")")
    print("\n".join(summary))


if __name__ == "__main__":
    main()
