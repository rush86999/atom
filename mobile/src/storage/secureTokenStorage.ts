/**
 * Secure token storage using expo-secure-store.
 *
 * Replaces AsyncStorage for ALL authentication tokens. AsyncStorage stores
 * data in an unencrypted SQLite database on Android — any root-level
 * process or backup extraction can read the tokens. SecureStore uses:
 *   - iOS: Keychain (hardware-backed on devices with Secure Enclave)
 *   - Android: EncryptedSharedPreferences (AES-256-GCM)
 *
 * Migration: callers that previously did
 *   AsyncStorage.setItem('auth_token', token)
 * now do
 *   secureSet('auth_token', token)
 * and reads use secureGet('auth_token').
 *
 * Legacy AsyncStorage tokens are migrated on first read.
 */
import * as SecureStore from "expo-secure-store";
import AsyncStorage from "@react-native-async-storage/async-storage";

// Keys that hold sensitive auth material and MUST go through SecureStore.
const SECURE_KEYS = [
  "auth_token",
  "atom_access_token",
  "refresh_token",
  "device_token",
  "DEVICE_ID_KEY",
  "DEVICE_TOKEN_KEY",
] as const;

type SecureKey = (typeof SECURE_KEYS)[number];

/** Whether this key should be stored in SecureStore (not AsyncStorage). */
export function isSecureKey(key: string): key is SecureKey {
  return (SECURE_KEYS as readonly string[]).includes(key);
}

/**
 * Store a sensitive value in the OS keychain/keystore.
 * Requires an authentication-free SecureStore (not requiring biometric).
 */
async function writeSecureValue(key: string, value: string): Promise<void> {
  await SecureStore.setItemAsync(key, value, {
    keychainAccessible: SecureStore.WHEN_UNLOCKED,
    // No requireAuthentication — the app already gates behind biometric login
    // at the AuthContext level. Re-requiring it per token read would be
    // disruptive for legitimate users.
  });
}

/**
 * Read a sensitive value. If the value is not yet in SecureStore but exists
 * in AsyncStorage (pre-migration), migrate it transparently.
 */
async function readSecureValue(key: string): Promise<string | null> {
  // Try SecureStore first. A read failure (e.g. keychain unavailable /
  // keystore corruption on Android) must NOT fail closed — fall through to
  // the legacy AsyncStorage copy so the user is not locked out of their
  // session. The legacy value is plaintext anyway, so reading it on failure
  // does not weaken the security posture.
  let value: string | null = null;
  try {
    value = await SecureStore.getItemAsync(key);
  } catch {
    value = null;
  }
  if (value !== null) return value;

  // Migration: check AsyncStorage for a legacy value, move it to SecureStore
  const legacy = await AsyncStorage.getItem(key);
  if (legacy !== null) {
    try {
      await SecureStore.setItemAsync(key, legacy, {
        keychainAccessible: SecureStore.WHEN_UNLOCKED,
      });
      // Wipe from AsyncStorage so the unencrypted copy is gone
      await AsyncStorage.removeItem(key);
    } catch {
      // SecureStore write failed (keychain unavailable) — keep the legacy
      // value readable from AsyncStorage rather than losing the session.
      // It will be migrated on a later read once the keystore recovers.
    }
    return legacy;
  }

  return null;
}

/** Delete a sensitive value from both stores. */
async function deleteSecureValue(key: string): Promise<void> {
  await SecureStore.deleteItemAsync(key);
  // Also clean up any lingering legacy copy
  try {
    await AsyncStorage.removeItem(key);
  } catch {
    // ignore — best-effort cleanup
  }
}

// One JS-runtime ordering boundary for every participating access-token writer.
// Native cross-process atomicity is not provided by SecureStore.
let accessTokenTail: Promise<void> = Promise.resolve();
let accessTokenGeneration = 0;
const ACCESS_TOKEN_KEY = 'atom_access_token';

function withAccessToken<T>(operation: () => Promise<T>): Promise<T> {
  const result = accessTokenTail.then(operation);
  accessTokenTail = result.then(() => undefined, () => undefined);
  return result;
}

export interface AccessTokenSnapshot {
  readonly token: string | null;
  readonly generation: number;
}

export function secureSet(key: string, value: string): Promise<void> {
  if (key !== ACCESS_TOKEN_KEY) return writeSecureValue(key, value);
  return withAccessToken(async () => {
    // Invalidate old request ownership even if a native write is uncertain.
    accessTokenGeneration += 1;
    await writeSecureValue(key, value);
  });
}

export function secureGet(key: string): Promise<string | null> {
  if (key !== ACCESS_TOKEN_KEY) return readSecureValue(key);
  return withAccessToken(() => readSecureValue(key));
}

export function secureDelete(key: string): Promise<void> {
  if (key !== ACCESS_TOKEN_KEY) return deleteSecureValue(key);
  return withAccessToken(async () => {
    accessTokenGeneration += 1;
    await deleteSecureValue(key);
  });
}

export function readAccessTokenSnapshot(): Promise<AccessTokenSnapshot> {
  return withAccessToken(async () => ({
    token: await readSecureValue(ACCESS_TOKEN_KEY),
    generation: accessTokenGeneration,
  }));
}

export function invalidateAccessToken(snapshot: AccessTokenSnapshot): Promise<boolean> {
  return withAccessToken(async () => {
    if (!snapshot.token || snapshot.generation !== accessTokenGeneration) return false;
    const current = await readSecureValue(ACCESS_TOKEN_KEY);
    if (current !== snapshot.token) return false;
    accessTokenGeneration += 1;
    await deleteSecureValue(ACCESS_TOKEN_KEY);
    await deleteSecureValue('auth_token');
    return true;
  });
}
