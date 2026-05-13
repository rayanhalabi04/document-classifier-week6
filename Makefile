.PHONY: setup up down reset test test-live test-all clean logs ps seed seed-users seed-all

# ── First-time setup ──────────────────────────────────────────────
setup:
	@echo "==> Installing Git LFS assets ..."
	git lfs pull
	@echo "==> Creating .env from example (if missing) ..."
	cp -n backend/.env.example backend/.env 2>/dev/null || true
	@echo "==> Starting all services ..."
	docker compose up -d
	@echo "==> Waiting for services to be ready ..."
	@sleep 10
	@echo "==> Running Alembic migrations ..."
	docker compose run --rm api alembic upgrade head
	@echo "==> Seeding Vault secrets ..."
	cd backend && .venv/bin/python scripts/seed_vault.py
	@echo "==> Seeding model metadata ..."
	docker compose run --rm api python scripts/seed_model_metadata.py
	@echo "==> Seeding admin user ..."
	docker compose run --rm api python scripts/seed_users.py
	@echo "==> Seeding Casbin policies ..."
	docker compose run --rm api python scripts/seed_casbin_policies.py
	@echo ""
	@echo "Setup complete — http://localhost:8000"
	@echo "Login: admin@example.com / admin"

# ── Day-to-day ────────────────────────────────────────────────────
up:
	docker compose up -d

down:
	docker compose down

ps:
	docker compose ps

logs:
	docker compose logs -f

# ── Testing ───────────────────────────────────────────────────────
test:
	cd backend && .venv/bin/python -m pytest tests/unit/ -v

test-live:
	cd backend && .venv/bin/python -m pytest tests/integration/test_adapters_live.py -v -s

test-all:
	cd backend && .venv/bin/python -m pytest tests/ -v

# ── Teardown / reset ──────────────────────────────────────────────
clean:
	docker compose down --volumes --remove-orphans
	rm -rf sftp_drop/*
	@echo "Cleaned. Run 'make setup' to start fresh."

reset:
	docker compose down --volumes --remove-orphans
	rm -rf sftp_drop/*
	docker compose up -d
	@sleep 8
	cd backend && .venv/bin/python scripts/seed_vault.py
	@echo "Reset complete."

# ── Utilities ─────────────────────────────────────────────────────
seed:
	@echo "Seeding Vault secrets ..."
	cd backend && .venv/bin/python scripts/seed_vault.py

seed-users:
	docker compose run --rm api python scripts/seed_users.py

seed-all:
	@echo "Seeding everything ..."
	docker compose run --rm api python scripts/seed_model_metadata.py
	docker compose run --rm api python scripts/seed_users.py
	docker compose run --rm api python scripts/seed_casbin_policies.py

shell:
	cd backend && .venv/bin/python
