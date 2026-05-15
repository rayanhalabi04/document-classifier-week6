# Secrets Management — HashiCorp Vault

The Document Classifier stores all runtime credentials in **HashiCorp Vault** (KV v2).
No passwords, keys, or tokens are hardcoded in the application code or environment files
beyond the initial Vault bootstrap token.

---

## Vault Secret Map

Five secret paths cover every external dependency:

| Path | Keys | Used by |
|------|------|---------|
| `jwt` | `secret` | fastapi-users JWT token signing |
| `postgres` | `user`, `password`, `db` | SQLAlchemy + Alembic migrations |
| `minio` | `access_key`, `secret_key` | MinIO uploads/downloads for originals and overlays |
| `sftp` | `user`, `password`, `host`, `port` | Vendor SFTP drop folder (ingestion worker) |
| `redis` | `url` | RQ broker + fastapi-cache2 backend |

**13 keys total** across 5 paths. Any missing key blocks startup (see `app/infra/vault.py:28` —
`REQUIRED_SECRETS` dict defines the contract).

---

## How Secrets Flow

```
docker-compose.yml          .env / .env.example
─────────────────          ────────────────────
VAULT_DEV_ROOT_TOKEN_ID    VAULT_ADDR=http://vault:8200
  = root                     VAULT_TOKEN=root

       │                          │
       ▼                          ▼
┌─────────────┐    hvac    ┌──────────────────┐
│  Vault      │◄───────────│  app/infra/      │
│  dev server │  KV v2     │  vault.py        │
│  :8200      │            │                  │
│             │            │  VaultAdapter()  │
│  jwt/       │            │    .read_secret( │
│  postgres/  │            │      "jwt",      │
│  minio/     │            │      "secret"    │
│  sftp/      │            │    )             │
│  redis/     │            │                  │
└─────────────┘            └──────────────────┘
                                     │
                                     ▼
                            Runtime: JWT signing,
                            Postgres URL, MinIO
                            creds, SFTP auth
```

---

## Bootstrap (First-Time Setup)

Vault starts empty in dev mode. Run the seeder to populate all 5 paths:

```bash
# From repo root, with Docker services running:
cd backend && python scripts/seed_vault.py
```

Or via Docker:

```bash
docker compose run --rm api python scripts/seed_vault.py
```

The seeder:
1. Authenticates with `VAULT_TOKEN` (default: `root`)
2. Creates/updates all 5 KV v2 paths
3. Verifies every key was written correctly
4. Exits 0 on success, 1 on failure

Seeded values match the defaults in `.env.example`. In production, change them
before running the seeder by editing `scripts/seed_vault.py` line 23 (`SECRETS` dict).

---

## Startup Validation

On application startup (`app/infra/vault.py:139`), the module-level wrapper
`validate_required_secrets()` is called. It:
- Connects to Vault using `VAULT_ADDR` + `VAULT_TOKEN` env vars
- Reads every key in `REQUIRED_SECRETS`
- Raises `VaultConnectionError` listing which keys are missing
- If all pass, the API and workers proceed to start

This is a hard gate — the system refuses to start with missing secrets.

---

## Dev vs Production

| Aspect | Dev (this project) | Production |
|--------|-------------------|------------|
| Vault mode | Dev (`VAULT_DEV_ROOT_TOKEN_ID`) | HA with TLS + auto-unseal |
| Root token | `root` (hardcoded) | Generated at init, rotated |
| Secrets | Seeded by script | Written via CI/CD pipeline or operator |
| Network | Bridge network (`classifier-net`) | Internal VPC, no public exposure |
| Audit | Not configured | Vault audit device enabled |
| Token lifecycle | Static forever | TTL + renewal + revocation |

**For production**, at minimum:
- Enable TLS on Vault (`VAULT_ADDR=https://...`)
- Rotate the root token after initial setup
- Use AppRole or Kubernetes auth instead of static tokens
- Enable Vault audit logging to a file or syslog
- Store unseal keys in a secure key management system (AWS KMS, Azure Key Vault)

---

## Adapter API

`VaultAdapter` exposes two primary methods:

```python
adapter = VaultAdapter(url="http://vault:8200", token="root")

# Read a single secret
jwt_secret = adapter.read_secret("jwt", "secret")

# Validate all required secrets exist
results = adapter.validate_required_secrets()
# -> {"jwt": {"secret": True}, "postgres": {"user": True}, ...}
```

Error hierarchy:
- `VaultConnectionError` — server unreachable or auth failed
- `VaultSecretNotFound` — path doesn't exist in KV v2
- `VaultKeyNotFound` — key missing within an existing path

---

## Emergency: Vault is Down

If Vault is unreachable:
1. **API** — fails `/health/ready` check; `/health/live` still returns OK (container alive)
2. **Workers** — ingestion and inference workers crash-loop (restart policy: `unless-stopped`)
3. **Recovery** — restart the Vault container (`docker compose restart vault`), then re-seed if data was lost

Vault data is persisted in the `vault_data` Docker volume. A `docker compose down --volumes`
destroys all secrets — you must re-seed after a full teardown.
