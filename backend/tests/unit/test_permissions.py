import pytest

from app.domain.roles import Action, Resource, Role
from app.infra.casbin import baseline_policy_tuples


def _baseline_allows(
    role: Role | str,
    resource: Resource | str,
    action: Action | str,
) -> bool:
    return (str(role), str(resource), str(action)) in baseline_policy_tuples()


@pytest.mark.parametrize(
    ("action", "resource"),
    [
        (Action.MANAGE, Resource.USERS),
        (Action.MANAGE, Resource.ROLES),
        (Action.READ, Resource.AUDIT_LOGS),
        (Action.READ, Resource.BATCHES),
        (Action.READ, Resource.PREDICTIONS),
    ],
)
def test_admin_baseline_permissions(action: Action, resource: Resource) -> None:
    assert _baseline_allows(Role.ADMIN, resource, action)


@pytest.mark.parametrize(
    ("action", "resource"),
    [
        (Action.READ, Resource.BATCHES),
        (Action.READ, Resource.PREDICTIONS),
        (Action.RELABEL, Resource.PREDICTIONS),
    ],
)
def test_reviewer_baseline_permissions(action: Action, resource: Resource) -> None:
    assert _baseline_allows(Role.REVIEWER, resource, action)


@pytest.mark.parametrize(
    ("action", "resource"),
    [
        (Action.MANAGE, Resource.USERS),
        (Action.MANAGE, Resource.ROLES),
        (Action.READ, Resource.AUDIT_LOGS),
    ],
)
def test_reviewer_denied_admin_and_audit_permissions(
    action: Action, resource: Resource
) -> None:
    assert not _baseline_allows(Role.REVIEWER, resource, action)


@pytest.mark.parametrize(
    "resource",
    [
        Resource.BATCHES,
        Resource.PREDICTIONS,
        Resource.AUDIT_LOGS,
    ],
)
def test_auditor_can_read_allowed_resources(resource: Resource) -> None:
    assert _baseline_allows(Role.AUDITOR, resource, Action.READ)


@pytest.mark.parametrize(
    ("action", "resource"),
    [
        (Action.MANAGE, Resource.USERS),
        (Action.MANAGE, Resource.ROLES),
        (Action.REVIEW, Resource.PREDICTIONS),
        (Action.RELABEL, Resource.PREDICTIONS),
    ],
)
def test_auditor_cannot_write_or_change_anything(
    action: Action, resource: Resource
) -> None:
    assert not _baseline_allows(Role.AUDITOR, resource, action)


def test_unknown_role_is_denied_by_default() -> None:
    assert not _baseline_allows("operator", Resource.BATCHES, Action.READ)


def test_unknown_action_is_denied_by_default() -> None:
    assert not _baseline_allows(Role.ADMIN, Resource.PREDICTIONS, "export")


def test_unknown_resource_is_denied_by_default() -> None:
    assert not _baseline_allows(Role.ADMIN, "documents", Action.READ)


def test_multiple_roles_receive_union_of_allowed_permissions() -> None:
    roles = [Role.REVIEWER, Role.AUDITOR]

    assert any(
        _baseline_allows(role, Resource.AUDIT_LOGS, Action.READ) for role in roles
    )
    assert any(
        _baseline_allows(role, Resource.PREDICTIONS, Action.RELABEL) for role in roles
    )
    assert not any(
        _baseline_allows(role, Resource.USERS, Action.MANAGE) for role in roles
    )
