"""Casbin RBAC enforcer backed by PostgreSQL and synchronized via Redis pub/sub.

Policy changes (assign_role, remove_role, etc.) are published to a Redis
channel so every API worker and background process reloads the latest policy
within milliseconds — no polling, no stale reads in multi-worker deployments.
"""

from __future__ import annotations

import json
from app.infra.logging import get_logger
import threading
import time
from functools import lru_cache
from pathlib import Path

import casbin
import casbin_sqlalchemy_adapter
from sqlalchemy.engine import Engine

from app.db.models import CasbinRule
from app.db.session import engine as default_engine
from app.domain.roles import Action, Resource, Role

logger = get_logger(__name__)

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

REDIS_POLICY_CHANNEL = "casbin:policy-changed"

# Set by the pub/sub listener thread when another process mutates policy.
# Checked and cleared by can() on the main thread before every enforce().
_policy_stale = threading.Event()


# ── Enforcer lifecycle ────────────────────────────────────────────


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


def clear_enforcer_cache() -> None:
    get_enforcer.cache_clear()


# ── Redis pub/sub policy sync ─────────────────────────────────────


def spawn_policy_listener() -> None:
    """Start a daemon thread that reloads policy on Redis pub/sub messages.

    Call once per process at startup.  The thread sets _policy_stale so the
    main thread reloads the enforcer safely inside can() — no cross-thread
    Casbin calls.
    """
    from app.infra.redis import get_redis_client

    client = get_redis_client()
    pubsub = client.pubsub()
    pubsub.subscribe(REDIS_POLICY_CHANNEL)

    thread = threading.Thread(
        target=_listen,
        args=(pubsub,),
        daemon=True,
        name="casbin-policy-listener",
    )
    thread.start()
    logger.info("Casbin policy listener started on channel '%s'", REDIS_POLICY_CHANNEL)


def _listen(pubsub) -> None:
    """Blocking listener loop — runs on the daemon thread."""
    try:
        for message in pubsub.listen():
            if message.get("type") == "message":
                _policy_stale.set()
    except Exception:
        logger.warning(
            "Casbin policy listener disconnected — will retry on next message"
        )


def _notify_policy_change() -> None:
    """Publish a policy-change event so all processes reload."""
    from app.infra.redis import get_redis_client

    try:
        get_redis_client().publish(
            REDIS_POLICY_CHANNEL,
            json.dumps({"ts": time.time()}),
        )
    except Exception:
        pass


# ── Authorization primitives ──────────────────────────────────────


def can(user_id: str, resource: Resource | str, action: Action | str) -> bool:
    """Check permission. Reloads policy if another process changed it."""
    if _policy_stale.is_set():
        reload_enforcer()
        _policy_stale.clear()
    return bool(
        get_enforcer().enforce(str(user_id), str(resource), str(action))
    )


def assign_role(user_id: str, role: Role | str) -> bool:
    enforcer = get_enforcer()
    reload_enforcer()
    result = bool(enforcer.add_role_for_user(str(user_id), str(role)))
    _notify_policy_change()
    return result


def remove_role(user_id: str, role: Role | str) -> bool:
    enforcer = get_enforcer()
    reload_enforcer()
    result = bool(enforcer.delete_role_for_user(str(user_id), str(role)))
    _notify_policy_change()
    return result


def remove_roles_for_user(user_id: str) -> bool:
    enforcer = get_enforcer()
    reload_enforcer()
    result = bool(enforcer.delete_roles_for_user(str(user_id)))
    _notify_policy_change()
    return result


def get_roles_for_user(user_id: str) -> list[str]:
    return list(get_enforcer().get_roles_for_user(str(user_id)))


def seed_baseline_policies() -> int:
    """Insert baseline role permissions if missing. Returns rows added."""
    enforcer = get_enforcer()
    reload_enforcer()
    added = 0
    for role, resource, action in sorted(BASELINE_POLICIES):
        if enforcer.add_policy(str(role), str(resource), str(action)):
            added += 1
    if added > 0:
        _notify_policy_change()
    return added


def baseline_policy_tuples() -> tuple[tuple[str, str, str], ...]:
    return tuple(
        sorted(
            (str(role), str(resource), str(action))
            for role, resource, action in BASELINE_POLICIES
        )
    )
