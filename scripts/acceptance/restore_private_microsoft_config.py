"""Restore the existing approved Microsoft OAuth client settings.

Copies ONLY the Microsoft client keys from an existing private runtime env
into the target private runtime env. Never prints values, never creates an app
registration, and never rotates a credential.

Usage:
    python scripts/acceptance/restore_private_microsoft_config.py \
        --source /Users/.../atom/backend/.env \
        --destination /private/.../atom-whole-app/backend/.env
"""
from __future__ import annotations

import argparse
import os
import shutil
import time
from pathlib import Path

KEYS = (
    "MICROSOFT_CLIENT_ID",
    "MICROSOFT_CLIENT_SECRET",
    "MICROSOFT_TENANT_ID",
)
_PLACEHOLDERS = ("your-", "change-me", "<redacted>", "stripped", "placeholder")


def _read_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        if key in KEYS:
            values[key] = value.strip().strip('"\'')
    return values


def _valid(value: str) -> bool:
    lowered = (value or "").lower()
    return bool(value) and not any(marker in lowered for marker in _PLACEHOLDERS)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--destination", required=True)
    args = parser.parse_args()

    source = Path(args.source).expanduser().resolve()
    destination = Path(args.destination).expanduser().resolve()
    if not source.is_file():
        print(f"source_missing={source}")
        return 2
    if not destination.is_file():
        print(f"destination_missing={destination}")
        return 2
    if source == destination:
        print("source_and_destination_identical")
        return 2

    values = _read_values(source)
    missing = [key for key in KEYS if not _valid(values.get(key, ""))]
    if missing:
        print("source_incomplete=" + ",".join(missing))
        return 3

    backup = destination.with_name(
        destination.name + f".pre-oauth-restore-{time.strftime('%Y%m%dT%H%M%SZ')}"
    )
    shutil.copy2(destination, backup)
    os.chmod(backup, 0o600)

    lines = destination.read_text().splitlines()
    seen: set[str] = set()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in KEYS:
            lines[index] = f"{key}={values[key]}"
            seen.add(key)
    for key in KEYS:
        if key not in seen:
            lines.append(f"{key}={values[key]}")

    destination.write_text("\n".join(lines).rstrip() + "\n")
    os.chmod(destination, 0o600)

    restored = _read_values(destination)
    print(f"destination={destination}")
    print(f"backup={backup}")
    for key in KEYS:
        print(f"{key}:present={bool(restored.get(key))}")
    print("credential_values_printed=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
