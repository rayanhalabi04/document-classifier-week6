import uuid
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import CasbinRule, RoleAssignment
from app.domain.errors import ReviewNotEligible, StartupValidationError
from app.domain.roles import Action, Resource, Role
from app.infra.authz import casbin_enforcer
from app.services import prediction_review, role_management
from app.services.startup_authorization import validate_authorization_startup


def _sqlite_enforcer():
    engine = create_engine("sqlite:///:memory:")
    CasbinRule.__table__.create(engine)
    enforcer = casbin_enforcer.create_enforcer(engine)
    for role, resource, action in casbin_enforcer.baseline_policy_tuples():
        enforcer.add_policy(role, resource, action)
    return engine, enforcer


def test_baseline_policies_are_enforced_by_casbin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, enforcer = _sqlite_enforcer()
    admin_id = str(uuid.uuid4())
    reviewer_id = str(uuid.uuid4())
    auditor_id = str(uuid.uuid4())

    enforcer.add_role_for_user(admin_id, Role.ADMIN)
    enforcer.add_role_for_user(reviewer_id, Role.REVIEWER)
    enforcer.add_role_for_user(auditor_id, Role.AUDITOR)
    monkeypatch.setattr(casbin_enforcer, "get_enforcer", lambda: enforcer)

    assert casbin_enforcer.can(admin_id, Resource.ROLES, Action.MANAGE)
    assert casbin_enforcer.can(admin_id, Resource.AUDIT_LOGS, Action.READ)
    assert casbin_enforcer.can(reviewer_id, Resource.BATCHES, Action.READ)
    assert casbin_enforcer.can(reviewer_id, Resource.PREDICTIONS, Action.RELABEL)
    assert casbin_enforcer.can(auditor_id, Resource.AUDIT_LOGS, Action.READ)
    assert not casbin_enforcer.can(auditor_id, Resource.PREDICTIONS, Action.RELABEL)
    assert not casbin_enforcer.can(auditor_id, Resource.ROLES, Action.MANAGE)


def test_role_change_updates_casbin_permissions_without_new_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, enforcer = _sqlite_enforcer()
    user_id = str(uuid.uuid4())
    enforcer.add_role_for_user(user_id, Role.AUDITOR)
    monkeypatch.setattr(casbin_enforcer, "get_enforcer", lambda: enforcer)

    assert casbin_enforcer.can(user_id, Resource.AUDIT_LOGS, Action.READ)
    assert not casbin_enforcer.can(user_id, Resource.PREDICTIONS, Action.RELABEL)

    casbin_enforcer.remove_roles_for_user(user_id)
    casbin_enforcer.assign_role(user_id, Role.REVIEWER)

    assert casbin_enforcer.get_roles_for_user(user_id) == [Role.REVIEWER]
    assert casbin_enforcer.can(user_id, Resource.PREDICTIONS, Action.RELABEL)
    assert not casbin_enforcer.can(user_id, Resource.AUDIT_LOGS, Action.READ)


class _FakePredictionRepo:
    def __init__(self, prediction):
        self.prediction = prediction

    def get_by_id(self, prediction_id):
        return self.prediction

    def update(self, prediction):
        return prediction


class _FakeAuthz:
    def __init__(self, *, is_admin: bool = False):
        self.is_admin = is_admin

    def require_permission(self, user_id, resource, action):
        return None

    def can(self, user_id, resource, action):
        return self.is_admin


@pytest.mark.parametrize("confidence", [0.1, 0.699])
def test_reviewer_can_relabel_prediction_below_confidence_threshold(
    confidence: float,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prediction = SimpleNamespace(
        id=uuid.uuid4(),
        predicted_class="letter",
        top1_confidence=confidence,
        review_eligible=True,
        review_label=None,
        reviewed_by_user_id=None,
        reviewed_at=None,
    )
    monkeypatch.setattr(
        prediction_review,
        "PredictionRepository",
        lambda session: _FakePredictionRepo(prediction),
    )
    monkeypatch.setattr(prediction_review, "AuditLogService", lambda session: Mock())
    monkeypatch.setattr(
        prediction_review,
        "AuthorizationService",
        lambda: _FakeAuthz(is_admin=False),
    )
    monkeypatch.setattr(prediction_review, "invalidate_after_relabel", Mock())
    session = Mock()

    result = prediction_review.PredictionReviewService(session).relabel(
        prediction_id=prediction.id,
        review_label="memo",
        reviewer_user_id=uuid.uuid4(),
        batch_id=uuid.uuid4(),
    )

    assert result.review_label == "memo"
    session.commit.assert_called_once()


def test_reviewer_cannot_relabel_prediction_at_or_above_confidence_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prediction = SimpleNamespace(
        id=uuid.uuid4(),
        predicted_class="letter",
        top1_confidence=0.7,
        review_eligible=False,
        review_label=None,
        reviewed_by_user_id=None,
        reviewed_at=None,
    )
    monkeypatch.setattr(
        prediction_review,
        "PredictionRepository",
        lambda session: _FakePredictionRepo(prediction),
    )
    monkeypatch.setattr(prediction_review, "AuditLogService", lambda session: Mock())
    monkeypatch.setattr(
        prediction_review,
        "AuthorizationService",
        lambda: _FakeAuthz(is_admin=False),
    )

    with pytest.raises(ReviewNotEligible):
        prediction_review.PredictionReviewService(Mock()).relabel(
            prediction_id=prediction.id,
            review_label="memo",
            reviewer_user_id=uuid.uuid4(),
            batch_id=uuid.uuid4(),
        )


def test_admin_can_relabel_prediction_regardless_of_confidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prediction = SimpleNamespace(
        id=uuid.uuid4(),
        predicted_class="letter",
        top1_confidence=0.99,
        review_eligible=False,
        review_label=None,
        reviewed_by_user_id=None,
        reviewed_at=None,
    )
    monkeypatch.setattr(
        prediction_review,
        "PredictionRepository",
        lambda session: _FakePredictionRepo(prediction),
    )
    monkeypatch.setattr(prediction_review, "AuditLogService", lambda session: Mock())
    monkeypatch.setattr(
        prediction_review,
        "AuthorizationService",
        lambda: _FakeAuthz(is_admin=True),
    )
    monkeypatch.setattr(prediction_review, "invalidate_after_relabel", Mock())

    result = prediction_review.PredictionReviewService(Mock()).relabel(
        prediction_id=prediction.id,
        review_label="memo",
        reviewer_user_id=uuid.uuid4(),
        batch_id=uuid.uuid4(),
    )

    assert result.review_label == "memo"


def test_role_replacement_syncs_grouping_policy_audit_and_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target_user_id = uuid.uuid4()
    acting_admin_id = uuid.uuid4()
    existing_assignment = RoleAssignment(
        id=uuid.uuid4(),
        user_id=target_user_id,
        role=Role.AUDITOR,
        assigned_by_user_id=acting_admin_id,
    )
    roles_repo = Mock()
    roles_repo.get_active_roles.return_value = [existing_assignment]
    roles_repo.revoke_all_for_user.return_value = None
    roles_repo.create.side_effect = lambda assignment: assignment
    audit = Mock()
    cache = Mock()
    remove_roles = Mock()
    assign_role = Mock()

    monkeypatch.setattr(role_management, "RoleRepository", lambda session: roles_repo)
    monkeypatch.setattr(role_management, "AuditLogService", lambda session: audit)
    monkeypatch.setattr(
        role_management,
        "AuthorizationService",
        lambda: _FakeAuthz(is_admin=True),
    )
    monkeypatch.setattr(
        role_management.casbin_enforcer,
        "remove_roles_for_user",
        remove_roles,
    )
    monkeypatch.setattr(role_management.casbin_enforcer, "assign_role", assign_role)
    monkeypatch.setattr(role_management, "invalidate_user_roles", cache)

    assignments = role_management.RoleManagementService(Mock()).replace_roles(
        target_user_id=target_user_id,
        new_roles=[Role.REVIEWER],
        acting_admin_id=acting_admin_id,
    )

    assert [assignment.role for assignment in assignments] == [Role.REVIEWER]
    remove_roles.assert_called_once_with(str(target_user_id))
    assign_role.assert_called_once_with(str(target_user_id), Role.REVIEWER)
    audit.record.assert_called_once()
    cache.assert_called_once_with(target_user_id)


def test_startup_guard_fails_when_casbin_policy_table_is_empty() -> None:
    engine = create_engine("sqlite:///:memory:")
    CasbinRule.__table__.create(engine)
    Session = sessionmaker(bind=engine)

    with Session() as session, pytest.raises(StartupValidationError, match="empty"):
        validate_authorization_startup(session)
