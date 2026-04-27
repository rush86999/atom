/**
 * Crypto Utility Tests
 *
 * Test suite for AES-256-CBC encryption/decryption utilities
 */

import { encrypt, decrypt } from '../crypto';

describe('crypto', () => {
  describe('encrypt', () => {
    it('should encrypt a plain text string', () => {
      const plaintext = 'Hello, World!';
      const encrypted = encrypt(plaintext);

      expect(encrypted).toBeDefined();
      expect(encrypted).not.toBe(plaintext);
      expect(encrypted.length).toBeGreaterThan(0);
    });

    it('should produce different ciphertext for same plaintext', () => {
      const plaintext = 'Hello, World!';
      const encrypted1 = encrypt(plaintext);
      const encrypted2 = encrypt(plaintext);

      // Random IV should produce different ciphertext
      expect(encrypted1).not.toBe(encrypted2);
    });

    it('should include IV in the encrypted output', () => {
      const plaintext = 'Test message';
      const encrypted = encrypt(plaintext);

      // Format: IV:encrypted_text
      expect(encrypted).toContain(':');
      const parts = encrypted.split(':');
      expect(parts.length).toBe(2);
      expect(parts[0].length).toBe(32); // 16 bytes IV = 32 hex chars
    });

    it('should handle empty strings', () => {
      const plaintext = '';
      const encrypted = encrypt(plaintext);

      expect(encrypted).toBeDefined();
      expect(encrypted).toContain(':');
    });

    it('should handle special characters', () => {
      const plaintext = 'Special chars: !@#$%^&*()_+-=[]{}|;:,.<>?';
      const encrypted = encrypt(plaintext);

      expect(encrypted).toBeDefined();
      expect(encrypted).toContain(':');
    });

    it('should handle unicode characters', () => {
      const plaintext = 'Unicode: 你好 🌍 مرحبا';
      const encrypted = encrypt(plaintext);

      expect(encrypted).toBeDefined();
      expect(encrypted).toContain(':');
    });

    it('should handle long strings', () => {
      const plaintext = 'A'.repeat(10000);
      const encrypted = encrypt(plaintext);

      expect(encrypted).toBeDefined();
      expect(encrypted).toContain(':');
    });

    it('should handle numbers converted to strings', () => {
      const plaintext = '123456789';
      const encrypted = encrypt(plaintext);

      expect(encrypted).toBeDefined();
      expect(encrypted).toContain(':');
    });

    it('should produce valid hex format', () => {
      const plaintext = 'Test';
      const encrypted = encrypt(plaintext);
      const parts = encrypted.split(':');
      const iv = parts[0];
      const ciphertext = parts[1];

      // Should be valid hex (only 0-9, a-f)
      const hexRegex = /^[0-9a-f]+$/;
      expect(iv).toMatch(hexRegex);
      expect(ciphertext).toMatch(hexRegex);
    });
  });

  describe('decrypt', () => {
    it('should decrypt an encrypted string', () => {
      const plaintext = 'Hello, World!';
      const encrypted = encrypt(plaintext);
      const decrypted = decrypt(encrypted);

      expect(decrypted).toBe(plaintext);
    });

    it('should decrypt unicode characters correctly', () => {
      const plaintext = 'Unicode: 你好 🌍 مرحبا';
      const encrypted = encrypt(plaintext);
      const decrypted = decrypt(encrypted);

      expect(decrypted).toBe(plaintext);
    });

    it('should decrypt special characters correctly', () => {
      const plaintext = 'Special chars: !@#$%^&*()_+-=[]{}|;:,.<>?';
      const encrypted = encrypt(plaintext);
      const decrypted = decrypt(encrypted);

      expect(decrypted).toBe(plaintext);
    });

    it('should decrypt empty strings correctly', () => {
      const plaintext = '';
      const encrypted = encrypt(plaintext);
      const decrypted = decrypt(encrypted);

      expect(decrypted).toBe(plaintext);
    });

    it('should decrypt long strings correctly', () => {
      const plaintext = 'A'.repeat(10000);
      const encrypted = encrypt(plaintext);
      const decrypted = decrypt(encrypted);

      expect(decrypted).toBe(plaintext);
    });

    it('should throw error for invalid format (missing colon)', () => {
      const invalidEncrypted = 'invalid-format-no-colon';

      expect(() => {
        decrypt(invalidEncrypted);
      }).toThrow();
    });

    it('should throw error for invalid format (missing IV)', () => {
      const invalidEncrypted = ':encrypted-text';

      expect(() => {
        decrypt(invalidEncrypted);
      }).toThrow('Invalid encrypted text format');
    });

    it('should throw error for invalid hex characters', () => {
      const invalidEncrypted = 'invalid-hex!:text';

      expect(() => {
        decrypt(invalidEncrypted);
      }).toThrow();
    });

    it('should throw error for corrupted ciphertext', () => {
      const plaintext = 'Test';
      const encrypted = encrypt(plaintext);
      const corrupted = encrypted.replace(/a/g, 'z');

      expect(() => {
        decrypt(corrupted);
      }).toThrow();
    });

    it('should throw error for truncated ciphertext', () => {
      const plaintext = 'Test';
      const encrypted = encrypt(plaintext);
      const truncated = encrypted.split(':')[0] + ':' + 'abc';

      expect(() => {
        decrypt(truncated);
      }).toThrow();
    });
  });

  describe('encrypt/decrypt round-trip', () => {
    it('should maintain data integrity through multiple encryption cycles', () => {
      const plaintext = 'Original message';

      const encrypted1 = encrypt(plaintext);
      const decrypted1 = decrypt(encrypted1);

      const encrypted2 = encrypt(decrypted1);
      const decrypted2 = decrypt(encrypted2);

      expect(decrypted2).toBe(plaintext);
    });

    it('should produce different ciphertext each time but decrypt to same value', () => {
      const plaintext = 'Consistent message';

      const encrypted1 = encrypt(plaintext);
      const encrypted2 = encrypt(plaintext);
      const encrypted3 = encrypt(plaintext);

      expect(encrypted1).not.toBe(encrypted2);
      expect(encrypted2).not.toBe(encrypted3);
      expect(encrypted1).not.toBe(encrypted3);

      expect(decrypt(encrypted1)).toBe(plaintext);
      expect(decrypt(encrypted2)).toBe(plaintext);
      expect(decrypt(encrypted3)).toBe(plaintext);
    });

    it('should handle multiple different messages independently', () => {
      const messages = ['Message 1', 'Message 2', 'Message 3'];

      const encrypted = messages.map(m => encrypt(m));
      const decrypted = encrypted.map(c => decrypt(c));

      expect(decrypted).toEqual(messages);
    });
  });

  describe('edge cases', () => {
    it('should handle very long messages', () => {
      const plaintext = 'A'.repeat(1000000); // 1MB

      const encrypted = encrypt(plaintext);
      const decrypted = decrypt(encrypted);

      expect(decrypted).toBe(plaintext);
    });

    it('should handle messages with newlines', () => {
      const plaintext = 'Line 1\nLine 2\nLine 3';

      const encrypted = encrypt(plaintext);
      const decrypted = decrypt(encrypted);

      expect(decrypted).toBe(plaintext);
    });

    it('should handle messages with tabs', () => {
      const plaintext = 'Column1\tColumn2\tColumn3';

      const encrypted = encrypt(plaintext);
      const decrypted = decrypt(encrypted);

      expect(decrypted).toBe(plaintext);
    });

    it('should handle JSON strings', () => {
      const plaintext = JSON.stringify({ key: 'value', nested: { array: [1, 2, 3] } });

      const encrypted = encrypt(plaintext);
      const decrypted = decrypt(encrypted);

      expect(decrypted).toBe(plaintext);
      expect(JSON.parse(decrypted)).toEqual(JSON.parse(plaintext));
    });
  });
});
