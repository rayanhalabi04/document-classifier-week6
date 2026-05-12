from sqlalchemy.orm import Session

from app.domain.errors import StartupValidationError
from app.infra.authz import casbin_enforcer
from app.repositories.casbin_policies import CasbinPolicyRepository


def assert_policy_table_not_empty(session: Session) -> None:
    """Fail loudly if the API would start without persisted Casbin policies."""
    repo = CasbinPolicyRepository(session)
    if repo.count() == 0:
        raise StartupValidationError(
            "Casbin policy table is empty. Seed baseline RBAC policies before "
            "starting the API."
        )


def assert_baseline_policies_present(session: Session) -> None:
    """Ensure the required baseline role policies are present in Casbin storage."""
    repo = CasbinPolicyRepository(session)
    missing = [
        (role, resource, action)
        for role, resource, action in casbin_enforcer.baseline_policy_tuples()
        if not repo.has_policy("p", role, resource, action)
    ]
    if missing:
        raise StartupValidationError(
            "Casbin policy table is missing baseline RBAC policies: "
            + ", ".join(
                f"{role}:{resource}:{action}" for role, resource, action in missing
            )
        )


def validate_authorization_startup(session: Session) -> None:
    assert_policy_table_not_empty(session)
    assert_baseline_policies_present(session)
    casbin_enforcer.reload_enforcer()
