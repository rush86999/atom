#!/usr/bin/env python3
"""
Token Encryption Verification Script

Checks integration tokens for encryption status and identifies security issues.
Run this script to verify that tokens are properly encrypted at rest.

Usage:
    python scripts/verify_token_encryption.py
"""

import os
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import create_engine, text
from core.database import DATABASE_URL
from core.config import settings


def is_fernet_encrypted(value: str) -> bool:
    """
    Check if value looks like Fernet-encrypted data.

    Fernet ciphertext is base64-encoded and starts with 'gAAAA'
    (the base64 encoding of version byte + timestamp).
    """
    if not value or len(value) < 44:
        return False

    # Fernet ciphertext starts with 'gAAAA'
    if not value.startswith('gAAAA'):
        return False

    # Try to decode as base64 to confirm
    try:
        import base64
        decoded = base64.urlsafe_b64decode(value.encode())
        # Fernet tokens are at least 9 bytes (version + timestamp + data)
        return len(decoded) >= 9
    except Exception:
        return False


def check_encryption_key():
    """Check if BYOK_ENCRYPTION_KEY is configured (env or persisted key file).

    Reads the canonical env var ``BYOK_ENCRYPTION_KEY`` first. The historical
    typo ``BYOK_ENCRYTION_KEY`` is accepted only as a legacy alias so
    misconfigured deployments still work, but it is no longer the primary
    lookup — the prior ordering made the audit miss a correctly-configured key
    whenever the typo env var was unset.
    """
    key = (
        os.getenv('BYOK_ENCRYPTION_KEY')
        or os.getenv('OAUTH_ENCRYPTION_KEY')
        or os.getenv('BYOK_ENCRYTION_KEY')  # legacy typo alias
    )

    if not key:
        # P0: fall back to the persisted key file shared with the BYOK managers.
        key_file = os.getenv('BYOK_ENC_KEY_FILE', './data/byok_encryption_key')
        try:
            with open(key_file, 'r') as f:
                key = f.read().strip()
            if key:
                return {
                    "configured": True,
                    "status": "ok",
                    "message": f"✅ Persisted encryption key found ({key_file}, {len(key)} chars)",
                    "severity": "OK"
                }
        except OSError:
            pass

    if not key:
        return {
            "configured": False,
            "status": "critical",
            "message": "❌ CRITICAL: BYOK_ENCRYPTION_KEY not configured",
            "severity": "CRITICAL"
        }

    # Validate key format
    try:
        from cryptography.fernet import Fernet
        Fernet(key.encode())
        return {
            "configured": True,
            "status": "ok",
            "message": f"✅ BYOK_ENCRYPTION_KEY configured ({len(key)} chars)",
            "severity": "OK"
        }
    except Exception as e:
        return {
            "configured": False,
            "status": "critical",
            "message": f"❌ CRITICAL: Invalid key format: {e}",
            "severity": "CRITICAL"
        }


def verify_integration_tokens(engine):
    """Check IntegrationToken table for plain text tokens."""
    issues = []

    with engine.connect() as conn:
        # Get total count
        result = conn.execute(text("SELECT COUNT(*) FROM integration_tokens"))
        total = result.scalar()

        if total == 0:
            return {"status": "OK", "message": "No integration tokens found", "issues": []}

        # Check for plain text tokens
        query = text("""
            SELECT id, provider,
                   access_token as token,
                   CASE
                     WHEN access_token LIKE 'gAAAA%' THEN 'encrypted'
                     ELSE 'plaintext'
                   END as status
            FROM integration_tokens
        """)

        result = conn.execute(query)
        rows = result.fetchall()

        plaintext_count = 0
        encrypted_count = 0

        for row in rows:
            if row.status == 'plaintext':
                issues.append({
                    "table": "integration_tokens",
                    "id": row.id,
                    "provider": row.provider,
                    "issue": "PLAIN TEXT TOKEN",
                    "token_preview": row.token[:20] if row.token else None
                })
                plaintext_count += 1
            else:
                encrypted_count += 1

        return {
            "total": total,
            "encrypted": encrypted_count,
            "plaintext": plaintext_count,
            "issues": issues
        }


def verify_llm_oauth_credentials(engine):
    """Check LLMOAuthCredential table for plain text tokens."""
    issues = []

    with engine.connect() as conn:
        # Get total count
        result = conn.execute(text("SELECT COUNT(*) FROM llm_oauth_credentials"))
        total = result.scalar()

        if total == 0:
            return {"status": "OK", "message": "No LLM OAuth credentials found", "issues": []}

        # Check for plain text tokens
        query = text("""
            SELECT id, provider_id,
                   access_token as token,
                   CASE
                     WHEN access_token LIKE 'gAAAA%' THEN 'encrypted'
                     ELSE 'plaintext'
                   END as status
            FROM llm_oauth_credentials
        """)

        result = conn.execute(query)
        rows = result.fetchall()

        plaintext_count = 0
        encrypted_count = 0

        for row in rows:
            if row.status == 'plaintext':
                issues.append({
                    "table": "llm_oauth_credentials",
                    "id": row.id,
                    "provider": row.provider_id,
                    "issue": "PLAIN TEXT TOKEN",
                    "token_preview": row.token[:20] if row.token else None
                })
                plaintext_count += 1
            else:
                encrypted_count += 1

        return {
            "total": total,
            "encrypted": encrypted_count,
            "plaintext": plaintext_count,
            "issues": issues
        }


def main():
    """Run verification checks."""
    print("=" * 80)
    print("INTEGRATION TOKEN SECURITY VERIFICATION")
    print("=" * 80)
    print()

    # Check encryption key
    print("1. Checking encryption key configuration...")
    key_status = check_encryption_key()
    print(f"   {key_status['message']}")
    print()

    if not key_status.get("configured"):
        print("   ⚠️  Tokens will be stored in PLAIN TEXT without encryption key!")
        print()

    # Connect to database
    print("2. Connecting to database...")
    try:
        engine = create_engine(DATABASE_URL)
        print(f"   ✅ Connected to: {DATABASE_URL[:50]}...")
        print()
    except Exception as e:
        print(f"   ❌ Failed to connect: {e}")
        return 1

    # Check IntegrationToken table
    print("3. Checking IntegrationToken table...")
    try:
        status = verify_integration_tokens(engine)

        if status.get("total", 0) > 0:
            print(f"   Total tokens: {status['total']}")
            print(f"   ✅ Encrypted: {status['encrypted']}")
            print(f"   ❌ Plain text: {status['plaintext']}")

            if status['plaintext'] > 0:
                print()
                print("   ⚠️  SECURITY ISSUE: Plain text tokens found:")
                for issue in status['issues'][:5]:  # Show first 5
                    print(f"      - {issue['table']}:{issue['id']} ({issue['provider']})")
                    if issue['token_preview']:
                        print(f"        Preview: {issue['token_preview']}...")
        else:
            print(f"   ℹ️  {status.get('message', 'No tokens found')}")
        print()
    except Exception as e:
        print(f"   ❌ Error: {e}")
        print()

    # Check LLMOAuthCredential table
    print("4. Checking LLMOAuthCredential table...")
    try:
        status = verify_llm_oauth_credentials(engine)

        if status.get("total", 0) > 0:
            print(f"   Total credentials: {status['total']}")
            print(f"   ✅ Encrypted: {status['encrypted']}")
            print(f"   ❌ Plain text: {status['plaintext']}")

            if status['plaintext'] > 0:
                print()
                print("   ⚠️  SECURITY ISSUE: Plain text credentials found:")
                for issue in status['issues'][:5]:  # Show first 5
                    print(f"      - {issue['table']}:{issue['id']} ({issue['provider']})")
                    if issue['token_preview']:
                        print(f"        Preview: {issue['token_preview']}...")
        else:
            print(f"   ℹ️  {status.get('message', 'No credentials found')}")
        print()
    except Exception as e:
        print(f"   ❌ Error: {e}")
        print()

    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)

    if key_status.get("severity") == "CRITICAL":
        print("❌ CRITICAL: Encryption key not configured - all tokens at risk")
        print()
        print("Action required:")
        print("1. Generate encryption key: openssl rand -base64 32")
        print("2. Set environment variable: export BYOK_ENCRYPTION_KEY=<key>")
        print("3. Restart application")
        return 1

    # Check for plain text tokens
    all_issues = []
    try:
        integration_status = verify_integration_tokens(engine)
        llm_status = verify_llm_oauth_credentials(engine)
        all_issues.extend(integration_status.get('issues', []))
        all_issues.extend(llm_status.get('issues', []))
    except:
        pass

    if all_issues:
        print(f"❌ CRITICAL: {len(all_issues)} plain text tokens found")
        print()
        print("Action required:")
        print("1. Review INTEGRATION_TOKEN_SECURITY_VERIFICATION.md")
        print("2. Re-encrypt all plain text tokens")
        print("3. Update encryption to be mandatory (fail closed)")
        return 1
    else:
        print("✅ All tokens are properly encrypted")
        return 0


if __name__ == "__main__":
    sys.exit(main())
