/**
 * Tests for TokenEncryptionService
 *
 * Tests AES-256-GCM encryption/decryption functionality for OAuth tokens.
 */

import { TokenEncryptionService, getEncryptionService, encryptToken, decryptToken } from '@lib/src/tokenEncryption';

describe('TokenEncryptionService', () => {
  let validKey: string;
  let encryptionService: TokenEncryptionService;

  beforeAll(() => {
    // Generate a valid 64-character hex key for testing
    validKey = '0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef';
    process.env.TOKEN_ENCRYPTION_KEY = validKey;
    encryptionService = new TokenEncryptionService();
  });

  afterEach(() => {
    // Reset environment variable
    process.env.TOKEN_ENCRYPTION_KEY = validKey;
  });

  describe('Constructor', () => {
    it('should create instance with valid key', () => {
      expect(encryptionService).toBeInstanceOf(TokenEncryptionService);
    });

    it('should throw error if TOKEN_ENCRYPTION_KEY not set', () => {
      delete process.env.TOKEN_ENCRYPTION_KEY;
      expect(() => new TokenEncryptionService()).toThrow(
        'TOKEN_ENCRYPTION_KEY environment variable is not set'
      );
    });

    it('should throw error if key is not 64 hex characters', () => {
      process.env.TOKEN_ENCRYPTION_KEY = 'invalid-key';
      expect(() => new TokenEncryptionService()).toThrow(
        'TOKEN_ENCRYPTION_KEY must be exactly 64 hexadecimal characters'
      );
    });

    it('should throw error if key contains non-hex characters', () => {
      process.env.TOKEN_ENCRYPTION_KEY = 'g'.repeat(64);
      expect(() => new TokenEncryptionService()).toThrow(
        'TOKEN_ENCRYPTION_KEY must be exactly 64 hexadecimal characters'
      );
    });
  });

  describe('encrypt', () => {
    it('should encrypt plaintext token', () => {
      const plaintext = 'my-access-token-12345';
      const encrypted = encryptionService.encrypt(plaintext);

      expect(encrypted).toBeDefined();
      expect(typeof encrypted).toBe('string');
      expect(encrypted).not.toBe(plaintext);
      expect(encrypted.length).toBeGreaterThan(plaintext.length);
    });

    it('should produce different ciphertext for same plaintext (random IV)', () => {
      const plaintext = 'same-token';
      const encrypted1 = encryptionService.encrypt(plaintext);
      const encrypted2 = encryptionService.encrypt(plaintext);

      expect(encrypted1).not.toBe(encrypted2);
    });

    it('should encrypt empty string', () => {
      const encrypted = encryptionService.encrypt('');
      expect(encrypted).toBeDefined();
      expect(encrypted.length).toBeGreaterThan(0);
    });

    it('should encrypt tokens with special characters', () => {
      const specialToken = 'token-with-special-chars-!@#$%^&*()';
      const encrypted = encryptionService.encrypt(specialToken);
      expect(encrypted).toBeDefined();
    });

    it('should encrypt long tokens', () => {
      const longToken = 'a'.repeat(10000);
      const encrypted = encryptionService.encrypt(longToken);
      expect(encrypted).toBeDefined();
    });

    it('should return hex-encoded string', () => {
      const encrypted = encryptionService.encrypt('test-token');
      expect(/^[a-f0-9]+$/i.test(encrypted)).toBe(true);
    });

    it('should throw error on encryption failure', () => {
      // Force an error by using an invalid service instance
      const badService = new TokenEncryptionService();
      (badService as any).key = null;

      expect(() => badService.encrypt('test')).toThrow();
    });
  });

  describe('decrypt', () => {
    it('should decrypt previously encrypted token', () => {
      const plaintext = 'my-access-token';
      const encrypted = encryptionService.encrypt(plaintext);
      const decrypted = encryptionService.decrypt(encrypted);

      expect(decrypted).toBe(plaintext);
    });

    it('should decrypt empty string', () => {
      const encrypted = encryptionService.encrypt('');
      const decrypted = encryptionService.decrypt(encrypted);
      expect(decrypted).toBe('');
    });

    it('should decrypt tokens with special characters', () => {
      const specialToken = 'token-with-special-chars-!@#$%^&*()';
      const encrypted = encryptionService.encrypt(specialToken);
      const decrypted = encryptionService.decrypt(encrypted);
      expect(decrypted).toBe(specialToken);
    });

    it('should decrypt long tokens', () => {
      const longToken = 'a'.repeat(10000);
      const encrypted = encryptionService.encrypt(longToken);
      const decrypted = encryptionService.decrypt(encrypted);
      expect(decrypted).toBe(longToken);
    });

    it('should throw error for invalid ciphertext length', () => {
      expect(() => encryptionService.decrypt('too-short')).toThrow(
        'Invalid ciphertext length'
      );
    });

    it('should throw error for non-hex ciphertext', () => {
      const invalidHex = 'x'.repeat(100);
      expect(() => encryptionService.decrypt(invalidHex)).toThrow();
    });

    it('should throw error for tampered ciphertext (wrong auth tag)', () => {
      const plaintext = 'test-token';
      const encrypted = encryptionService.encrypt(plaintext);
      // Tamper with the ciphertext
      const tampered = encrypted.slice(0, -10) + '0000000000';

      expect(() => encryptionService.decrypt(tampered)).toThrow();
    });
  });

  describe('isEncrypted', () => {
    it('should return true for encrypted token', () => {
      const plaintext = 'my-token';
      const encrypted = encryptionService.encrypt(plaintext);
      expect(encryptionService.isEncrypted(encrypted)).toBe(true);
    });

    it('should return false for short token', () => {
      expect(encryptionService.isEncrypted('short')).toBe(false);
    });

    it('should return false for non-hex token', () => {
      expect(encryptionService.isEncrypted('not-hex-chars-!@#$%')).toBe(false);
    });

    it('should return true for long hex string (heuristic)', () => {
      const longHex = 'a'.repeat(100);
      expect(encryptionService.isEncrypted(longHex)).toBe(true);
    });

    it('should return false for mixed hex and non-hex', () => {
      const mixed = 'abcdef12345ghij';
      expect(encryptionService.isEncrypted(mixed)).toBe(false);
    });
  });

  describe('reencrypt', () => {
    it('should re-encrypt with new key', () => {
      const plaintext = 'my-token';
      const currentEncrypted = encryptionService.encrypt(plaintext);

      const newKey = 'fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210';
      const reencrypted = encryptionService.reencrypt(currentEncrypted, newKey);

      expect(reencrypted).toBeDefined();
      expect(reencrypted).not.toBe(currentEncrypted);

      // Verify can decrypt with new key
      const newService = new TokenEncryptionService();
      (newService as any).key = Buffer.from(newKey, 'hex');
      const decrypted = newService.decrypt(reencrypted);
      expect(decrypted).toBe(plaintext);
    });

    it('should throw error for invalid current ciphertext', () => {
      const newKey = 'fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210';
      expect(() => encryptionService.reencrypt('invalid', newKey)).toThrow();
    });

    it('should throw error for invalid new key', () => {
      const plaintext = 'my-token';
      const currentEncrypted = encryptionService.encrypt(plaintext);

      expect(() => encryptionService.reencrypt(currentEncrypted, 'invalid-key')).toThrow();
    });
  });

  describe('getEncryptionService', () => {
    it('should return singleton instance', () => {
      const instance1 = getEncryptionService();
      const instance2 = getEncryptionService();

      expect(instance1).toBe(instance2);
    });

    it('should return TokenEncryptionService instance', () => {
      const instance = getEncryptionService();
      expect(instance).toBeInstanceOf(TokenEncryptionService);
    });
  });

  describe('encryptToken', () => {
    it('should encrypt token using singleton service', () => {
      const plaintext = 'test-token';
      const encrypted = encryptToken(plaintext);

      expect(encrypted).toBeDefined();
      expect(encrypted).not.toBe(plaintext);

      // Verify can decrypt
      const decrypted = decryptToken(encrypted);
      expect(decrypted).toBe(plaintext);
    });
  });

  describe('decryptToken', () => {
    it('should decrypt token using singleton service', () => {
      const plaintext = 'test-token';
      const encrypted = encryptToken(plaintext);
      const decrypted = decryptToken(encrypted);

      expect(decrypted).toBe(plaintext);
    });
  });

  describe('encryption format', () => {
    it('should produce IV (32 chars) + AuthTag (32 chars) + ciphertext', () => {
      const plaintext = 'test-token';
      const encrypted = encryptionService.encrypt(plaintext);

      // IV = 16 bytes = 32 hex chars
      // AuthTag = 16 bytes = 32 hex chars
      // Total minimum = 64 hex chars
      expect(encrypted.length).toBeGreaterThanOrEqual(64);
    });

    it('should produce unique IV for each encryption', () => {
      const plaintext = 'same-token';
      const encrypted1 = encryptionService.encrypt(plaintext);
      const encrypted2 = encryptionService.encrypt(plaintext);

      // First 32 chars are IV
      const iv1 = encrypted1.slice(0, 32);
      const iv2 = encrypted2.slice(0, 32);

      expect(iv1).not.toBe(iv2);
    });
  });

  describe('edge cases', () => {
    it('should handle unicode characters', () => {
      const unicodeToken = 'token-with-unicode-😀-🎉-🚀';
      const encrypted = encryptionService.encrypt(unicodeToken);
      const decrypted = encryptionService.decrypt(encrypted);
      expect(decrypted).toBe(unicodeToken);
    });

    it('should handle tokens with newlines', () => {
      const multilineToken = 'token\nwith\nnewlines';
      const encrypted = encryptionService.encrypt(multilineToken);
      const decrypted = encryptionService.decrypt(encrypted);
      expect(decrypted).toBe(multilineToken);
    });

    it('should handle very long tokens (10KB)', () => {
      const longToken = 'x'.repeat(10000);
      const encrypted = encryptionService.encrypt(longToken);
      const decrypted = encryptionService.decrypt(encrypted);
      expect(decrypted).toBe(longToken);
    });
  });
});
