"""Live integration test for Vault, MinIO, and SFTP adapters.

Run from host:
    docker compose up -d postgres redis minio vault sftp
    python tests/integration/test_adapters_live.py

Run inside Docker:
    docker compose run --rm -v ./tests:/app/tests:ro api pytest tests/integration/ -v

Service addresses are read from environment variables (same ones the app uses),
defaulting to localhost for host-side execution.
"""

from __future__ import annotations

import io
import os

import paramiko

_VAULT_ADDR = os.environ.get("VAULT_ADDR", "http://localhost:8200")
_VAULT_TOKEN = os.environ.get("VAULT_TOKEN", "root")
_MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "localhost:9000")
_SFTP_HOST = os.environ.get("SFTP_HOST", "localhost")
_SFTP_PORT = int(os.environ.get("SFTP_PORT", "2222"))
_SFTP_USER = os.environ.get("SFTP_USER", "vendor")
_SFTP_PASSWORD = os.environ.get("SFTP_PASSWORD", "vendorpass")


def test_vault_adapter_live():
    """Test VaultAdapter against a running Vault dev server."""
    print("=" * 60)
    print("1. VAULT ADAPTER — Live test")
    print("=" * 60)

    from app.infra.vault import VaultAdapter

    va = VaultAdapter(url=_VAULT_ADDR, token=_VAULT_TOKEN)

    paths = {
        "jwt": ["secret"],
        "postgres": ["user", "password", "db"],
        "minio": ["access_key", "secret_key"],
        "sftp": ["user", "password", "host", "port"],
        "redis": ["url"],
    }
    for path, keys in paths.items():
        for key in keys:
            val = va.read_secret(path, key)
            print(f"  {path}:{key} = {val}")

    print()
    print("  validate_required_secrets:")
    results = va.validate_required_secrets()
    all_ok = True
    for path, keys in results.items():
        for key, ok in keys.items():
            status = "OK" if ok else "MISSING"
            if not ok:
                all_ok = False
            print(f"    {path}:{key} = {status}")
    assert all_ok, "Expected all secrets to be present"
    print("  ALL SECRETS FOUND: PASS")

    # Test missing key raises properly
    from app.infra.vault import VaultKeyNotFound

    try:
        va.read_secret("jwt", "nonexistent_key")
        print("  Missing key detection: FAIL (should have raised)")
        assert False, "Should have raised VaultKeyNotFound"
    except VaultKeyNotFound:
        print("  Missing key detection: PASS")


def test_minio_adapter_live():
    """Test MinIOAdapter against a running MinIO server."""
    print()
    print("=" * 60)
    print("2. MINIO ADAPTER — Live test")
    print("=" * 60)

    from app.infra.minio import MinIOAdapter, MinIOFileNotFoundError

    ma = MinIOAdapter(endpoint=_MINIO_ENDPOINT)

    # Bucket bootstrap (idempotent)
    ma.ensure_buckets_exist()
    print("  Buckets ensured: PASS")

    # Upload a test object
    test_data = b"HELLO MINIO TEST DATA"
    key = ma.upload_file("originals", "test/manual-test.tiff", test_data, "image/tiff")
    assert key == "test/manual-test.tiff"
    print(f"  Upload: PASS ({key})")

    # Check existence
    exists = ma.file_exists("originals", "test/manual-test.tiff")
    assert exists is True
    print("  Exists (present): PASS")

    fake_exists = ma.file_exists("originals", "test/fake.tiff")
    assert fake_exists is False
    print("  Exists (absent): PASS")

    # Download and verify
    data = ma.download_file("originals", "test/manual-test.tiff")
    assert data == test_data, f"Content mismatch: {len(data)} != {len(test_data)}"
    print(f"  Download + verify: PASS ({len(data)} bytes)")

    # Test missing file raises properly
    try:
        ma.download_file("originals", "nonexistent.tiff")
        print("  Missing file detection: FAIL (should have raised)")
        assert False, "Should have raised MinIOFileNotFoundError"
    except MinIOFileNotFoundError:
        print("  Missing file detection: PASS")


def test_sftp_adapter_live():
    """Test SFTPAdapter against a running Atmoz SFTP server."""
    print()
    print("=" * 60)
    print("3. SFTP ADAPTER — Live test")
    print("=" * 60)

    from app.infra.sftp import SFTPAdapter

    # Drop a test file into the SFTP folder using raw paramiko
    transport = paramiko.Transport((_SFTP_HOST, _SFTP_PORT))
    transport.connect(username=_SFTP_USER, password=_SFTP_PASSWORD)
    sftp_put = paramiko.SFTPClient.from_transport(transport)
    test_content = b"THIS IS A TEST TIFF FILE CONTENT"
    sftp_put.putfo(io.BytesIO(test_content), "drop/live_test.tiff")
    sftp_put.close()
    transport.close()
    print("  Dropped live_test.tiff: PASS")

    # Test our adapter. Atmoz SFTP chroots users to their home,
    # so paths are relative to /home/vendor.
    with SFTPAdapter(_SFTP_HOST, _SFTP_PORT, _SFTP_USER, _SFTP_PASSWORD) as sftp:
        # list_files
        files = sftp.list_files("drop")
        assert len(files) >= 1, f"Expected at least 1 file, got {len(files)}"
        print(f"  list_files: PASS ({len(files)} file(s) found)")
        for f in files:
            print(f"    -> {f.filename}: {f.size_bytes} bytes, {f.modified_at}")

        # Use the test file specifically (not files[0] which may be another file)
        test_files = [f for f in files if f.filename == "live_test.tiff"]
        assert len(test_files) == 1, f"Expected test file, found: {[f.filename for f in files]}"

        # get_file_metadata
        meta = sftp.get_file_metadata(test_files[0].remote_path)
        assert meta.size_bytes > 0, f"Expected positive size, got {meta.size_bytes}"
        print(f"  get_file_metadata: PASS (size={meta.size_bytes})")

        # read_file_content
        content = sftp.read_file_content(test_files[0].remote_path)
        assert isinstance(content, bytes)
        assert len(content) == len(test_content)
        print(f"  read_file_content: PASS ({len(content)} bytes)")

        # Verify content
        assert content == test_content, "Content does not match"
        print("  Content match: PASS")

        # open_file (streaming)
        fh = sftp.open_file(test_files[0].remote_path)
        streamed = fh.read()
        fh.close()
        assert streamed == test_content
        print("  open_file (streaming): PASS")

        # Test missing file
        from app.infra.sftp import SFTPFileError

        try:
            sftp.get_file_metadata("drop/nonexistent.tiff")
            print("  Missing file detection: FAIL (should have raised)")
            assert False, "Should have raised SFTPFileError"
        except SFTPFileError:
            print("  Missing file detection: PASS")


if __name__ == "__main__":
    test_vault_adapter_live()
    test_minio_adapter_live()
    test_sftp_adapter_live()
    print()
    print("=" * 60)
    print("ALL LIVE INTEGRATION TESTS PASSED")
    print("=" * 60)
