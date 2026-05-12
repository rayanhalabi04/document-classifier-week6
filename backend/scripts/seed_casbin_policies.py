from app.db.session import SessionFactory
from app.infra.authz.casbin_enforcer import seed_baseline_policies
from app.services.startup_authorization import assert_baseline_policies_present


def main() -> None:
    added = seed_baseline_policies()
    with SessionFactory() as session:
        assert_baseline_policies_present(session)
    print(f"Seeded Casbin baseline policies. Added {added} new policy rows.")


if __name__ == "__main__":
    main()
