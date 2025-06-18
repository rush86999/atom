import { encryptToken, decryptToken, saveAtomGoogleCalendarTokens, getAtomGoogleCalendarTokens, deleteAtomGoogleCalendarTokens } from './token-utils';
import * as constants from './constants'; // Import to allow modification of its mocked properties
import crypto from 'crypto';
// Mock got for Hasura calls
jest.mock('got');
const got = require('got') as jest.Mocked<typeof import('got')>;

// Mock the constants module
// We will set specific mock values for KEY and IV per test or describe block if needed.
jest.mock('./constants', () => {
    const actualConstants = jest.requireActual('./constants');
    return {
        ...actualConstants,
        ATOM_TOKEN_ENCRYPTION_KEY: '0000000000000000000000000000000000000000000000000000000000000000', // Default mock key
        ATOM_TOKEN_ENCRYPTION_IV: '00000000000000000000000000000000',   // Default mock IV
        HASURA_GRAPHQL_URL: 'mock_hasura_url', // Default mock Hasura URL
        HASURA_ADMIN_SECRET: 'mock_hasura_secret', // Default mock Hasura Secret
        ATOM_CALENDAR_RESOURCE_NAME: 'google_atom_calendar', // Actual value for tests
        ATOM_CLIENT_TYPE: 'atom_agent', // Actual value for tests
    };
});


describe('Token Utilities', () => {
  let consoleErrorSpy: jest.SpyInstance;
  const validTestKey = crypto.randomBytes(32).toString('hex');
  const validTestIv = crypto.randomBytes(16).toString('hex');

  // Helper to set mock values for constants
  const setMockEncryptionConstants = (key?: string | null, iv?: string | null) => {
    Object.defineProperty(constants, 'ATOM_TOKEN_ENCRYPTION_KEY', { value: key, configurable: true, writable: true });
    Object.defineProperty(constants, 'ATOM_TOKEN_ENCRYPTION_IV', { value: iv, configurable: true, writable: true });
  };

  const setMockHasuraConstants = (hasuraUrl?: string | null, hasuraSecret?: string | null) => {
    Object.defineProperty(constants, 'HASURA_GRAPHQL_URL', { value: hasuraUrl, configurable: true, writable: true });
    Object.defineProperty(constants, 'HASURA_ADMIN_SECRET', { value: hasuraSecret, configurable: true, writable: true });
  }

  beforeEach(() => {
    jest.clearAllMocks();
    consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    // Set default valid encryption keys for encrypt/decrypt tests
    setMockEncryptionConstants(validTestKey, validTestIv);
    // Set default valid Hasura constants for Hasura interaction tests
    setMockHasuraConstants('mock_hasura_url', 'mock_hasura_secret');

  });

  afterEach(() => {
    consoleErrorSpy.mockRestore();
  });

  describe('encryptToken', () => {
    it('should successfully encrypt a valid token string', async () => {
      const token = 'mySecretToken123';
      const encrypted = await encryptToken(token);
      expect(encrypted).not.toBeNull();
      expect(encrypted).not.toBe(token);
      expect(typeof encrypted).toBe('string');
    });

    it('should return null for null token input', async () => {
      expect(await encryptToken(null as any)).toBeNull();
    });

    it('should return empty string for empty string token input', async () => {
      expect(await encryptToken('')).toBe('');
    });

    it('should return null if ATOM_TOKEN_ENCRYPTION_KEY is missing', async () => {
      setMockEncryptionConstants(null, validTestIv);
      expect(await encryptToken('test')).toBeNull();
      expect(consoleErrorSpy).toHaveBeenCalledWith("Encryption key or IV is missing. Cannot encrypt token.");
    });

    it('should return null if ATOM_TOKEN_ENCRYPTION_IV is missing', async () => {
      setMockEncryptionConstants(validTestKey, null);
      expect(await encryptToken('test')).toBeNull();
      expect(consoleErrorSpy).toHaveBeenCalledWith("Encryption key or IV is missing. Cannot encrypt token.");
    });

    it('should return null if ATOM_TOKEN_ENCRYPTION_KEY has invalid length', async () => {
      setMockEncryptionConstants('invalidkey', validTestIv); // Too short
      expect(await encryptToken('test')).toBeNull();
      expect(consoleErrorSpy).toHaveBeenCalledWith(expect.stringContaining("Invalid key or IV length"));
    });

    it('should return null if ATOM_TOKEN_ENCRYPTION_IV has invalid length', async () => {
      setMockEncryptionConstants(validTestKey, 'invalidiv'); // Too short
      expect(await encryptToken('test')).toBeNull();
      expect(consoleErrorSpy).toHaveBeenCalledWith(expect.stringContaining("Invalid key or IV length"));
    });

    it('should handle crypto operation errors gracefully', async () => {
        const cryptoErrorSpy = jest.spyOn(crypto, 'createCipheriv').mockImplementationOnce(() => { throw new Error('Crypto failure'); });
        expect(await encryptToken('test')).toBeNull();
        expect(consoleErrorSpy).toHaveBeenCalledWith("Error during token encryption:", expect.any(Error));
        cryptoErrorSpy.mockRestore();
    });
  });

  describe('decryptToken', () => {
    it('should successfully decrypt a previously encrypted string (roundtrip)', async () => {
      const originalToken = 'mySuperSecretToken!@#';
      const encrypted = await encryptToken(originalToken);
      expect(encrypted).not.toBeNull();
      const decrypted = await decryptToken(encrypted as string);
      expect(decrypted).toBe(originalToken);
    });

    it('should return null for null encrypted token input', async () => {
      expect(await decryptToken(null as any)).toBeNull();
    });

    it('should return empty string for empty string encrypted token input', async () => {
      expect(await decryptToken('')).toBe('');
    });

    it('should return null if ATOM_TOKEN_ENCRYPTION_KEY is missing for decryption', async () => {
      setMockEncryptionConstants(null, validTestIv);
      expect(await decryptToken('encrypted_test')).toBeNull();
      expect(consoleErrorSpy).toHaveBeenCalledWith("Encryption key or IV is missing. Cannot decrypt token.");
    });

    it('should return null if ATOM_TOKEN_ENCRYPTION_IV is missing for decryption', async () => {
      setMockEncryptionConstants(validTestKey, null);
      expect(await decryptToken('encrypted_test')).toBeNull();
      expect(consoleErrorSpy).toHaveBeenCalledWith("Encryption key or IV is missing. Cannot decrypt token.");
    });

    it('should return null if ATOM_TOKEN_ENCRYPTION_KEY has invalid length for decryption', async () => {
      setMockEncryptionConstants('invalidkey_dec', validTestIv);
      expect(await decryptToken('encrypted_test')).toBeNull();
      expect(consoleErrorSpy).toHaveBeenCalledWith(expect.stringContaining("Invalid key or IV length"));
    });

    it('should return null if ATOM_TOKEN_ENCRYPTION_IV has invalid length for decryption', async () => {
      setMockEncryptionConstants(validTestKey, 'invalidiv_dec');
      expect(await decryptToken('encrypted_test')).toBeNull();
      expect(consoleErrorSpy).toHaveBeenCalledWith(expect.stringContaining("Invalid key or IV length"));
    });

    it('should return null for a malformed base64 string', async () => {
      expect(await decryptToken('this is not base64!')).toBeNull();
      expect(consoleErrorSpy).toHaveBeenCalledWith("Error during token decryption:", expect.any(Error));
    });

    it('should return null for a valid base64 string that is not a valid ciphertext for the key/IV', async () => {
      expect(await decryptToken('dGVzdA==')).toBeNull(); // "test" in base64
      expect(consoleErrorSpy).toHaveBeenCalledWith("Error during token decryption:", expect.any(Error));
    });
  });

  describe('Token Utilities - Hasura Interactions', () => {
    const mockUserId = 'test-user-id';
    const mockAppEmail = 'user@example.com';
    const mockTokenData = {
      access_token: 'test_access_token',
      refresh_token: 'test_refresh_token',
      expiry_date: Date.now() + 3600000,
      scope: 'test_scope',
      token_type: 'Bearer',
    };

    describe('saveAtomGoogleCalendarTokens', () => {
        it('should throw error if encryption of accessToken fails', async () => {
            setMockEncryptionConstants(null, validTestIv); // Cause encryption to fail
            await expect(saveAtomGoogleCalendarTokens(mockUserId, mockTokenData, mockAppEmail))
              .rejects.toThrow("Token encryption failed. Cannot save tokens.");
            expect(consoleErrorSpy).toHaveBeenCalledWith("Encryption key or IV is missing. Cannot encrypt token.");
            expect(consoleErrorSpy).toHaveBeenCalledWith("Failed to encrypt tokens. Aborting save.");
            expect(got.post).not.toHaveBeenCalled();
          });

          it('should throw error if encryption of refreshToken fails (when refreshToken is present)', async () => {
            // Make accessToken encryption succeed but refreshToken encryption fail
            const goodKey = validTestKey;
            const goodIv = validTestIv;
            const badKeyForRefresh = null;

            const encryptTokenSpy = jest.spyOn(require('./token-utils'), 'encryptToken')
              .mockImplementation(async (token: string) => {
                if (token === mockTokenData.access_token) {
                  setMockEncryptionConstants(goodKey, goodIv);
                  return `encrypted_${token}`; // Simulate good encryption
                }
                if (token === mockTokenData.refresh_token) {
                  setMockEncryptionConstants(badKeyForRefresh, goodIv); // Simulate bad key for refresh token
                  const actualModule = jest.requireActual('./token-utils');
                  return actualModule.encryptToken(token); // Will fail and return null
                }
                return `encrypted_${token}`;
              });

            await expect(saveAtomGoogleCalendarTokens(mockUserId, mockTokenData, mockAppEmail))
              .rejects.toThrow("Token encryption failed. Cannot save tokens.");
            expect(consoleErrorSpy).toHaveBeenCalledWith("Failed to encrypt tokens. Aborting save.");
            expect(got.post).not.toHaveBeenCalled();
            encryptTokenSpy.mockRestore();
          });

      it('should successfully save/upsert tokens to Hasura', async () => {
        setMockEncryptionConstants(validTestKey, validTestIv); // Ensure encryption works
        got.post.mockResolvedValue({
          json: jest.fn().mockResolvedValue({
            data: { insert_Calendar_Integration_one: { id: 'mock-db-id', userId: mockUserId } },
          }),
        } as any);

        const result = await saveAtomGoogleCalendarTokens(mockUserId, mockTokenData, mockAppEmail);

        expect(got.post).toHaveBeenCalledTimes(1);
        expect(got.post).toHaveBeenCalledWith('mock_hasura_url', expect.any(Object));
        const callOptions = got.post.mock.calls[0][1] as any;
        expect(callOptions.headers['x-hasura-admin-secret']).toBe('mock_hasura_secret');

        const gqlVariables = callOptions.json.variables;
        expect(gqlVariables.userId).toBe(mockUserId);
        expect(gqlVariables.accessToken).toEqual(await encryptToken(mockTokenData.access_token));
        expect(gqlVariables.refreshToken).toEqual(await encryptToken(mockTokenData.refresh_token!));
        expect(gqlVariables.appEmail).toBe(mockAppEmail);
        expect(gqlVariables.resourceName).toBe(constants.ATOM_CALENDAR_RESOURCE_NAME);
        expect(gqlVariables.clientType).toBe(constants.ATOM_CLIENT_TYPE);

        const gqlQuery = callOptions.json.query;
        expect(gqlQuery).toContain('mutation upsertAtomGoogleCalendarToken');
        expect(gqlQuery).toContain('insert_Calendar_Integration_one');
        expect(gqlQuery).toContain('on_conflict');
        expect(gqlQuery).toContain('Calendar_Integration_userId_resource_clientType_key');
        expect(gqlQuery).toContain('$appEmail: String');
        expect(gqlQuery).toContain('appEmail: $appEmail');
        expect(gqlQuery).toContain('update_columns: [token, refreshToken, expiresAt, scope, token_type, appEmail, enabled, updatedAt]');

        expect(result).toEqual({ id: 'mock-db-id', userId: mockUserId });
      });

      it('should throw error if Hasura returns errors', async () => {
        setMockEncryptionConstants(validTestKey, validTestIv);
        got.post.mockResolvedValue({
          json: jest.fn().mockResolvedValue({ errors: [{ message: "Constraint violation" }] }),
        } as any);

        await expect(saveAtomGoogleCalendarTokens(mockUserId, mockTokenData, mockAppEmail))
          .rejects.toThrow('Failed to save tokens: Constraint violation');
        expect(consoleErrorSpy).toHaveBeenCalledWith("Error saving Atom Google Calendar tokens to Hasura:", [{ message: "Constraint violation" }]);
      });

      it('should throw error if got.post rejects (network/http error)', async () => {
        setMockEncryptionConstants(validTestKey, validTestIv);
        got.post.mockRejectedValue(new Error("Network failure"));
        await expect(saveAtomGoogleCalendarTokens(mockUserId, mockTokenData, mockAppEmail))
          .rejects.toThrow('An exception occurred while saving tokens: Network failure');
      });

      it('should throw error if Hasura URL or Secret is missing', async () => {
        setMockEncryptionConstants(validTestKey, validTestIv);
        setMockHasuraConstants(null, 'secret');
        await expect(saveAtomGoogleCalendarTokens(mockUserId, mockTokenData, mockAppEmail))
          .rejects.toThrow('Server configuration error for saving tokens.');
        expect(consoleErrorSpy).toHaveBeenCalledWith('Hasura URL or Admin Secret not configured. Cannot save tokens.');

        setMockHasuraConstants('url', null);
        await expect(saveAtomGoogleCalendarTokens(mockUserId, mockTokenData, mockAppEmail))
          .rejects.toThrow('Server configuration error for saving tokens.');
      });
    });

    describe('getAtomGoogleCalendarTokens', () => {
      const encryptedAccessToken = `encrypted_${mockTokenData.access_token}`; // Placeholder for actual encryption
      const encryptedRefreshToken = `encrypted_${mockTokenData.refresh_token!}`;
      const mockExpiry = new Date(mockTokenData.expiry_date);

      it('should successfully fetch and decrypt tokens from Hasura', async () => {
        setMockEncryptionConstants(validTestKey, validTestIv); // Ensure decryption works
        got.post.mockResolvedValue({
          json: jest.fn().mockResolvedValue({
            data: {
              Calendar_Integration: [{
                id: 'mock-id',
                token: await encryptToken(mockTokenData.access_token), // Use actual encrypt
                refreshToken: await encryptToken(mockTokenData.refresh_token!),
                expiresAt: mockExpiry.toISOString(),
                scope: mockTokenData.scope,
                token_type: mockTokenData.token_type,
                appEmail: mockAppEmail,
              }],
            },
          }),
        } as any);

        const result = await getAtomGoogleCalendarTokens(mockUserId);

        expect(got.post).toHaveBeenCalledTimes(1);
        const callOptions = got.post.mock.calls[0][1] as any;
        expect(callOptions.json.variables.userId).toBe(mockUserId);
        expect(callOptions.json.variables.resourceName).toBe(constants.ATOM_CALENDAR_RESOURCE_NAME);
        expect(callOptions.json.variables.clientType).toBe(constants.ATOM_CLIENT_TYPE);
        expect(callOptions.json.query).toContain('query getAtomGoogleCalendarTokens');

        expect(result).toEqual({
          ...mockTokenData,
          appEmail: mockAppEmail,
        });
      });

      it('should return null if no tokens are found in Hasura', async () => {
        setMockEncryptionConstants(validTestKey, validTestIv);
        got.post.mockResolvedValue({
          json: jest.fn().mockResolvedValue({ data: { Calendar_Integration: [] } }),
        } as any);
        const result = await getAtomGoogleCalendarTokens(mockUserId);
        expect(result).toBeNull();
      });

      it('should return null if Hasura returns errors', async () => {
        setMockEncryptionConstants(validTestKey, validTestIv);
        got.post.mockResolvedValue({
          json: jest.fn().mockResolvedValue({ errors: [{ message: "DB error" }] }),
        } as any);
        const result = await getAtomGoogleCalendarTokens(mockUserId);
        expect(result).toBeNull();
        expect(consoleErrorSpy).toHaveBeenCalledWith("Error fetching Atom Google Calendar tokens from Hasura:", [{ message: "DB error" }]);
      });

      it('should return null if got.post rejects', async () => {
        setMockEncryptionConstants(validTestKey, validTestIv);
        got.post.mockRejectedValue(new Error("Network failure"));
        const result = await getAtomGoogleCalendarTokens(mockUserId);
        expect(result).toBeNull();
      });

      it('should return null if decryption of accessToken fails', async () => {
        setMockEncryptionConstants(validTestKey, validTestIv);
        got.post.mockResolvedValue({
            json: async () => ({ data: { Calendar_Integration: [{ token: 'actually_not_encrypted_properly', refreshToken: encryptedRefreshToken }] } })
        } as any);

        const result = await getAtomGoogleCalendarTokens('user1');
        expect(result).toBeNull();
        expect(consoleErrorSpy).toHaveBeenCalledWith("Error during token decryption:", expect.any(Error)); // From decryptToken itself
        expect(consoleErrorSpy).toHaveBeenCalledWith("Failed to decrypt access token for userId: user1. Returning null.");
    });

    it('should return tokens with undefined refreshToken if only refreshToken decryption fails', async () => {
        setMockEncryptionConstants(validTestKey, validTestIv);
        got.post.mockResolvedValue({
            json: async () => ({
                data: {
                    Calendar_Integration: [{
                        token: await encryptToken(mockTokenData.access_token),
                        refreshToken: 'bad_encrypted_refresh_token',
                        expiresAt: mockExpiry.toISOString(),
                        scope: mockTokenData.scope,
                        token_type: mockTokenData.token_type,
                        appEmail: mockAppEmail
                    }]
                }
            })
        } as any);

        const result = await getAtomGoogleCalendarTokens('user1');
        expect(result).not.toBeNull();
        expect(result?.access_token).toBe(mockTokenData.access_token);
        expect(result?.refresh_token).toBeUndefined();
        expect(consoleErrorSpy).toHaveBeenCalledWith("Error during token decryption:", expect.any(Error)); // From decryptToken
        expect(consoleErrorSpy).toHaveBeenCalledWith("Failed to decrypt refresh token for userId: user1. Proceeding without it.");
    });

    });

    describe('deleteAtomGoogleCalendarTokens', () => {
      it('should successfully delete tokens from Hasura', async () => {
        got.post.mockResolvedValue({
          json: jest.fn().mockResolvedValue({
            data: { delete_Calendar_Integration: { affected_rows: 1 } },
          }),
        } as any);

        const result = await deleteAtomGoogleCalendarTokens(mockUserId);
        expect(got.post).toHaveBeenCalledTimes(1);
        const callOptions = got.post.mock.calls[0][1] as any;
        expect(callOptions.json.variables.userId).toBe(mockUserId);
        expect(callOptions.json.variables.resourceName).toBe(constants.ATOM_CALENDAR_RESOURCE_NAME);
        expect(callOptions.json.variables.clientType).toBe(constants.ATOM_CLIENT_TYPE);
        expect(callOptions.json.query).toContain('mutation deleteAtomGoogleCalendarToken');
        expect(result).toEqual({ affected_rows: 1 });
      });

      it('should return affected_rows: 0 if no tokens were deleted', async () => {
        got.post.mockResolvedValue({
          json: jest.fn().mockResolvedValue({
            data: { delete_Calendar_Integration: { affected_rows: 0 } },
          }),
        } as any);
        const result = await deleteAtomGoogleCalendarTokens(mockUserId);
        expect(result).toEqual({ affected_rows: 0 });
      });

      it('should throw error if Hasura returns errors on delete', async () => {
        got.post.mockResolvedValue({
          json: jest.fn().mockResolvedValue({ errors: [{ message: "Delete failed" }] }),
        } as any);
        await expect(deleteAtomGoogleCalendarTokens(mockUserId))
          .rejects.toThrow('Failed to delete tokens: Delete failed');
      });
    });

  // --- Tests for Atom Gmail Token Utilities ---
  describe('Token Utilities - Gmail Hasura Interactions', () => {
    const mockUserId = 'test-gmail-user-id';
    const mockAppEmail = 'user.gmail@example.com';
    const mockTokenData = { // Slightly different token data for distinction if needed
      access_token: 'test_gmail_access_token',
      refresh_token: 'test_gmail_refresh_token',
      expiry_date: Date.now() + 7200000, // 2 hours from now
      scope: 'gmail_test_scope',
      token_type: 'Bearer',
    };

    // beforeEach, afterEach for consoleErrorSpy and Hasura/Encryption constants are inherited from parent describe block
    // Or can be re-declared if specific overrides are needed for this block only

    describe('saveAtomGmailTokens', () => {
      it('should successfully save/upsert Gmail tokens to Hasura', async () => {
        setMockEncryptionConstants(validTestKey, validTestIv);
        got.post.mockResolvedValue({
          json: jest.fn().mockResolvedValue({
            data: { insert_Calendar_Integration_one: { id: 'mock-gmail-db-id', userId: mockUserId } },
          }),
        } as any);

        const result = await require('./token-utils').saveAtomGmailTokens(mockUserId, mockTokenData, mockAppEmail);

        expect(got.post).toHaveBeenCalledTimes(1);
        const callOptions = got.post.mock.calls[0][1] as any;
        const gqlVariables = callOptions.json.variables;

        expect(gqlVariables.resourceName).toBe(constants.ATOM_GMAIL_RESOURCE_NAME); // Check Gmail resource name
        expect(gqlVariables.clientType).toBe(constants.ATOM_CLIENT_TYPE);
        expect(gqlVariables.userId).toBe(mockUserId);
        expect(gqlVariables.accessToken).toEqual(await encryptToken(mockTokenData.access_token));
        expect(gqlVariables.appEmail).toBe(mockAppEmail);

        const gqlQuery = callOptions.json.query;
        expect(gqlQuery).toContain('mutation upsertAtomGmailToken');
        expect(gqlQuery).toContain(constants.ATOM_GMAIL_RESOURCE_NAME); // Ensure resource name is in query if it's dynamic, or check var

        expect(result).toEqual({ id: 'mock-gmail-db-id', userId: mockUserId });
      });

      it('should throw error if Hasura returns errors for Gmail save', async () => {
          setMockEncryptionConstants(validTestKey, validTestIv);
          got.post.mockResolvedValue({
            json: jest.fn().mockResolvedValue({ errors: [{ message: "Gmail save constraint violation" }] }),
          } as any);

          await expect(require('./token-utils').saveAtomGmailTokens(mockUserId, mockTokenData, mockAppEmail))
            .rejects.toThrow('Failed to save Gmail tokens: Gmail save constraint violation');
        });
    });

    describe('getAtomGmailTokens', () => {
      it('should successfully fetch and decrypt Gmail tokens from Hasura', async () => {
        setMockEncryptionConstants(validTestKey, validTestIv);
        const encryptedAccessToken = await encryptToken(mockTokenData.access_token);
        const encryptedRefreshToken = await encryptToken(mockTokenData.refresh_token!);
        const mockExpiry = new Date(mockTokenData.expiry_date);

        got.post.mockResolvedValue({
          json: jest.fn().mockResolvedValue({
            data: {
              Calendar_Integration: [{
                id: 'mock-id',
                token: encryptedAccessToken,
                refreshToken: encryptedRefreshToken,
                expiresAt: mockExpiry.toISOString(),
                scope: mockTokenData.scope,
                token_type: mockTokenData.token_type,
                appEmail: mockAppEmail,
              }],
            },
          }),
        } as any);

        const result = await require('./token-utils').getAtomGmailTokens(mockUserId);

        expect(got.post).toHaveBeenCalledTimes(1);
        const callOptions = got.post.mock.calls[0][1] as any;
        expect(callOptions.json.variables.resourceName).toBe(constants.ATOM_GMAIL_RESOURCE_NAME);
        expect(callOptions.json.query).toContain('query getAtomGmailTokens');

        expect(result).toEqual({
          ...mockTokenData,
          appEmail: mockAppEmail,
        });
      });

      it('should return null if no Gmail tokens are found', async () => {
          setMockEncryptionConstants(validTestKey, validTestIv);
          got.post.mockResolvedValue({
            json: jest.fn().mockResolvedValue({ data: { Calendar_Integration: [] } }),
          } as any);
          const result = await require('./token-utils').getAtomGmailTokens(mockUserId);
          expect(result).toBeNull();
        });
    });

    describe('deleteAtomGmailTokens', () => {
      it('should successfully delete Gmail tokens from Hasura', async () => {
        got.post.mockResolvedValue({
          json: jest.fn().mockResolvedValue({
            data: { delete_Calendar_Integration: { affected_rows: 1 } },
          }),
        } as any);

        const result = await require('./token-utils').deleteAtomGmailTokens(mockUserId);
        expect(got.post).toHaveBeenCalledTimes(1);
        const callOptions = got.post.mock.calls[0][1] as any;
        expect(callOptions.json.variables.resourceName).toBe(constants.ATOM_GMAIL_RESOURCE_NAME);
        expect(callOptions.json.query).toContain('mutation deleteAtomGmailToken');
        expect(result).toEqual({ affected_rows: 1 });
      });

      it('should throw error if Hasura returns errors on Gmail delete', async () => {
          got.post.mockResolvedValue({
            json: jest.fn().mockResolvedValue({ errors: [{ message: "Gmail delete failed" }] }),
          } as any);
          await expect(require('./token-utils').deleteAtomGmailTokens(mockUserId))
            .rejects.toThrow('Failed to delete Gmail tokens: Gmail delete failed');
        });
    });
  });
  });

  // --- Tests for Atom Microsoft Graph Token Utilities ---
  describe('Token Utilities - Microsoft Graph Hasura Interactions', () => {
    const mockUserId = 'test-msgraph-user-id';
    const mockAppEmail = 'user.ms@example.com';
    const mockTokenData = {
      access_token: 'test_ms_access_token',
      refresh_token: 'test_ms_refresh_token',
      expiry_date: Date.now() + 3600000,
      scope: 'ms_test_scope',
      token_type: 'Bearer',
    };

    // beforeEach and afterEach for consoleErrorSpy and Hasura/Encryption constants are inherited from parent describe block.
    // Specific overrides for constants (like resource_name) will be handled by using the MSGraph specific constants.

    describe('saveAtomMicrosoftGraphTokens', () => {
      it('should successfully save/upsert MS Graph tokens to Hasura', async () => {
        setMockEncryptionConstants(validTestKey, validTestIv);
        got.post.mockResolvedValue({
          json: jest.fn().mockResolvedValue({
            data: { insert_Calendar_Integration_one: { id: 'mock-ms-db-id', userId: mockUserId } },
          }),
        } as any);

        const result = await require('./token-utils').saveAtomMicrosoftGraphTokens(mockUserId, mockTokenData, mockAppEmail);

        expect(got.post).toHaveBeenCalledTimes(1);
        const callOptions = got.post.mock.calls[0][1] as any;
        const gqlVariables = callOptions.json.variables;

        expect(gqlVariables.resourceName).toBe(constants.ATOM_MSGRAPH_RESOURCE_NAME); // Check MS Graph resource name
        expect(gqlVariables.clientType).toBe(constants.ATOM_CLIENT_TYPE);
        expect(gqlVariables.userId).toBe(mockUserId);
        expect(gqlVariables.accessToken).toEqual(await encryptToken(mockTokenData.access_token));
        expect(gqlVariables.appEmail).toBe(mockAppEmail);

        const gqlQuery = callOptions.json.query;
        expect(gqlQuery).toContain('mutation upsertAtomMicrosoftGraphToken');
        expect(gqlQuery).toContain(constants.ATOM_MSGRAPH_RESOURCE_NAME);

        expect(result).toEqual({ id: 'mock-ms-db-id', userId: mockUserId });
      });

      it('should throw error if Hasura returns errors for MS Graph save', async () => {
          setMockEncryptionConstants(validTestKey, validTestIv);
          got.post.mockResolvedValue({
            json: jest.fn().mockResolvedValue({ errors: [{ message: "MS Graph save constraint violation" }] }),
          } as any);

          await expect(require('./token-utils').saveAtomMicrosoftGraphTokens(mockUserId, mockTokenData, mockAppEmail))
            .rejects.toThrow('Failed to save Microsoft Graph tokens: MS Graph save constraint violation');
        });
    });

    describe('getAtomMicrosoftGraphTokens', () => {
      it('should successfully fetch and decrypt MS Graph tokens from Hasura', async () => {
        setMockEncryptionConstants(validTestKey, validTestIv);
        const encryptedAccessToken = await encryptToken(mockTokenData.access_token);
        const encryptedRefreshToken = await encryptToken(mockTokenData.refresh_token!);
        const mockExpiry = new Date(mockTokenData.expiry_date);

        got.post.mockResolvedValue({
          json: jest.fn().mockResolvedValue({
            data: {
              Calendar_Integration: [{
                id: 'mock-id',
                token: encryptedAccessToken,
                refreshToken: encryptedRefreshToken,
                expiresAt: mockExpiry.toISOString(),
                scope: mockTokenData.scope,
                token_type: mockTokenData.token_type,
                appEmail: mockAppEmail,
              }],
            },
          }),
        } as any);

        const result = await require('./token-utils').getAtomMicrosoftGraphTokens(mockUserId);

        expect(got.post).toHaveBeenCalledTimes(1);
        const callOptions = got.post.mock.calls[0][1] as any;
        expect(callOptions.json.variables.resourceName).toBe(constants.ATOM_MSGRAPH_RESOURCE_NAME);
        expect(callOptions.json.query).toContain('query getAtomMicrosoftGraphTokens');

        expect(result).toEqual({
          ...mockTokenData,
          appEmail: mockAppEmail,
        });
      });

      it('should return null if no MS Graph tokens are found', async () => {
          setMockEncryptionConstants(validTestKey, validTestIv);
          got.post.mockResolvedValue({
            json: jest.fn().mockResolvedValue({ data: { Calendar_Integration: [] } }),
          } as any);
          const result = await require('./token-utils').getAtomMicrosoftGraphTokens(mockUserId);
          expect(result).toBeNull();
        });
    });

    describe('deleteAtomMicrosoftGraphTokens', () => {
      it('should successfully delete MS Graph tokens from Hasura', async () => {
        got.post.mockResolvedValue({
          json: jest.fn().mockResolvedValue({
            data: { delete_Calendar_Integration: { affected_rows: 1 } },
          }),
        } as any);

        const result = await require('./token-utils').deleteAtomMicrosoftGraphTokens(mockUserId);
        expect(got.post).toHaveBeenCalledTimes(1);
        const callOptions = got.post.mock.calls[0][1] as any;
        expect(callOptions.json.variables.resourceName).toBe(constants.ATOM_MSGRAPH_RESOURCE_NAME);
        expect(callOptions.json.query).toContain('mutation deleteAtomMicrosoftGraphToken');
        expect(result).toEqual({ affected_rows: 1 });
      });

      it('should throw error if Hasura returns errors on MS Graph delete', async () => {
          got.post.mockResolvedValue({
            json: jest.fn().mockResolvedValue({ errors: [{ message: "MS Graph delete failed" }] }),
          } as any);
          await expect(require('./token-utils').deleteAtomMicrosoftGraphTokens(mockUserId))
            .rejects.toThrow('Failed to delete Microsoft Graph tokens: MS Graph delete failed');
        });
    });
  });
});
