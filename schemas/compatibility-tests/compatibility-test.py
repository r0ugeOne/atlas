#!/usr/bin/env python3
"""
Register Avro schemas with a Confluent-compatible Schema Registry.

Recursively scans a directory (default: ./ecommerce) for *.avsc files,
including ones nested in per-table subfolders, e.g.:

    ecommerce/customers/customers-key.avsc
    ecommerce/customers/customers-value.avsc
    ecommerce/orders/orders-key.avsc
    ecommerce/orders/orders-value.avsc

Since each filename already includes its "-key" / "-value" suffix, the
subject is simply <subject-prefix>.<filename-without-extension>, e.g.:

    atlas_postgres.ecommerce.customers-value
    atlas_postgres.ecommerce.customers-key

Usage:
    python register_schemas.py
    python register_schemas.py --schema-dir ecommerce --url http://localhost:8081
    python register_schemas.py --subject-prefix atlas_postgres.ecommerce
    python register_schemas.py --dry-run
    python register_schemas.py --keys-only        # only register *-key.avsc files
    python register_schemas.py --values-only       # only register *-value.avsc files
    python register_schemas.py --skip-compatibility-check   # register without checking first

By default, each schema is checked for compatibility against the subject's
latest registered version (via /compatibility/subjects/{subject}/versions/latest)
before being registered. New subjects (no existing versions) are always
treated as compatible. Incompatible schemas are skipped, not registered.

To Register Schema


python schemas/compatibility-tests/compatibility-test.py \
  --schema-dir schemas/ecommerce \
  --url http://localhost:8081 \
  --subject-prefix atlas_postgres.ecommerce

To Check Schema


python schemas/compatibility-tests/compatibility-test.py \
  --schema-dir schemas/ecommerce \
  --url http://localhost:8081 \
  --subject-prefix atlas_postgres.ecommerce
  --check-only

Env vars (used as defaults if flags aren't passed):
    SCHEMA_REGISTRY_URL
    SCHEMA_DIR
    SUBJECT_PREFIX
"""

import argparse
import json
import os
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("This script requires the 'requests' package: pip install requests")


def parse_args():
    p = argparse.ArgumentParser(description="Register Avro schemas with a Schema Registry")
    p.add_argument(
        "--url",
        default=os.environ.get("SCHEMA_REGISTRY_URL", "http://localhost:8081"),
        help="Schema Registry base URL (default: %(default)s)",
    )
    p.add_argument(
        "--schema-dir",
        default=os.environ.get("SCHEMA_DIR", "ecommerce"),
        help="Directory containing .avsc files (default: %(default)s)",
    )
    p.add_argument(
        "--subject-prefix",
        default=os.environ.get("SUBJECT_PREFIX", "atlas_postgres.ecommerce"),
        help="Prefix prepended to each subject name, e.g. '<connector>.<schema>' (default: %(default)s)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be registered without calling the registry",
    )
    p.add_argument(
        "--keys-only",
        action="store_true",
        help="Only register *-key.avsc files",
    )
    p.add_argument(
        "--values-only",
        action="store_true",
        help="Only register *-value.avsc files",
    )
    p.add_argument(
        "--skip-compatibility-check",
        action="store_true",
        help="Register directly without checking compatibility against the latest version first",
    )
    p.add_argument(
        "--check-only",
        action="store_true",
        help="Only run compatibility checks; do not register any schemas (useful in CI)",
    )
    args = p.parse_args()

    if args.check_only and args.skip_compatibility_check:
        p.error("--check-only and --skip-compatibility-check cannot be used together")

    return args


def load_schema_files(schema_dir: Path, keys_only: bool = False, values_only: bool = False):
    # rglob walks into per-table subfolders (customers/, orders/, etc.)
    files = sorted(schema_dir.rglob("*.avsc"))

    if keys_only:
        files = [f for f in files if f.stem.endswith("-key")]
    elif values_only:
        files = [f for f in files if f.stem.endswith("-value")]

    if not files:
        sys.exit(f"No matching .avsc files found under '{schema_dir}'")
    return files


def build_subject(file: Path, prefix: str) -> str:
    # filename already includes -key / -value, e.g. "customers-value"
    subject_name = file.stem
    parts = [p for p in (prefix, subject_name) if p]
    return ".".join(parts)


def check_compatibility(url: str, subject: str, schema_str: str):
    """
    Check the given schema against the subject's latest registered version.

    Returns a tuple (status, detail):
      status = "new"          -> subject has no existing versions, nothing to check against
      status = "compatible"   -> compatible with the latest version
      status = "incompatible" -> NOT compatible; detail contains the reason if provided
      status = "error"        -> could not determine (network/HTTP error); detail has the message
    """
    endpoint = f"{url}/compatibility/subjects/{subject}/versions/latest"
    headers = {"Content-Type": "application/vnd.schemaregistry.v1+json"}
    payload = {"schema": schema_str}

    try:
        resp = requests.post(endpoint, headers=headers, data=json.dumps(payload), timeout=15)
    except requests.RequestException as e:
        return "error", str(e)

    if resp.status_code == 404:
        # Subject or version doesn't exist yet -> nothing to be incompatible with
        return "new", None

    if resp.status_code != 200:
        return "error", f"HTTP {resp.status_code}: {resp.text}"

    is_compatible = resp.json().get("is_compatible", False)
    if is_compatible:
        return "compatible", None
    return "incompatible", resp.json()


def register_schema(url: str, subject: str, schema_path: Path, dry_run: bool = False,
                     skip_compatibility_check: bool = False, check_only: bool = False):
    schema_str = schema_path.read_text()

    # Validate it's actually valid JSON before sending
    try:
        json.loads(schema_str)
    except json.JSONDecodeError as e:
        print(f"  [SKIP] {schema_path} is not valid JSON: {e}")
        return False

    if not skip_compatibility_check:
        status, detail = check_compatibility(url, subject, schema_str)
        if status == "new":
            print(f"  [COMPAT] '{subject}' has no existing versions, skipping check")
        elif status == "compatible":
            print(f"  [COMPAT] '{subject}' is compatible with latest version")
        elif status == "incompatible":
            print(f"  [COMPAT-FAIL] '{subject}' is NOT compatible with latest version: {detail}")
            print(f"  [SKIP] Not registering '{subject}'")
            return False
        else:  # error
            print(f"  [COMPAT-ERROR] Could not check compatibility for '{subject}': {detail}")
            print(f"  [SKIP] Not registering '{subject}' (compatibility unknown)")
            return False

        if check_only:
            # Compatibility already confirmed above; nothing more to do for this file.
            return True

    payload = {"schema": schema_str}

    if dry_run:
        print(f"  [DRY-RUN] Would register subject '{subject}' from {schema_path}")
        return True

    endpoint = f"{url}/subjects/{subject}/versions"
    headers = {"Content-Type": "application/vnd.schemaregistry.v1+json"}

    try:
        resp = requests.post(endpoint, headers=headers, data=json.dumps(payload), timeout=15)
    except requests.RequestException as e:
        print(f"  [ERROR] Could not reach {endpoint}: {e}")
        return False

    if 200 <= resp.status_code < 300:
        version_id = resp.json().get("id")
        print(f"  [OK] '{subject}' registered (schema id: {version_id})")
        return True
    else:
        print(f"  [FAIL] '{subject}' -> HTTP {resp.status_code}: {resp.text}")
        return False


def main():
    args = parse_args()
    schema_dir = Path(args.schema_dir)

    if not schema_dir.is_dir():
        sys.exit(f"Schema directory '{schema_dir}' does not exist")

    files = load_schema_files(schema_dir, keys_only=args.keys_only, values_only=args.values_only)
    print(f"Found {len(files)} schema file(s) under '{schema_dir}'\n")

    results = []
    for file in files:
        subject = build_subject(file, args.subject_prefix)
        action = "Checking" if args.check_only else "Registering"
        print(f"{action} '{file.name}' -> subject '{subject}'")
        ok = register_schema(
            args.url, subject, file,
            dry_run=args.dry_run,
            skip_compatibility_check=args.skip_compatibility_check,
            check_only=args.check_only,
        )
        results.append((subject, ok))

    print("\nSummary:")
    failures = [s for s, ok in results if not ok]
    for subject, ok in results:
        print(f"  {'OK  ' if ok else 'FAIL'}  {subject}")

    if failures:
        label = "incompatible" if args.check_only else "failed to register"
        print(f"\n{len(failures)} schema(s) {label}.")
        sys.exit(1)

    if args.check_only:
        print(f"\nAll {len(results)} schema(s) are compatible.")
    else:
        print(f"\nAll {len(results)} schema(s) registered successfully.")


if __name__ == "__main__":
    main()