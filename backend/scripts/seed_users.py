"""Seed initial admin user for local development.

Reads ADMIN_EMAIL and ADMIN_PASSWORD from environment (with defaults).
Idempotent — skips if the admin user already exists. Uses direct
SQLAlchemy INSERT (not RoleManagement service) since this is a
bootstrap tool that runs before any API requests are possible.

Usage:
    python scripts/seed_users.py
"""

from __future__ import annotations

import os
import uuid

from passlib.context import CryptContext
from sqlalchemy import select

from app.db.models import RoleAssignment, User
from app.db.session import SessionFactory

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin")


def main() -> None:
    """Create the initial admin user if it does not already exist."""
    pwd_context = CryptContext(schemes=["bcrypt"])
    session = SessionFactory()

    try:
        existing = session.execute(
            select(User).where(User.email == ADMIN_EMAIL)
        ).scalar_one_or_none()

        if existing is not None:
            print(f"Admin user already exists: {ADMIN_EMAIL}")
            return

        user = User(
            id=uuid.uuid4(),
            email=ADMIN_EMAIL,
            hashed_password=pwd_context.hash(ADMIN_PASSWORD),
            is_active=True,
            is_verified=True,
        )
        session.add(user)
        session.flush()

        role = RoleAssignment(
            id=uuid.uuid4(),
            user_id=user.id,
            role="admin",
            assigned_by_user_id=user.id,
        )
        session.add(role)
        session.commit()

        # Sync the role assignment to Casbin so authorization works
        from app.infra.authz.casbin_enforcer import assign_role
        assign_role(str(user.id), "admin")

        print(f"Created admin user: {ADMIN_EMAIL}")
        print("  Role: admin")
        print(f"  Password: {ADMIN_PASSWORD}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
