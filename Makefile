.PHONY: setup up down reset test test-live test-all clean logs ps seed

# ── First-time setup ──────────────────────────────────────────────
setup:
	@echo "==> Installing Git LFS assets ..."
	git lfs pull
	@echo "==> Creating .env from example (if missing) ..."
	cp -n backend/.env.example backend/.env 2>/dev/null || true
	@echo "==> Starting all services ..."
	docker compose up -d
	@echo "==> Waiting for Vault to be ready ..."
	@sleep 8
	@echo "==> Seeding Vault secrets ..."
	cd backend && .venv/bin/python scripts/seed_vault.py
	@echo ""
	@echo "Setup complete. Run 'make ps' to check services."
	@echo "Once Member 2 finishes migrations, run: docker compose exec api alembic upgrade head"

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

shell:
	cd backend && .venv/bin/python
