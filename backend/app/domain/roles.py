from enum import StrEnum


class Role(StrEnum):
    ADMIN = "admin"
    REVIEWER = "reviewer"
    AUDITOR = "auditor"


class Action(StrEnum):
    READ = "read"
    MANAGE = "manage"
    REVIEW = "review"
    RELABEL = "relabel"


class Resource(StrEnum):
    USERS = "users"
    ROLES = "roles"
    AUDIT_LOGS = "audit_logs"
    BATCHES = "batches"
    PREDICTIONS = "predictions"

