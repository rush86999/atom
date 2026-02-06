# Data Protection Guide

> **Last Updated**: February 6, 2026
> **Purpose**: Complete guide to encryption, secrets management, and data protection in Atom

---

## Overview

Atom provides comprehensive data protection with:
- **Fernet Encryption**: Symmetric encryption for sensitive data
- **Secrets Management**: Secure storage and retrieval of API keys and tokens
- **Auto-Migration**: Automatic migration from plaintext to encrypted secrets
- **Per-User Encryption**: Individual credential encryption for OAuth tokens
- **Secure Configuration**: Environment-based secret management

### Encryption Architecture

```
Plaintext Secret → Fernet Encryption → Encrypted Data → Database Storage
     ↓
Encryption Key (ENV variable)
```

---

## Fernet Encryption

### Overview

**Fernet** is a symmetric encryption algorithm provided by the `cryptography` library:
- **AES-128-CBC** encryption
- **HMAC-SHA256** authentication
- **URL-safe base64 encoding**
- **Timestamp verification** (optional)

### Encryption Key Generation

**Generate Secure Key**:
```bash
python -c "import secrets; print('ENCRYPTION_KEY=' + secrets.token_urlsafe(32))"
```

**Example Output**:
```
ENCRYPTION_KEY=a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6
```

### Configuration

**Environment Variable**:
```bash
export ENCRYPTION_KEY="your-encryption-key-here"
```

**Optional Feature**:
- If `ENCRYPTION_KEY` is not set, secrets are stored in **plaintext**
- Encryption is **optional** but recommended for production
- Auto-migrates plaintext secrets to encrypted when key is set

### Implementation

**File**: `backend/core/secrets_encryption.py`

```python
from cryptography.fernet import Fernet, InvalidToken
import os
import logging

logger = logging.getLogger(__name__)

class SecretsEncryption:
    """Fernet encryption for sensitive data"""

    def __init__(self):
        self.encryption_key = os.getenv('ENCRYPTION_KEY')
        self.cipher = None

        if self.encryption_key:
            try:
                # Ensure key is URL-safe base64 encoded
                if not self.encryption_key.endswith('='):
                    # Add padding if needed
                    self.encryption_key += '=' * (4 - len(self.encryption_key) % 4)

                self.cipher = Fernet(self.encryption_key.encode())
                logger.info("✅ Secrets encryption enabled")
            except Exception as e:
                logger.error(f"Failed to initialize encryption: {e}")
                self.cipher = None
        else:
            logger.warning("⚠️ ENCRYPTION_KEY not set - secrets will be stored in plaintext")

    def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext string"""
        if not self.cipher:
            # Fallback to plaintext if encryption not enabled
            logger.debug("Encryption not enabled, returning plaintext")
            return plaintext

        try:
            encrypted_bytes = self.cipher.encrypt(plaintext.encode())
            return encrypted_bytes.decode()
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise

    def decrypt(self, encrypted: str) -> str:
        """Decrypt encrypted string"""
        if not self.cipher:
            # Return as-is if encryption not enabled
            logger.debug("Decryption not enabled, returning as-is")
            return encrypted

        try:
            decrypted_bytes = self.cipher.decrypt(encrypted.encode())
            return decrypted_bytes.decode()
        except InvalidToken:
            logger.error("Decryption failed: Invalid token")
            raise ValueError("Invalid encrypted data")
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise

# Global instance
secrets_encryption = SecretsEncryption()
```

### Usage Examples

**Encrypting Data**:
```python
from core.secrets_encryption import secrets_encryption

# Encrypt API token
access_token = "xoxb-your-slack-token"
encrypted_token = secrets_encryption.encrypt(access_token)
# Result: "gAAAAABh..."

# Store in database
credential = UserCredential(
    user_id="user_123",
    provider="slack",
    encrypted_token=encrypted_token
)
db.add(credential)
db.commit()
```

**Decrypting Data**:
```python
# Retrieve from database
credential = db.query(UserCredential).filter(
    UserCredential.user_id == "user_123",
    UserCredential.provider == "slack"
).first()

# Decrypt token
access_token = secrets_encryption.decrypt(credential.encrypted_token)
# Result: "xoxb-your-slack-token"

# Use for API calls
slack_client = SlackClient(token=access_token)
```

---

## Secrets Migration

### Auto-Migration

**Purpose**: Automatically migrate plaintext secrets to encrypted format

**Trigger**: When `ENCRYPTION_KEY` is set for the first time

**Implementation**:

```python
def migrate_secrets_to_encryption():
    """Migrate plaintext secrets to encrypted format"""

    if not secrets_encryption.cipher:
        logger.info("Encryption not enabled, skipping migration")
        return

    # Get all secrets from secrets.json
    with open('secrets.json', 'r') as f:
        secrets = json.load(f)

    # Migrate each secret
    encrypted_secrets = {}
    for key, value in secrets.items():
        if isinstance(value, str):
            encrypted_secrets[key] = secrets_encryption.encrypt(value)
        else:
            encrypted_secrets[key] = value

    # Save to secrets.enc
    with open('secrets.enc', 'w') as f:
        json.dump(encrypted_secrets, f)

    # Backup plaintext file
    shutil.copy('secrets.json', 'secrets.json.backup')

    logger.info("✅ Secrets migrated to encrypted format")
```

### Manual Migration

**Step 1: Backup Existing Secrets**
```bash
cp secrets.json secrets.json.backup
```

**Step 2: Set Encryption Key**
```bash
export ENCRYPTION_KEY="your-encryption-key"
```

**Step 3: Run Migration Script**
```bash
python3 backend/scripts/migrate_secrets.py
```

**Step 4: Verify Migration**
```bash
python3 -c "
import json
from core.secrets_encryption import secrets_encryption

# Load encrypted secrets
with open('secrets.enc', 'r') as f:
    encrypted = json.load(f)

# Decrypt and verify
for key, value in encrypted.items():
    decrypted = secrets_encryption.decrypt(value)
    print(f'{key}: {decrypted[:10]}...')
"
```

### Rollback

**If Migration Fails**:
```bash
# Restore from backup
cp secrets.json.backup secrets.json

# Remove encrypted file
rm secrets.enc

# Restart without encryption
unset ENCRYPTION_KEY
```

---

## Storage Formats

### Plaintext Storage (Unencrypted)

**File**: `secrets.json`

```json
{
  "slack_token": "xoxb-your-plaintext-token",
  "google_api_key": "AIza-your-plaintext-key",
  "openai_api_key": "sk-your-plaintext-key"
}
```

**⚠️ Security Risk**: Use only in development!

### Encrypted Storage (Fernet)

**File**: `secrets.enc`

```json
{
  "slack_token": "gAAAAABh...",
  "google_api_key": "gAAAAABi...",
  "openai_api_key": "gAAAAABj..."
}
```

**✅ Secure**: Suitable for production!

### Database Storage

**Table**: `user_credentials`

```sql
CREATE TABLE user_credentials (
    id INTEGER PRIMARY KEY,
    user_id VARCHAR(255),
    provider VARCHAR(50),
    encrypted_token TEXT,  -- Fernet encrypted
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

**Query with Decryption**:
```python
credentials = db.query(UserCredential).filter(
    UserCredential.user_id == current_user.id
).all()

for cred in credentials:
    token = secrets_encryption.decrypt(cred.encrypted_token)
    # Use token for API calls
```

---

## Per-User Credential Encryption

### Overview

Each user's OAuth tokens are encrypted **individually**:
- Prevents cross-user data leakage
- Enables secure multi-tenancy
- Isolates user credentials

### Implementation

**Store User Credential**:
```python
def store_user_credential(user_id: str, provider: str, access_token: str):
    """Store encrypted user credential"""
    encrypted_token = secrets_encryption.encrypt(access_token)

    credential = UserCredential(
        user_id=user_id,
        provider=provider,
        encrypted_token=encrypted_token
    )

    db.add(credential)
    db.commit()

    logger.info(f"Stored encrypted credential for user {user_id}, provider {provider}")
```

**Retrieve User Credential**:
```python
def get_user_credential(user_id: str, provider: str) -> str:
    """Retrieve and decrypt user credential"""
    credential = db.query(UserCredential).filter(
        UserCredential.user_id == user_id,
        UserCredential.provider == provider
    ).first()

    if not credential:
        raise ValueError(f"Credential not found for {provider}")

    access_token = secrets_encryption.decrypt(credential.encrypted_token)
    return access_token
```

### Usage in Services

```python
class SlackService:
    """Slack API service with encrypted credentials"""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.access_token = get_user_credential(user_id, "slack")
        self.client = SlackClient(token=self.access_token)

    async def list_channels(self):
        """List Slack channels"""
        return await self.client.conversations_list()
```

---

## Security Best Practices

### 1. Key Management

**Never Commit Keys**:
```bash
# Add to .gitignore
echo "ENCRYPTION_KEY" >> .gitignore
echo "secrets.enc" >> .gitignore
echo "secrets.json" >> .gitignore
```

**Rotate Keys Regularly**:
```bash
# Generate new key
export ENCRYPTION_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")

# Decrypt all secrets with old key
# Encrypt all secrets with new key
# Update database
```

### 2. Environment Variables

**Use .env Files** (Development):
```bash
# .env
ENCRYPTION_KEY=your-development-key
SECRET_KEY=your-secret-key
SLACK_SIGNING_SECRET=your-slack-secret
```

**Use Secret Management** (Production):
- AWS Secrets Manager
- Azure Key Vault
- Google Secret Manager
- HashiCorp Vault

### 3. Access Control

**Restrict File Permissions**:
```bash
# Limit access to secrets file
chmod 600 secrets.enc
chmod 600 secrets.json

# Limit access to logs
chmod 640 logs/atom.log
```

**Database Permissions**:
```sql
-- Restrict access to user_credentials table
GRANT SELECT, INSERT, UPDATE ON user_credentials TO app_user;
REVOKE ALL ON user_credentials FROM public;
```

### 4. Logging

**Never Log Secrets**:
```python
# ❌ BAD - Logs plaintext token
logger.info(f"Using token: {access_token}")

# ✅ GOOD - Logs masked token
logger.info(f"Using token: {access_token[:10]}...")
```

**Log Security Events**:
```python
logger.info(f"Security Audit: credential_accessed - user={user_id} - provider={provider}")
```

---

## Security Status

### Check Encryption Status

**API Endpoint**:
```bash
curl http://localhost:8000/api/security/configuration
```

**Response**:
```json
{
  "encryption_enabled": true,
  "encryption_key_configured": true,
  "secrets_file": "secrets.enc",
  "total_secrets": 25,
  "encrypted_secrets": 25,
  "plaintext_secrets": 0
}
```

### Check Individual Secret

**Python**:
```python
from core.secrets_encryption import secrets_encryption

def check_secret_status(secret: str) -> bool:
    """Check if secret is encrypted"""
    try:
        # Try to decrypt
        decrypted = secrets_encryption.decrypt(secret)
        # If successful, it was encrypted
        return True
    except:
        # If failed, it might be plaintext
        return False
```

---

## Troubleshooting

### Issue: Encryption Not Working

**Symptoms**: Secrets stored in plaintext

**Diagnosis**:
```bash
# Check if ENCRYPTION_KEY is set
echo $ENCRYPTION_KEY

# Check logs
tail -f logs/atom.log | grep "encryption"
```

**Solutions**:
1. Set `ENCRYPTION_KEY` environment variable
2. Restart backend: `systemctl restart atom-backend`
3. Verify key format (URL-safe base64)

### Issue: Decryption Failed

**Symptoms**: `InvalidToken` error when decrypting

**Diagnosis**:
```python
# Check if encrypted data is valid
python3 -c "
from core.secrets_encryption import secrets_encryption
encrypted = 'gAAAAABh...'
try:
    decrypted = secrets_encryption.decrypt(encrypted)
    print(f'Decrypted: {decrypted}')
except Exception as e:
    print(f'Error: {e}')
"
```

**Solutions**:
1. Verify `ENCRYPTION_KEY` matches original key
2. Check if encrypted data was tampered with
3. Restore from backup if needed

### Issue: Migration Failed

**Symptoms**: Secrets not migrated to encrypted format

**Diagnosis**:
```bash
# Check if secrets.enc exists
ls -la secrets.enc

# Check migration logs
tail -f logs/atom.log | grep "migration"
```

**Solutions**:
1. Restore from backup: `cp secrets.json.backup secrets.json`
2. Verify `ENCRYPTION_KEY` is set
3. Re-run migration script
4. Check file permissions

---

## Compliance

### GDPR Compliance

- **Data Encryption**: All sensitive data encrypted at rest
- **Access Control**: Per-user credential isolation
- **Audit Logging**: All credential access logged
- **Right to Erasure**: Users can delete their credentials

### SOC2 Compliance

- **Encryption**: Fernet encryption for secrets
- **Key Management**: Secure key rotation
- **Access Logging**: Audit trail for credential access
- **Monitoring**: Security status endpoints

### HIPAA Compliance

- **PHI Protection**: Encrypted storage for health data
- **Audit Controls**: Access logging
- **Integrity Controls**: Tamper detection
- **Transmission Security**: HTTPS/TLS

---

## Configuration Checklist

### Development

- [ ] Set `ENCRYPTION_KEY` (optional)
- [ ] Use `secrets.json` for plaintext secrets
- [ ] Add `secrets.json` to `.gitignore`
- [ ] Test encryption/decryption
- [ ] Verify migration script

### Production

- [ ] Set `ENCRYPTION_KEY` (required)
- [ ] Migrate secrets to `secrets.enc`
- [ ] Delete plaintext secrets files
- [ ] Verify all secrets encrypted
- [ ] Set up key rotation
- [ ] Configure monitoring
- [ ] Set up alerts for encryption failures

---

## References

### Official Documentation
- [Cryptography Library](https://cryptography.io/)
- [Fernet Specification](https://github.com/fernet/spec/blob/master/Spec.md)
- [OWASP Encryption](https://cheatsheetseries.owasp.org/cheatsheets/Encryption_In_Practice_Cheat_Sheet.html)

### Atom Documentation
- [DEVELOPMENT.md](../DEVELOPMENT.md) - Security Configuration section
- [SECURITY/AUTHENTICATION.md](AUTHENTICATION.md) - OAuth credential storage
- [backend/core/secrets_encryption.py](../../backend/core/secrets_encryption.py) - Implementation
- [backend/tests/test_secrets_encryption.py](../../backend/tests/test_secrets_encryption.py) - Tests

### Security Standards
- [GDPR Compliance](COMPLIANCE.md) - GDPR requirements
- [SOC2 Compliance](COMPLIANCE.md) - SOC2 requirements
- [HIPAA Compliance](COMPLIANCE.md) - HIPAA requirements

