# OAuth Token Encryption Migration Guide

## Overview

This guide explains how to encrypt existing OAuth tokens in the database using AES-256-GCM encryption.

## Security Critical

OAuth tokens (access tokens, refresh tokens, ID tokens) are currently stored in plaintext. This migration encrypts all tokens at rest.

## Prerequisites

1. Generate a secure encryption key (64 hex characters = 256 bits):
```bash
node -e "console.log(crypto.randomBytes(32).toString('hex'))"
```

2. Set the `TOKEN_ENCRYPTION_KEY` environment variable:
```bash
export TOKEN_ENCRYPTION_KEY=<your-64-hex-char-key>
```

Add this to your `.env` file or production environment variables.

## Migration Steps

### Step 1: Backup Database

**CRITICAL**: Always backup before migration:
```bash
pg_dump $DATABASE_URL > backup-before-token-encryption-$(date +%Y%m%d).sql
```

### Step 2: Dry Run Migration

Test the migration without making changes:
```bash
cd frontend-nextjs
DRY_RUN=true \
TOKEN_ENCRYPTION_KEY=<your-key> \
DATABASE_URL=$DATABASE_URL \
npx ts-node scripts/migrate-oauth-tokens.ts
```

### Step 3: Run Migration

Execute the actual migration:
```bash
cd frontend-nextjs
TOKEN_ENCRYPTION_KEY=<your-key> \
DATABASE_URL=$DATABASE_URL \
npx ts-node scripts/migrate-oauth-tokens.ts
```

### Step 4: Verify

Check that tokens are encrypted:
```sql
SELECT
  id,
  user_id,
  service_name,
  is_encrypted,
  LENGTH(access_token) as access_token_length,
  SUBSTRING(access_token, 1, 20) as access_token_preview
FROM user_tokens
ORDER BY updated_at DESC
LIMIT 10;
```

Encrypted tokens should have:
- `is_encrypted = TRUE`
- `access_token_length` >= 96 characters (32 bytes IV + 32 bytes AuthTag + encrypted data)
- `access_token_preview` containing only hexadecimal characters (0-9, a-f)

## Token Encryption Format

Encrypted tokens use AES-256-GCM with the following format:
```
IV (16 bytes, 32 hex chars) + AuthTag (16 bytes, 32 hex chars) + EncryptedData (variable, hex)
```

Total minimum length: 64 hex characters (32 bytes).

## Updating OAuth Callbacks

After migration, all OAuth callback handlers should encrypt tokens before storage. Use the `encryptToken()` function:

```typescript
import { encryptToken } from '@lib/tokenEncryption';

// Encrypt access token
const encryptedAccessToken = encryptToken(tokens.accessToken);

// Encrypt refresh token (if present)
const encryptedRefreshToken = tokens.refreshToken
  ? encryptToken(tokens.refreshToken)
  : null;

// Store in database
await db.query(`
  INSERT INTO user_tokens (access_token, refresh_token, is_encrypted, ...)
  VALUES ($1, $2, TRUE, ...)
`, [encryptedAccessToken, encryptedRefreshToken, ...]);
```

## Decrypting Tokens

To decrypt tokens (for API calls to OAuth providers):
```typescript
import { decryptToken } from '@lib/tokenEncryption';

// Retrieve encrypted token from database
const encryptedToken = row.access_token;

// Decrypt for use
const plaintextToken = decryptToken(encryptedToken);

// Use plaintext token for API call
const response = await fetch('https://api.example.com', {
  headers: { 'Authorization': `Bearer ${plaintextToken}` }
});
```

## Files Requiring Updates

All OAuth callback files in `frontend-nextjs/pages/api/`:
- `auth/*/callback.ts`
- `integrations/*/auth/callback.ts`
- `atom/auth/*/callback.ts`
- `msteams/oauth/callback.ts`
- `slack/oauth/callback.ts`
- And 20+ other callback files

## Rollback Plan

If migration fails:
1. Database has transaction rollback built-in
2. Restore from backup: `psql $DATABASE_URL < backup-before-token-encryption-YYYYMMDD.sql`
3. Report issue with migration script output

## Security Notes

1. **Never log plaintext tokens** - The encryption service prevents accidental logging
2. **Key rotation** - If encryption key is compromised, use `reencrypt()` method
3. **Key storage** - Store `TOKEN_ENCRYPTION_KEY` in secure secrets manager (AWS KMS, Azure Key Vault, etc.)
4. **Key requirements** - Must be exactly 64 hex characters (256 bits)
5. **Production safety** - Encryption service throws error if key format is invalid

## Testing

Test encryption/decryption:
```typescript
import { encryptToken, decryptToken } from '@lib/tokenEncryption';

const original = 'my-test-token-abc123';
const encrypted = encryptToken(original);
const decrypted = decryptToken(encrypted);

console.log('Original:', original);
console.log('Encrypted:', encrypted); // 64+ hex characters
console.log('Decrypted:', decrypted);
console.log('Match:', original === decrypted); // Should be true
```

## Monitoring

After migration, monitor for:
- Failed token decryptions (indicates corrupted data or wrong key)
- OAuth API call failures (indicates encryption issue)
- Performance impact (encryption adds ~1-2ms per operation)

## Support

For issues or questions:
1. Check migration script output for error messages
2. Verify `TOKEN_ENCRYPTION_KEY` is exactly 64 hex characters
3. Ensure database user has ALTER TABLE permission
4. Review logs for decryption failures

## Success Criteria

Migration is successful when:
- ✅ All tokens have `is_encrypted = TRUE`
- ✅ Encrypted tokens are >= 64 hex characters
- ✅ OAuth integrations still work (tokens decrypt correctly)
- ✅ Zero failed decryptions in logs
- ✅ No OAuth API call failures

---

**Last Updated**: February 4, 2026
**Related**: `frontend-nextjs/src/lib/tokenEncryption.ts`, `scripts/migrate-oauth-tokens.ts`
