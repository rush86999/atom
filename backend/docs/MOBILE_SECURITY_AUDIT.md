# Mobile Security Audit — Round 39

**Date**: June 22, 2026
**Scope**: `mobile/src/` — token storage, biometric auth, deep links

## Findings

### HIGH-1: Access tokens stored in unencrypted `AsyncStorage`

**Files affected**:
- `src/contexts/AuthContext.tsx:172`
- `src/contexts/WebSocketContext.tsx:93`
- `src/contexts/DeviceContext.tsx:167,203,234,421,470`
- `src/screens/chat/ChatTabScreen.tsx:101`
- `src/services/deviceSocket.ts:90`
- `src/services/api.ts:58`

**Risk**: `AsyncStorage` on Android stores data in an unencrypted SQLite database.
On a rooted/jailbroken device, or via a backup extraction, an attacker can read
`atom_access_token` and `auth_token` directly from the filesystem → full account
takeover. iOS is safer (sandboxed) but still not using the Keychain.

`expo-secure-store` IS already imported in `AuthContext.tsx` and
`ForgotPasswordScreen.tsx`, but the main access token flow uses AsyncStorage
instead.

**Recommended fix**: Replace all `AsyncStorage.setItem('atom_access_token', ...)`
and `AsyncStorage.getItem('atom_access_token')` calls with:
```typescript
import * as SecureStore from 'expo-secure-store';
await SecureStore.setItemAsync('atom_access_token', token);
const token = await SecureStore.getItemAsync('atom_access_token');
```
`SecureStore` uses iOS Keychain and Android EncryptedSharedPreferences.

### MEDIUM-2: No jailbreak/root detection

No `expo-jail-break` or similar detection found. On rooted devices, the app
should refuse to run or warn the user, since filesystem protections are
bypassed.

### LOW-3: Deep link handler input validation unverified

`atom://` deep links are handled but no evidence of input sanitization on the
parameters. Malicious deep links could inject agent IDs or workflow IDs.

## Summary

| Severity | Count | Status |
|----------|-------|--------|
| HIGH (token storage) | 10 sites | Migrate to SecureStore |
| MEDIUM (root detection) | — | Add jailbreak detection |
| LOW (deep links) | — | Validate deep link params |

**No code changes applied** — mobile changes require device testing and were
out of scope for the backend-focused bug hunt.
