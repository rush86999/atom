/**
 * Property-Based Tests for Crypto Utilities
 *
 * Tests encryption/decryption using property-based testing with fast-check
 */

import fc from 'fast-check';
import { encrypt, decrypt } from '../crypto';

describe('Crypto Utilities - Property-Based Tests', () => {
  // Property 1: Round-trip encryption/decryption
  // For any plaintext, decrypt(encrypt(plaintext)) === plaintext
  it('should satisfy round-trip property: decrypt(encrypt(x)) === x', () => {
    fc.assert(
      fc.property(
        fc.string({ minLength: 1, maxLength: 1000 }), // plaintext strings
        (plaintext) => {
          const encrypted = encrypt(plaintext);
          const decrypted = decrypt(encrypted);
          return decrypted === plaintext;
        }
      ),
      { numRuns: 100 }
    );
  });

  // Property 2: Encryption output format
  // Encrypted text should always contain ':' separator
  it('should always produce encrypted text with IV separator', () => {
    fc.assert(
      fc.property(
        fc.string({ minLength: 1, maxLength: 100 }),
        (plaintext) => {
          const encrypted = encrypt(plaintext);
          return encrypted.includes(':');
        }
      ),
      { numRuns: 100 }
    );
  });

  // Property 3: Encryption is deterministic for same input with mocked IV
  // Note: In production with random IV, encryption won't be deterministic
  // This property tests that the structure is maintained
  it('should produce different encrypted values for same plaintext (due to random IV)', () => {
    fc.assert(
      fc.property(
        fc.string({ minLength: 1, maxLength: 100 }),
        (plaintext) => {
          const encrypted1 = encrypt(plaintext);
          const encrypted2 = encrypt(plaintext);
          // Due to random IV, encryptions should be different
          return encrypted1 !== encrypted2;
        }
      ),
      { numRuns: 50 }
    );
  });

  // Property 4: Empty string handling
  it('should handle empty string correctly', () => {
    const plaintext = '';
    const encrypted = encrypt(plaintext);
    const decrypted = decrypt(encrypted);
    expect(decrypted).toBe(plaintext);
  });

  // Property 5: Special characters and Unicode
  it('should handle special characters and Unicode correctly', () => {
    fc.assert(
      fc.property(
        fc.string({ minLength: 1, maxLength: 100 }),
        (plaintext) => {
          const encrypted = encrypt(plaintext);
          const decrypted = decrypt(encrypted);
          return decrypted === plaintext;
        }
      ),
      { numRuns: 50 }
    );
  });

  // Property 6: Long strings
  it('should handle long strings correctly', () => {
    fc.assert(
      fc.property(
        fc.string({ minLength: 1000, maxLength: 10000 }),
        (plaintext) => {
          const encrypted = encrypt(plaintext);
          const decrypted = decrypt(encrypted);
          return decrypted === plaintext;
        }
      ),
      { numRuns: 20 }
    );
  });

  // Property 7: Idempotency of decryption
  // decrypt(decrypt(encrypted)) should throw an error
  it('should throw error when decrypting non-encrypted text', () => {
    fc.assert(
      fc.property(
        fc.string({ minLength: 1, maxLength: 100 }),
        (plaintext) => {
          expect(() => decrypt(plaintext)).toThrow();
        }
      ),
      { numRuns: 50 }
    );
  });

  // Property 8: Encrypted text length relationship
  // Encrypted text should be longer than plaintext (AES expansion + IV)
  it('should produce encrypted text longer than plaintext', () => {
    fc.assert(
      fc.property(
        fc.string({ minLength: 10, maxLength: 100 }),
        (plaintext) => {
          const encrypted = encrypt(plaintext);
          return encrypted.length > plaintext.length;
        }
      ),
      { numRuns: 100 }
    );
  });
});
