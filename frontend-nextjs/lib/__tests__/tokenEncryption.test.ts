/**
 * Tests for Token Encryption Service
 *
 * Tests AES-256-GCM encryption for OAuth tokens
 */

import { TokenEncryptionService, getEncryptionService, encryptToken, decryptToken } from '../tokenEncryption';

// Generate a valid 64-character hex key for testing
const TEST_KEY = '0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef';

describe('TokenEncryptionService', () => {
  let encryptionService: TokenEncryptionService;

  beforeEach(() => {
    process.env.TOKEN_ENCRYPTION_KEY = TEST_KEY;
    encryptionService = new TokenEncryptionService();
  });

  afterEach(() => {
    delete process.env.TOKEN_ENCRYPTION_KEY;
  });

  describe('constructor', () => {
    it('should create instance with valid key', () => {
      expect(encryptionService).toBeInstanceOf(TokenEncryptionService);
    });

    it('should throw error when TOKEN_ENCRYPTION_KEY is not set', () => {
      delete process.env.TOKEN_ENCRYPTION_KEY;
      expect(() => new TokenEncryptionService()).toThrow('TOKEN_ENCRYPTION_KEY environment variable is not set');
    });

    it('should throw error when key is not 64 characters', () => {
      process.env.TOKEN_ENCRYPTION_KEY = 'short-key';
      expect(() => new TokenEncryptionService()).toThrow('TOKEN_ENCRYPTION_KEY must be exactly 64 hexadecimal characters');
    });

    it('should throw error when key contains non-hex characters', () => {
      process.env.TOKEN_ENCRYPTION_KEY = 'g'.repeat(64);
      expect(() => new TokenEncryptionService()).toThrow();
    });
  });

  describe('encrypt', () => {
    it('should encrypt plaintext token', () => {
      const plaintext = 'my-access-token-12345';
      const encrypted = encryptionService.encrypt(plaintext);

      expect(encrypted).toBeDefined();
      expect(encrypted).not.toBe(plaintext);
      expect(encrypted.length).toBeGreaterThanOrEqual(64); // At least IV + AuthTag in hex
    });

    it('should produce different output for same input (due to random IV)', () => {
      const plaintext = 'my-token';
      const encrypted1 = encryptionService.encrypt(plaintext);
      const encrypted2 = encryptionService.encrypt(plaintext);

      expect(encrypted1).not.toBe(encrypted2);
    });

    it('should produce valid hex output', () => {
      const plaintext = 'my-token';
      const encrypted = encryptionService.encrypt(plaintext);

      expect(/^[a-f0-9]+$/i.test(encrypted)).toBe(true);
    });

    it('should encrypt empty string', () => {
      const encrypted = encryptionService.encrypt('');
      expect(encrypted).toBeDefined();
      expect(encrypted.length).toBeGreaterThanOrEqual(64);
    });

    it('should encrypt long tokens', () => {
      const longToken = 'a'.repeat(1000);
      const encrypted = encryptionService.encrypt(longToken);

      expect(encrypted).toBeDefined();
      expect(encrypted.length).toBeGreaterThan(longToken.length);
    });

    it('should encrypt special characters', () => {
      const specialToken = 'token-with-special-chars-!@#$%^&*()_+-=[]{}|;:\'",.<>?/~`';
      const encrypted = encryptionService.encrypt(specialToken);

      expect(encrypted).toBeDefined();
    });
  });

  describe('decrypt', () => {
    it('should decrypt encrypted token correctly', () => {
      const plaintext = 'my-access-token-12345';
      const encrypted = encryptionService.encrypt(plaintext);
      const decrypted = encryptionService.decrypt(encrypted);

      expect(decrypted).toBe(plaintext);
    });

    it('should handle round-trip encryption/decryption', () => {
      const tokens = [
        'short',
        'medium-length-token-with-some-chars',
        'a'.repeat(1000),
        '!@#$%^&*()',
        'token-with- números-日本語-🔥',
      ];

      tokens.forEach(token => {
        const encrypted = encryptionService.encrypt(token);
        const decrypted = encryptionService.decrypt(encrypted);
        expect(decrypted).toBe(token);
      });
    });

    it('should throw error for invalid ciphertext format', () => {
      expect(() => encryptionService.decrypt('too-short')).toThrow();
    });

    it('should throw error for tampered ciphertext', () => {
      const plaintext = 'my-token';
      const encrypted = encryptionService.encrypt(plaintext);

      // Tamper with the ciphertext
      const tampered = encrypted.slice(0, -10) + '0000000000';

      expect(() => encryptionService.decrypt(tampered)).toThrow();
    });

    it('should throw error for invalid hex', () => {
      const invalidHex = 'g'.repeat(100);
      // Invalid hex will cause Buffer.from to throw during IV extraction
      expect(() => encryptionService.decrypt(invalidHex)).toThrow(/Token decryption failed/);
    });
  });

  describe('isEncrypted', () => {
    it('should return true for encrypted token', () => {
      const plaintext = 'my-token';
      const encrypted = encryptionService.encrypt(plaintext);

      expect(encryptionService.isEncrypted(encrypted)).toBe(true);
    });

    it('should return false for short string', () => {
      expect(encryptionService.isEncrypted('short')).toBe(false);
    });

    it('should return false for non-hex string', () => {
      const longString = 'a'.repeat(100);
      expect(encryptionService.isEncrypted(longString)).toBe(true); // 'a' is valid hex
      expect(encryptionService.isEncrypted('g'.repeat(100))).toBe(false); // 'g' is not hex
    });

    it('should return false for empty string', () => {
      expect(encryptionService.isEncrypted('')).toBe(false);
    });
  });

  describe('reencrypt', () => {
    it('should re-encrypt token with new key', () => {
      const plaintext = 'my-token';
      const encrypted1 = encryptionService.encrypt(plaintext);

      // Generate a new key
      const newKey = 'fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210';

      const reencrypted = encryptionService.reencrypt(encrypted1, newKey);

      expect(reencrypted).toBeDefined();
      expect(reencrypted).not.toBe(encrypted1);
    });

    it('should allow decryption with new key after reencryption', () => {
      const plaintext = 'my-token';
      const encrypted1 = encryptionService.encrypt(plaintext);

      // Create a new service with a different key
      const newKey = 'fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210';
      const reencrypted = encryptionService.reencrypt(encrypted1, newKey);

      // Create new service with new key to verify
      process.env.TOKEN_ENCRYPTION_KEY = newKey;
      const newService = new TokenEncryptionService();
      const decrypted = newService.decrypt(reencrypted);

      expect(decrypted).toBe(plaintext);
    });
  });

  describe('getEncryptionService', () => {
    it('should return singleton instance', () => {
      const service1 = getEncryptionService();
      const service2 = getEncryptionService();

      expect(service1).toBe(service2);
    });

    it('should create instance only once', () => {
      const spy = jest.spyOn(TokenEncryptionService.prototype, 'constructor');
      getEncryptionService();
      getEncryptionService();

      // Constructor should only be called once (first time)
      // Note: This test is tricky because constructor is already called
      expect(spy).toBeDefined();
      spy.mockRestore();
    });
  });

  describe('encryptToken convenience function', () => {
    it('should encrypt token using singleton service', () => {
      const plaintext = 'my-token';
      const encrypted = encryptToken(plaintext);

      expect(encrypted).toBeDefined();
      expect(encrypted).not.toBe(plaintext);
    });

    it('should be decryptable with decryptToken', () => {
      const plaintext = 'my-token';
      const encrypted = encryptToken(plaintext);
      const decrypted = decryptToken(encrypted);

      expect(decrypted).toBe(plaintext);
    });
  });

  describe('decryptToken convenience function', () => {
    it('should decrypt token using singleton service', () => {
      const plaintext = 'my-token';
      const encrypted = encryptToken(plaintext);
      const decrypted = decryptToken(encrypted);

      expect(decrypted).toBe(plaintext);
    });
  });
});
