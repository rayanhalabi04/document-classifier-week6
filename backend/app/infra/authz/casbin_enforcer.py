from functools import lru_cache
from pathlib import Path

import casbin
import casbin_sqlalchemy_adapter
from sqlalchemy.engine import Engine

from app.db.models import CasbinRule
from app.db.session import engine as default_engine
from app.domain.roles import Action, Resource, Role

MODEL_PATH = Path(__file__).with_name("rbac_model.conf")

Policy = tuple[Role, Resource, Action]

BASELINE_POLICIES: frozenset[Policy] = frozenset(
    {
        (Role.ADMIN, Resource.USERS, Action.MANAGE),
        (Role.ADMIN, Resource.ROLES, Action.MANAGE),
        (Role.ADMIN, Resource.AUDIT_LOGS, Action.READ),
        (Role.ADMIN, Resource.BATCHES, Action.READ),
        (Role.ADMIN, Resource.PREDICTIONS, Action.READ),
        (Role.ADMIN, Resource.PREDICTIONS, Action.RELABEL),
        (Role.REVIEWER, Resource.BATCHES, Action.READ),
        (Role.REVIEWER, Resource.PREDICTIONS, Action.READ),
        (Role.REVIEWER, Resource.PREDICTIONS, Action.RELABEL),
        (Role.AUDITOR, Resource.BATCHES, Action.READ),
        (Role.AUDITOR, Resource.PREDICTIONS, Action.READ),
        (Role.AUDITOR, Resource.AUDIT_LOGS, Action.READ),
    }
)


@lru_cache(maxsize=1)
def get_enforcer() -> casbin.Enforcer:
    """Return the process-wide DB-backed Casbin enforcer."""
    return create_enforcer(default_engine)


def create_enforcer(engine: Engine) -> casbin.Enforcer:
    """Create and load a Casbin enforcer backed by SQLAlchemy storage."""
    adapter = casbin_sqlalchemy_adapter.Adapter(
        engine,
        db_class=CasbinRule,
        create_all_models=False,
    )
    enforcer = casbin.Enforcer(str(MODEL_PATH), adapter)
    enforcer.load_policy()
    return enforcer


def reload_enforcer() -> None:
    get_enforcer().load_policy()


def can(user_id: str, resource: Resource | str, action: Action | str) -> bool:
    enforcer = get_enforcer()
    return bool(enforcer.enforce(str(user_id), str(resource), str(action)))


def assign_role(user_id: str, role: Role | str) -> bool:
    enforcer = get_enforcer()
    reload_enforcer()
    return bool(enforcer.add_role_for_user(str(user_id), str(role)))


def remove_role(user_id: str, role: Role | str) -> bool:
    enforcer = get_enforcer()
    reload_enforcer()
    return bool(enforcer.delete_role_for_user(str(user_id), str(role)))


def remove_roles_for_user(user_id: str) -> bool:
    enforcer = get_enforcer()
    reload_enforcer()
    return bool(enforcer.delete_roles_for_user(str(user_id)))


def get_roles_for_user(user_id: str) -> list[str]:
    enforcer = get_enforcer()
    return list(enforcer.get_roles_for_user(str(user_id)))


def seed_baseline_policies() -> int:
    """Insert baseline role permissions if missing. Returns rows added."""
    enforcer = get_enforcer()
    reload_enforcer()
    added = 0
    for role, resource, action in sorted(BASELINE_POLICIES):
        if enforcer.add_policy(str(role), str(resource), str(action)):
            added += 1
    return added


def baseline_policy_tuples() -> tuple[tuple[str, str, str], ...]:
    return tuple(
        sorted(
            (str(role), str(resource), str(action))
            for role, resource, action in BASELINE_POLICIES
        )
    )


def clear_enforcer_cache() -> None:
    get_enforcer.cache_clear()
