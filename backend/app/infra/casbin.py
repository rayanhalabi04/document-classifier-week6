from collections.abc import Iterable

from app.domain.roles import Action, Resource, Role

Permission = tuple[Role, Action, Resource]

BASELINE_POLICIES: frozenset[Permission] = frozenset(
    {
        (Role.ADMIN, Action.MANAGE, Resource.USERS),
        (Role.ADMIN, Action.MANAGE, Resource.ROLES),
        (Role.ADMIN, Action.READ, Resource.AUDIT_LOGS),
        (Role.ADMIN, Action.READ, Resource.BATCHES),
        (Role.ADMIN, Action.READ, Resource.PREDICTIONS),
        (Role.REVIEWER, Action.READ, Resource.BATCHES),
        (Role.REVIEWER, Action.READ, Resource.PREDICTIONS),
        (Role.REVIEWER, Action.REVIEW, Resource.PREDICTIONS),
        (Role.REVIEWER, Action.RELABEL, Resource.PREDICTIONS),
        (Role.AUDITOR, Action.READ, Resource.BATCHES),
        (Role.AUDITOR, Action.READ, Resource.PREDICTIONS),
        (Role.AUDITOR, Action.READ, Resource.AUDIT_LOGS),
    }
)


def can(
    role: Role | str | Iterable[Role | str],
    action: Action | str,
    resource: Resource | str,
) -> bool:
    """Return whether the baseline in-memory policy allows this operation."""
    parsed_action = _parse_action(action)
    parsed_resource = _parse_resource(resource)

    if parsed_action is None or parsed_resource is None:
        return False

    return any(
        (parsed_role, parsed_action, parsed_resource) in BASELINE_POLICIES
        for parsed_role in _parse_roles(role)
    )


def _parse_roles(role: Role | str | Iterable[Role | str]) -> tuple[Role, ...]:
    if isinstance(role, (Role, str)):
        roles = (role,)
    else:
        roles = tuple(role)

    parsed_roles: list[Role] = []
    for candidate in roles:
        try:
            parsed_roles.append(Role(candidate))
        except ValueError:
            continue

    return tuple(parsed_roles)


def _parse_action(action: Action | str) -> Action | None:
    try:
        return Action(action)
    except ValueError:
        return None


def _parse_resource(resource: Resource | str) -> Resource | None:
    try:
        return Resource(resource)
    except ValueError:
        return None

