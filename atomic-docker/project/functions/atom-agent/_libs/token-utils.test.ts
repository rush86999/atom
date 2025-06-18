import { encryptToken, decryptToken, saveAtomGoogleCalendarTokens, getAtomGoogleCalendarTokens } from './token-utils';
import * as constants from './constants'; // Import to allow modification of its mocked properties
import crypto from 'crypto'; // Needed for generating valid key/iv for some tests if not using mocks

// Mock the constants module
// We will set specific mock values for KEY and IV per test or describe block if needed.
jest.mock('./constants', () => ({
  ...jest.requireActual('./constants'), // Import and retain default behavior for other constants
  ATOM_TOKEN_ENCRYPTION_KEY: '0000000000000000000000000000000000000000000000000000000000000000', // 64 hex chars -> 32 bytes
  ATOM_TOKEN_ENCRYPTION_IV: '00000000000000000000000000000000',   // 32 hex chars -> 16 bytes
}));

// Mock got for Hasura calls in save/get token functions
jest.mock('got');
const got = require('got') as jest.Mocked<typeof import('got')>;


describe('Token Utilities', () => {
  let consoleErrorSpy: jest.SpyInstance;

  beforeEach(() => {
    jest.clearAllMocks();
    // Spy on console.error and suppress its output during tests
    consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    consoleErrorSpy.mockRestore();
  });

  // Helper to set mock values for constants
  const setMockConstants = (key?: string | null, iv?: string | null) => {
    Object.defineProperty(constants, 'ATOM_TOKEN_ENCRYPTION_KEY', {
      value: key,
      configurable: true,
      writable: true,
    });
    Object.defineProperty(constants, 'ATOM_TOKEN_ENCRYPTION_IV', {
      value: iv,
      configurable: true,
      writable: true,
    });
  };

  const validTestKey = crypto.randomBytes(32).toString('hex');
  const validTestIv = crypto.randomBytes(16).toString('hex');

  describe('encryptToken', () => {
    beforeEach(() => {
        setMockConstants(validTestKey, validTestIv);
    });

    it('should successfully encrypt a valid token string', async () => {
      const token = 'mySecretToken123';
      const encrypted = await encryptToken(token);
      expect(encrypted).not.toBeNull();
      expect(encrypted).not.toBe(token);
      expect(typeof encrypted).toBe('string');
    });

    it('should return null for null token input', async () => {
      // @ts-ignore testing invalid input
      expect(await encryptToken(null)).toBeNull();
    });

    it('should return empty string for empty string token input', async () => {
      expect(await encryptToken('')).toBe('');
    });

    it('should return null if ATOM_TOKEN_ENCRYPTION_KEY is missing', async () => {
      setMockConstants(null, validTestIv);
      expect(await encryptToken('test')).toBeNull();
      expect(consoleErrorSpy).toHaveBeenCalledWith("Encryption key or IV is missing. Cannot encrypt token.");
    });

    it('should return null if ATOM_TOKEN_ENCRYPTION_IV is missing', async () => {
      setMockConstants(validTestKey, null);
      expect(await encryptToken('test')).toBeNull();
      expect(consoleErrorSpy).toHaveBeenCalledWith("Encryption key or IV is missing. Cannot encrypt token.");
    });

    it('should return null if ATOM_TOKEN_ENCRYPTION_KEY has invalid length', async () => {
      setMockConstants('invalidkey', validTestIv); // Too short
      expect(await encryptToken('test')).toBeNull();
      expect(consoleErrorSpy).toHaveBeenCalledWith(expect.stringContaining("Invalid key or IV length"));
    });

    it('should return null if ATOM_TOKEN_ENCRYPTION_IV has invalid length', async () => {
      setMockConstants(validTestKey, 'invalidiv'); // Too short
      expect(await encryptToken('test')).toBeNull();
      expect(consoleErrorSpy).toHaveBeenCalledWith(expect.stringContaining("Invalid key or IV length"));
    });

    it('should handle crypto operation errors gracefully', async () => {
        jest.spyOn(crypto, 'createCipheriv').mockImplementationOnce(() => { throw new Error('Crypto failure'); });
        expect(await encryptToken('test')).toBeNull();
        expect(consoleErrorSpy).toHaveBeenCalledWith("Error during token encryption:", expect.any(Error));
    });
  });

  describe('decryptToken', () => {
    beforeEach(() => {
        setMockConstants(validTestKey, validTestIv);
    });

    it('should successfully decrypt a previously encrypted string (roundtrip)', async () => {
      const originalToken = 'mySuperSecretToken!@#';
      const encrypted = await encryptToken(originalToken);
      expect(encrypted).not.toBeNull();
      const decrypted = await decryptToken(encrypted as string);
      expect(decrypted).toBe(originalToken);
    });

    it('should return null for null encrypted token input', async () => {
      // @ts-ignore testing invalid input
      expect(await decryptToken(null)).toBeNull();
    });

    it('should return empty string for empty string encrypted token input', async () => {
      expect(await decryptToken('')).toBe('');
    });

    it('should return null if ATOM_TOKEN_ENCRYPTION_KEY is missing for decryption', async () => {
      setMockConstants(null, validTestIv);
      expect(await decryptToken('encrypted_test')).toBeNull();
      expect(consoleErrorSpy).toHaveBeenCalledWith("Encryption key or IV is missing. Cannot decrypt token.");
    });

    it('should return null if ATOM_TOKEN_ENCRYPTION_IV is missing for decryption', async () => {
      setMockConstants(validTestKey, null);
      expect(await decryptToken('encrypted_test')).toBeNull();
      expect(consoleErrorSpy).toHaveBeenCalledWith("Encryption key or IV is missing. Cannot decrypt token.");
    });

    it('should return null if ATOM_TOKEN_ENCRYPTION_KEY has invalid length for decryption', async () => {
      setMockConstants('invalidkey_dec', validTestIv);
      expect(await decryptToken('encrypted_test')).toBeNull();
      expect(consoleErrorSpy).toHaveBeenCalledWith(expect.stringContaining("Invalid key or IV length"));
    });

    it('should return null if ATOM_TOKEN_ENCRYPTION_IV has invalid length for decryption', async () => {
      setMockConstants(validTestKey, 'invalidiv_dec');
      expect(await decryptToken('encrypted_test')).toBeNull();
      expect(consoleErrorSpy).toHaveBeenCalledWith(expect.stringContaining("Invalid key or IV length"));
    });

    it('should return null for a malformed base64 string', async () => {
      expect(await decryptToken('this is not base64!')).toBeNull();
      expect(consoleErrorSpy).toHaveBeenCalledWith("Error during token decryption:", expect.any(Error));
    });

    it('should return null for a valid base64 string that is not a valid ciphertext', async () => {
      // "test" in base64 is "dGVzdA=="
      expect(await decryptToken('dGVzdA==')).toBeNull();
      expect(consoleErrorSpy).toHaveBeenCalledWith("Error during token decryption:", expect.any(Error));
    });
  });

  describe('saveAtomGoogleCalendarTokens', () => {
    const mockTokens = {
        access_token: 'access',
        refresh_token: 'refresh',
        expiry_date: Date.now() + 3600000,
        scope: 'scope',
        token_type: 'Bearer',
      };

    beforeEach(() => {
        setMockConstants(validTestKey, validTestIv); // Ensure valid keys for encryption part
        got.post.mockReset(); // Reset got mock specifically
    });

    it('should throw error if encryption of accessToken fails', async () => {
      // Forcing encryptToken to return null for accessToken
      const originalEncryptToken = require('./token-utils').encryptToken;
      const encryptTokenMock = jest.spyOn(require('./token-utils'), 'encryptToken')
        .mockImplementation(async (token: string) => {
          if (token === mockTokens.access_token) return null;
          return originalEncryptToken(token); // Call original for other tokens if any
        });

      await expect(saveAtomGoogleCalendarTokens('user1', mockTokens))
        .rejects.toThrow("Token encryption failed. Cannot save tokens.");
      expect(consoleErrorSpy).toHaveBeenCalledWith("Failed to encrypt tokens. Aborting save.");
      expect(got.post).not.toHaveBeenCalled();
      encryptTokenMock.mockRestore();
    });

    it('should throw error if encryption of refreshToken fails (when refreshToken is present)', async () => {
      const originalEncryptToken = require('./token-utils').encryptToken;
      const encryptTokenMock = jest.spyOn(require('./token-utils'), 'encryptToken')
        .mockImplementation(async (token: string) => {
          if (token === mockTokens.refresh_token) return null;
          // Need to ensure access_token encrypts fine for this specific test case
          if (token === mockTokens.access_token) return `encrypted_${token}`;
          return originalEncryptToken(token);
        });

      await expect(saveAtomGoogleCalendarTokens('user1', mockTokens))
        .rejects.toThrow("Token encryption failed. Cannot save tokens.");
      expect(consoleErrorSpy).toHaveBeenCalledWith("Failed to encrypt tokens. Aborting save.");
      expect(got.post).not.toHaveBeenCalled();
      encryptTokenMock.mockRestore();
    });

    it('should successfully call Hasura with encrypted tokens', async () => {
        got.post.mockResolvedValue({
            json: async () => ({ data: { insert_Calendar_Integration_one: { id: 'new_id', userId: 'user1' } } })
        } as any);

        await saveAtomGoogleCalendarTokens('user1', mockTokens);
        expect(got.post).toHaveBeenCalledTimes(1);
        const calledWith = got.post.mock.calls[0][1] as any; // Get the options argument
        expect(calledWith.json.variables.accessToken).toContain('encrypted_');
        expect(calledWith.json.variables.refreshToken).toContain('encrypted_');
    });
  });

  describe('getAtomGoogleCalendarTokens', () => {
    beforeEach(() => {
        setMockConstants(validTestKey, validTestIv);
        got.post.mockReset();
    });

    it('should return null if decryption of accessToken fails', async () => {
        got.post.mockResolvedValue({
            json: async () => ({ data: { Calendar_Integration: [{ token: 'encrypted_access', refreshToken: 'encrypted_refresh' }] } })
        } as any);

        const originalDecryptToken = require('./token-utils').decryptToken;
        const decryptTokenMock = jest.spyOn(require('./token-utils'), 'decryptToken')
            .mockImplementation(async (token: string) => {
                if (token === 'encrypted_access') return null; // Simulate access token decryption failure
                return originalDecryptToken(token);
            });

        const result = await getAtomGoogleCalendarTokens('user1');
        expect(result).toBeNull();
        expect(consoleErrorSpy).toHaveBeenCalledWith("Failed to decrypt access token for userId: user1. Returning null.");
        decryptTokenMock.mockRestore();
    });

    it('should return tokens with null refreshToken if only refreshToken decryption fails', async () => {
        got.post.mockResolvedValue({
            json: async () => ({
                data: {
                    Calendar_Integration: [{
                        token: 'encrypted_access_valid',
                        refreshToken: 'encrypted_refresh_invalid',
                        expiresAt: new Date(Date.now() + 3600000).toISOString(),
                        scope: 'scope',
                        token_type: 'Bearer'
                    }]
                }
            })
        } as any);

        const decryptTokenMock = jest.spyOn(require('./token-utils'), 'decryptToken')
            .mockImplementation(async (token: string) => {
                if (token === 'encrypted_access_valid') return 'decrypted_access_valid';
                if (token === 'encrypted_refresh_invalid') return null; // Simulate refresh token decryption failure
                return token; // Should not happen for this test
            });

        const result = await getAtomGoogleCalendarTokens('user1');
        expect(result).not.toBeNull();
        expect(result?.access_token).toBe('decrypted_access_valid');
        expect(result?.refresh_token).toBeUndefined(); // because it was null after failed decryption
        expect(consoleErrorSpy).toHaveBeenCalledWith("Failed to decrypt refresh token for userId: user1. Proceeding without it.");
        decryptTokenMock.mockRestore();
    });

    it('should successfully fetch and decrypt tokens', async () => {
        const encryptedAccessToken = await encryptToken('real_access_token');
        const encryptedRefreshToken = await encryptToken('real_refresh_token');
        const expiry = new Date(Date.now() + 3600000);

        got.post.mockResolvedValue({
            json: async () => ({
                data: {
                    Calendar_Integration: [{
                        token: encryptedAccessToken,
                        refreshToken: encryptedRefreshToken,
                        expiresAt: expiry.toISOString(),
                        scope: 'read write',
                        token_type: 'Bearer'
                    }]
                }
            })
        } as any);

        const result = await getAtomGoogleCalendarTokens('user1');
        expect(result).not.toBeNull();
        expect(result?.access_token).toBe('real_access_token');
        expect(result?.refresh_token).toBe('real_refresh_token');
        expect(result?.expiry_date).toBe(expiry.getTime());
        expect(result?.scope).toBe('read write');
    });
  });
});
