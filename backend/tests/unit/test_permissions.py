import pytest

from app.domain.roles import Action, Resource, Role
from app.infra.casbin import can


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
    assert can(Role.ADMIN, action, resource)


@pytest.mark.parametrize(
    ("action", "resource"),
    [
        (Action.READ, Resource.BATCHES),
        (Action.READ, Resource.PREDICTIONS),
        (Action.REVIEW, Resource.PREDICTIONS),
        (Action.RELABEL, Resource.PREDICTIONS),
    ],
)
def test_reviewer_baseline_permissions(action: Action, resource: Resource) -> None:
    assert can(Role.REVIEWER, action, resource)


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
    assert not can(Role.REVIEWER, action, resource)


@pytest.mark.parametrize(
    "resource",
    [
        Resource.BATCHES,
        Resource.PREDICTIONS,
        Resource.AUDIT_LOGS,
    ],
)
def test_auditor_can_read_allowed_resources(resource: Resource) -> None:
    assert can(Role.AUDITOR, Action.READ, resource)


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
    assert not can(Role.AUDITOR, action, resource)


def test_unknown_role_is_denied_by_default() -> None:
    assert not can("operator", Action.READ, Resource.BATCHES)


def test_unknown_action_is_denied_by_default() -> None:
    assert not can(Role.ADMIN, "export", Resource.PREDICTIONS)


def test_unknown_resource_is_denied_by_default() -> None:
    assert not can(Role.ADMIN, Action.READ, "documents")


def test_multiple_roles_receive_union_of_allowed_permissions() -> None:
    assert can([Role.REVIEWER, Role.AUDITOR], Action.READ, Resource.AUDIT_LOGS)
    assert can([Role.REVIEWER, Role.AUDITOR], Action.RELABEL, Resource.PREDICTIONS)
    assert not can([Role.REVIEWER, Role.AUDITOR], Action.MANAGE, Resource.USERS)

