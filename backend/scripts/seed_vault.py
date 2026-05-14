"""Seed Vault dev mode KV v2 with required secrets for local development.

Usage:
    python scripts/seed_vault.py [--vault-url http://localhost:8200] [--vault-token root]

Requires a running Vault dev server. Reads VAULT_ADDR and VAULT_TOKEN
from environment if not passed as arguments.
"""

from __future__ import annotations

import argparse
import os
import sys

import hvac


# All Vault secrets required for local development.
# Each top-level key is a KV v2 path. The nested dict contains
# the key-value pairs that will be written under that path.
# These values match the defaults in .env.example.
SECRETS = {
    "jwt": {
        "secret": "my-jwt-secret-key",
    },
    "postgres": {
        "user": "postgres",
        "password": "changeme",
        "db": "document_classifier",
    },
    "minio": {
        "access_key": "minioadmin",
        "secret_key": "minioadmin",
    },
    "sftp": {
        "user": "vendor",
        "password": "vendorpass",
        "host": "sftp",
        "port": "22",
    },
    "redis": {
        "url": "redis://redis:6379/0",
    },
}


def seed_vault(vault_url: str, vault_token: str) -> bool:
    """Seed all required secrets into Vault KV v2.

    Args:
        vault_url: Vault server URL.
        vault_token: Vault authentication token.

    Returns:
        True if all secrets were written and verified successfully.
    """
    print(f"Connecting to Vault at {vault_url} ...")
    try:
        client = hvac.Client(url=vault_url, token=vault_token)
    except Exception as exc:
        print(f"FAILED to create Vault client: {exc}", file=sys.stderr)
        return False

    try:
        authenticated = client.is_authenticated()
    except Exception as exc:
        print(f"FAILED to verify authentication: {exc}", file=sys.stderr)
        return False

    if not authenticated:
        print("FAILED to authenticate with Vault. Check your token.", file=sys.stderr)
        return False

    print("Authenticated OK.\n")

    all_ok = True
    for path, data in SECRETS.items():
        try:
            client.secrets.kv.v2.create_or_update_secret(
                path=path,
                secret=data,
            )
            print(f"  seed/{path} -> {_format_keys(data)}")
        except Exception as exc:
            print(f"  seed/{path} -> FAILED: {exc}", file=sys.stderr)
            all_ok = False

    if not all_ok:
        print("\nSome secrets failed to write.", file=sys.stderr)
        return False

    # Verify
    print("\nVerifying secrets ...")
    for path, data in SECRETS.items():
        try:
            response = client.secrets.kv.v2.read_secret_version(
                path=path,
                raise_on_deleted_version=True,
            )
            stored = response.get("data", {}).get("data", {})
            missing = [k for k in data if stored.get(k) != data[k]]
            if missing:
                print(f"  {path} -> MISMATCH in keys: {missing}")
                all_ok = False
            else:
                print(f"  {path} -> OK")
        except Exception as exc:
            print(f"  {path} -> FAILED to verify: {exc}")
            all_ok = False

    return all_ok


def _format_keys(data: dict) -> str:
    """Format a dict of secret keys for display (no values shown)."""
    return ", ".join(sorted(data.keys()))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed Vault dev mode with required local secrets."
    )
    parser.add_argument(
        "--vault-url",
        default=os.environ.get("VAULT_ADDR", "http://localhost:8200"),
        help="Vault server URL (default: VAULT_ADDR env or http://localhost:8200)",
    )
    parser.add_argument(
        "--vault-token",
        default=os.environ.get("VAULT_TOKEN", "root"),
        help="Vault token (default: VAULT_TOKEN env or 'root')",
    )
    args = parser.parse_args()

    print("=" * 55)
    print("Vault Secret Seeder — Document Classification Service")
    print("=" * 55)
    print()

    success = seed_vault(args.vault_url, args.vault_token)

    print()
    if success:
        print("All secrets seeded and verified successfully.")
        sys.exit(0)
    else:
        print("Seeding FAILED. Check Vault is running and reachable.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
