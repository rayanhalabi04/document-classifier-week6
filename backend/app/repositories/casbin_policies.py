from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import CasbinRule


class CasbinPolicyRepository:
    """SQL-only access for Casbin policy storage."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def count(self) -> int:
        stmt = select(func.count()).select_from(CasbinRule)
        return self._session.execute(stmt).scalar_one()

    def has_policy(self, ptype: str, v0: str, v1: str, v2: str) -> bool:
        stmt = select(CasbinRule.id).where(
            CasbinRule.ptype == ptype,
            CasbinRule.v0 == v0,
            CasbinRule.v1 == v1,
            CasbinRule.v2 == v2,
        )
        return self._session.execute(stmt).scalar_one_or_none() is not None
