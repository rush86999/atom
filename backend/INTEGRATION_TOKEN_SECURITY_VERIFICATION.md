# Integration Token Management - Security Verification Report

**Date**: 2026-04-27
**Scope**: Token storage and encryption for all integration services
**Severity**: CRITICAL vulnerabilities identified

---

## Executive Summary

A comprehensive security review of integration token management has identified **CRITICAL vulnerabilities** in how OAuth tokens and API keys are stored. While the codebase includes encryption utilities, **tokens are being stored in plain text when encryption keys are not configured**, and encryption is **optional rather than enforced**.

**Key Finding**: The system fails closed to insecure behavior rather than failing open (rejecting operations when encryption is unavailable).

---

## Token Storage Architecture

### 1. Database Models

#### IntegrationToken Model (`backend/core/models.py:4092-4149`)
```python
class IntegrationToken(Base):
    access_token = Column(Text, nullable=False)  # Comment: "Encrypted at rest"
    refresh_token = Column(Text, nullable=True)  # Comment: "Encrypted at rest"
```

**Issues**:
- Comments claim "Encrypted at rest" but schema doesn't enforce encryption
- No database-level constraints to ensure encryption
- Tokens can be stored in plain text without validation

#### LLMOAuthCredential Model (`backend/core/models.py:6832-6882`)
```python
class LLMOAuthCredential(Base):
    access_token = Column(Text, nullable=False)  # Comment: "Encrypted access token"
    refresh_token = Column(Text, nullable=True)  # Comment: "Encrypted refresh token"
```

**Issues**:
- Same as IntegrationToken - comments claim encryption but no enforcement
- Used for LLM provider OAuth tokens (Google, OpenAI, Anthropic, Hugging Face)

---

## CRITICAL Security Vulnerabilities

### 1. Optional Encryption (CRITICAL)

**Location**: `backend/core/llm_oauth_handler.py:446-449`

```python
if not self.encryption_key:
    # Generate warning but allow operation in development
    logger.warning("No encryption key configured - storing tokens in plain text (INSECURE)")
    return token  # ⚠️ RETURNS PLAIN TEXT TOKEN
```

**Impact**:
- Tokens stored in plain text in database when `BYOK_ENCRYPTION_KEY` not set
- System continues operation instead of failing securely
- Any database backup, log export, or SQL dump exposes all integration tokens

**Affected Components**:
- All integration OAuth tokens (Slack, Salesforce, HubSpot, Google, Microsoft, etc.)
- All LLM provider OAuth tokens (Google AI, OpenAI, Anthropic, Hugging Face)
- API keys stored in IntegrationToken model

**Risk Level**: CRITICAL
- Could lead to complete compromise of third-party accounts
- Data breach of database exposes all customer integrations
- Violates SOC 2, HIPAA, PCI DSS encryption-at-rest requirements

---

### 2. Encryption Key Logged in Plaintext (CRITICAL)

**Location**: `backend/core/privsec/token_encryption.py:106-110`

```python
key_str = generate_encryption_key()
logger.info(
    "Generated temporary encryption key - save this for future use",
    extra={"generated_key": key_str, "security_note": "Save this key!"}  # ⚠️ KEY IN LOGS
)
```

**Impact**:
- Encryption keys exposed in structured logs
- Anyone with log access can decrypt all tokens
- Defeats the entire purpose of encryption

**Risk Level**: CRITICAL
- Defeats encryption completely
- Violates principle of never logging secrets
- Could lead to token decryption even after database is secured

---

### 3. No Encryption Validation (HIGH)

**Issue**: No validation that tokens are actually encrypted before storage

**Example**:
```python
# IntegrationToken.__repr__ exposes first 8 chars of token
def __repr__(self):
    masked_token = f"{self.access_token[:8]}..."  # ⚠️ Could expose plaintext
```

**Impact**:
- Plain text tokens could be stored without detection
- No way to audit which tokens are encrypted vs plain text
- Debug output could leak tokens

---

### 4. Backward Compatibility with Plain Text (MEDIUM)

**Location**: `backend/core/privsec/token_encryption.py:254-260`

```python
if not is_encrypted and allow_plaintext:  # ⚠️ DEFAULTS TO TRUE
    # Assume plaintext (backward compatibility)
    logger.debug("Decrypting plaintext token (backward compatibility)")
    return ciphertext  # Returns as-is
```

**Impact**:
- `decrypt_token()` defaults to `allow_plaintext=True`
- Could inadvertently return plain text tokens
- Makes it impossible to detect if encryption is working

---

### 5. Conflicting Encryption Key Configuration (MEDIUM)

**Issue**: Multiple environment variables referenced for encryption key

- `BYOK_ENCRYPTION_KEY` referenced in `token_encryption.py:97`
- `OAUTH_ENCRYPTION_KEY` referenced in `.env.oauth.template`
- No clear documentation on which to use

**Impact**:
- Operators may configure wrong key
- Tokens encrypted with one key cannot be decrypted with another
- Data loss if key is changed without re-encryption

---

## Encryption Implementation Analysis

### Token Encryption Module (`backend/core/privsec/token_encryption.py`)

**Strengths**:
✅ Uses Fernet symmetric encryption (AES-128-CBC with HMAC)
✅ Provides key generation utilities
✅ Includes token rotation support
✅ Hash-based token comparison utility

**Weaknesses**:
❌ Generates and logs temporary key when not configured
❌ No enforcement of encryption at storage layer
❌ Backward compatibility mode allows plain text
❌ No audit trail of encryption/decryption operations

### LLM OAuth Handler (`backend/core/llm_oauth_handler.py`)

**Strengths**:
✅ Supports OAuth 2.0 flow for Google, OpenAI, Anthropic, Hugging Face
✅ Automatic token refresh when expired
✅ Token usage tracking (last_used_at, usage_count)
✅ Credential revocation support

**Weaknesses**:
❌ Falls back to plain text when encryption key missing
❌ No validation that encryption succeeded
❌ Error handling could expose tokens in logs

---

## Affected Integrations

### OAuth 2.0 Providers (via IntegrationToken):
- Slack
- Salesforce
- HubSpot
- Google (Calendar, Drive, Gmail)
- Microsoft (Teams, OneDrive, Office 365)
- Stripe
- Zendesk
- Jira
- Asana
- Monday.com
- Notion
- Airtable
- And 50+ more integrations

### LLM Provider OAuth (via LLMOAuthCredential):
- Google AI Studio (Gemini)
- OpenAI
- Anthropic (Claude)
- Hugging Face

### API Key Storage (via IntegrationToken):
- Any integration using API keys instead of OAuth
- Keys stored in `access_token` field

---

## Recommended Remediation

### Immediate Actions (CRITICAL)

1. **Enforce Encryption at Application Level**

```python
def _encrypt_token(self, token: str) -> str:
    if not self.encryption_key:
        raise RuntimeError(
            "BYOK_ENCRYPTION_KEY not configured - cannot store tokens securely. "
            "Please set BYOK_ENCRYPTION_KEY environment variable."
        )
    # ... rest of encryption logic
```

2. **Remove Encryption Key from Logs**

```python
# NEVER log the generated key
logger.warning(
    "BYOK_ENCRYPTION_KEY not configured - please generate and set key",
    extra={"security_warning": True}  # ⚠️ Don't include the key
)
```

3. **Disable Plaintext Backward Compatibility**

```python
def decrypt_token(ciphertext: str, allow_plaintext: bool = False):  # ⚠️ Change default to False
    if not is_encrypted and allow_plaintext:
        logger.error("Attempted to decrypt plaintext token - encryption required")
        raise DecryptionError("Plaintext tokens not allowed")
```

4. **Add Encryption Validation**

```python
def store_oauth_credentials(self, ...):
    # ... after storing credential
    if not is_encrypted_value(credential.access_token):
        raise RuntimeError("Token storage failed - encryption not working")
```

### Short-term Actions (HIGH)

1. **Database Migration**: Add check constraint to verify tokens are encrypted
2. **Audit Script**: Scan existing tokens for plain text and flag them
3. **Monitoring**: Alert if plain text tokens are detected
4. **Documentation**: Clarify BYOK_ENCRYPTION_KEY vs OAUTH_ENCRYPTION_KEY

### Long-term Actions (MEDIUM)

1. **Key Rotation**: Implement automatic encryption key rotation
2. **HSM Integration**: Consider Hardware Security Module for key storage
3. **Envelope Encryption**: Use AWS KMS or Azure Key Vault
4. **Audit Logging**: Track all token encryption/decryption operations

---

## Security Checklist

- [ ] **CRITICAL**: Set `BYOK_ENCRYPTION_KEY` environment variable in production
- [ ] **CRITICAL**: Verify tokens are encrypted (should start with `gAAAA`)
- [ ] **CRITICAL**: Remove encryption key generation from logs
- [ ] **CRITICAL**: Fail closed when encryption not available
- [ ] **HIGH**: Audit existing tokens for plain text
- [ ] **HIGH**: Disable `allow_plaintext` default in `decrypt_token()`
- [ ] **MEDIUM**: Add database constraints for encrypted format
- [ ] **MEDIUM**: Implement key rotation procedure
- [ ] **MEDIUM**: Add monitoring for encryption failures

---

## Verification Commands

### Check if tokens are encrypted:

```sql
-- Check IntegrationToken for plain text (encrypted tokens start with 'gAAAA')
SELECT id, provider,
       CASE
         WHEN access_token LIKE 'gAAAA%' THEN 'ENCRYPTED'
         ELSE 'PLAIN TEXT - SECURITY ISSUE'
       END as encryption_status
FROM integration_tokens
LIMIT 10;

-- Check LLMOAuthCredential for plain text
SELECT id, provider_id,
       CASE
         WHEN access_token LIKE 'gAAAA%' THEN 'ENCRYPTED'
         ELSE 'PLAIN TEXT - SECURITY ISSUE'
       END as encryption_status
FROM llm_oauth_credentials;
```

### Check if encryption key is configured:

```bash
# Should return a 44-character base64 string
echo $BYOK_ENCRYPTION_KEY | wc -c

# Validate key format (should output "Valid Fernet key")
python3 -c "
from cryptography.fernet import Fernet
import os
key = os.getenv('BYOK_ENCRYPTION_KEY')
try:
    Fernet(key.encode())
    print('Valid Fernet key')
except:
    print('INVALID key format')
"
```

---

## Compliance Impact

These vulnerabilities may violate the following compliance requirements:

- **SOC 2 Type II**: Encryption at rest for sensitive data (CC6.1)
- **HIPAA**: Encryption of ePHI (§164.312(a)(2)(iv))
- **PCI DSS**: Encryption of stored account data (Requirement 3)
- **GDPR**: Appropriate technical measures for data security (Article 32)
- **ISO 27001**: Cryptography controls (A.10.1)

---

## References

- Token Encryption Module: `backend/core/privsec/token_encryption.py:1-495`
- LLM OAuth Handler: `backend/core/llm_oauth_handler.py:1-506`
- Database Models: `backend/core/models.py:4092-4149`, `backend/core/models.py:6832-6882`
- Database Migration: `backend/alembic/versions/20260426_add_llm_oauth_credentials.py`

---

## Conclusion

The integration token management system has **critical security vulnerabilities** that must be addressed immediately. While encryption utilities exist, they are not enforced, allowing tokens to be stored in plain text. The system fails open to insecure behavior rather than failing closed.

**Priority**: CRITICAL - Address immediately before production deployment or any compliance audit.

---

*Generated: 2026-04-27*
*Reviewer: Claude Code Security Analysis*
