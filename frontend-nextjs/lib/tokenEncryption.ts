/**
 * OAuth Token Encryption Service
 *
 * Provides AES-256-GCM encryption for OAuth tokens stored in the database.
 * This ensures that sensitive access tokens and refresh tokens are encrypted at rest.
 *
 * Security Features:
 * - AES-256-GCM encryption (authenticated encryption)
 * - Random IV for each encryption (prevents pattern analysis)
 * - AuthTag for integrity verification (detects tampering)
 * - Key derivation from environment variable
 *
 * Usage:
 *   import { TokenEncryptionService } from '@lib/tokenEncryption';
 *
 *   const encryption = new TokenEncryptionService();
 *   const encrypted = encryption.encrypt(plaintextToken);
 *   const decrypted = encryption.decrypt(encrypted);
 */

import crypto from 'crypto';

export class TokenEncryptionService {
  private key: Buffer;
  private algorithm = 'aes-256-gcm';
  private ivLength = 16; // AES block size
  private authTagLength = 16; // GCM auth tag length
  private keyLength = 32; // 256 bits for AES-256

  constructor() {
    const keyString = process.env.TOKEN_ENCRYPTION_KEY;

    if (!keyString) {
      throw new Error(
        'TOKEN_ENCRYPTION_KEY environment variable is not set. ' +
        'Please generate a secure 64-character hex string: ' +
        'node -e "console.log(crypto.randomBytes(32).toString(\'hex\'))"'
      );
    }

    // Validate key is 64 hex characters (256 bits)
    if (!/^[a-f0-9]{64}$/i.test(keyString)) {
      throw new Error(
        'TOKEN_ENCRYPTION_KEY must be exactly 64 hexadecimal characters (256 bits). ' +
        `Current length: ${keyString.length} characters. ` +
        'Generate with: node -e "console.log(crypto.randomBytes(32).toString(\'hex\'))"'
      );
    }

    this.key = Buffer.from(keyString, 'hex');
  }

  /**
   * Encrypt plaintext token string.
   *
   * Format: IV (16 bytes) + AuthTag (16 bytes) + EncryptedData (variable)
   *
   * @param plaintext - The plaintext token to encrypt
   * @returns Hex-encoded encrypted string (IV + AuthTag + EncryptedData)
   *
   * @example
   * const encrypted = encryption.encrypt('my-access-token');
   * // Returns: '1a2b3c4d...[32 chars IV][32 chars AuthTag][encrypted data]'
   */
  encrypt(plaintext: string): string {
    try {
      // Generate random IV for each encryption (prevents pattern analysis)
      const iv = crypto.randomBytes(this.ivLength);

      // Create cipher with AES-256-GCM
      const cipher = crypto.createCipheriv(this.algorithm, this.key, iv);

      // Encrypt the plaintext
      let encrypted = cipher.update(plaintext, 'utf8', 'hex');
      encrypted += cipher.final('hex');

      // Get authentication tag (for integrity verification)
      const authTag = cipher.getAuthTag();

      // Combine: IV + AuthTag + EncryptedData (all as hex)
      const result = iv.toString('hex') + authTag.toString('hex') + encrypted;

      return result;
    } catch (error) {
      console.error('[TokenEncryption] Encryption failed:', error);
      throw new Error(`Token encryption failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  /**
   * Decrypt encrypted token string.
   *
   * @param ciphertext - Hex-encoded encrypted string (IV + AuthTag + EncryptedData)
   * @returns Decrypted plaintext token
   * @throws Error if decryption fails or integrity check fails
   *
   * @example
   * const decrypted = encryption.decrypt('1a2b3c4d...');
   * // Returns: 'my-access-token'
   */
  decrypt(ciphertext: string): string {
    try {
      // Validate ciphertext length
      const minimumLength = (this.ivLength + this.authTagLength) * 2; // hex encoding doubles length
      if (ciphertext.length < minimumLength) {
        throw new Error(
          `Invalid ciphertext length (must be at least ${minimumLength} hex characters)`
        );
      }

      // Extract IV (first 32 hex chars = 16 bytes)
      const ivHex = ciphertext.slice(0, this.ivLength * 2);
      const iv = Buffer.from(ivHex, 'hex');

      // Extract AuthTag (next 32 hex chars = 16 bytes)
      const authTagHex = ciphertext.slice(this.ivLength * 2, (this.ivLength + this.authTagLength) * 2);
      const authTag = Buffer.from(authTagHex, 'hex');

      // Extract encrypted data (remaining bytes)
      const encrypted = ciphertext.slice((this.ivLength + this.authTagLength) * 2);

      // Create decipher with AES-256-GCM
      const decipher = crypto.createDecipheriv(this.algorithm, this.key, iv);

      // Set authentication tag (integrity verification)
      decipher.setAuthTag(authTag);

      // Decrypt the data
      let decrypted = decipher.update(encrypted, 'hex', 'utf8');
      decrypted += decipher.final('utf8');

      return decrypted;
    } catch (error) {
      console.error('[TokenEncryption] Decryption failed:', error);
      throw new Error(
        `Token decryption failed: ${error instanceof Error ? error.message : 'Unknown error'}. ` +
        'This may indicate the token was tampered with or the encryption key has changed.'
      );
    }
  }

  /**
   * Check if a token is encrypted (heuristically).
   *
   * This is a simple heuristic: if the token is long enough and looks like hex,
   * it's probably encrypted. This is NOT cryptographically secure - it's just
   * for migration purposes to detect already-encrypted tokens.
   *
   * @param token - Token string to check
   * @returns True if token appears to be encrypted
   */
  isEncrypted(token: string): boolean {
    // Check if token is long enough (IV + AuthTag + some data)
    const minimumEncryptedLength = (this.ivLength + this.authTagLength) * 2; // hex encoding
    if (token.length < minimumEncryptedLength) {
      return false;
    }

    // Check if token is valid hexadecimal
    return /^[a-f0-9]+$/i.test(token);
  }

  /**
   * Re-encrypt a token with a new key (for key rotation).
   *
   * @param currentCiphertext - Current encrypted token
   * @param newEncryptionKey - New 64-character hex encryption key
   * @returns Re-encrypted token with new key
   */
  reencrypt(currentCiphertext: string, newEncryptionKey: string): string {
    // Decrypt with current key
    const plaintext = this.decrypt(currentCiphertext);

    // Create new encryption service with new key
    const newEncryption = new TokenEncryptionService();
    // Temporarily override the key
    (newEncryption as any).key = Buffer.from(newEncryptionKey, 'hex');

    // Re-encrypt with new key
    return newEncryption.encrypt(plaintext);
  }
}

/**
 * Singleton instance for use throughout the application.
 * Reuse this instance rather than creating new ones.
 */
let encryptionServiceInstance: TokenEncryptionService | null = null;

/**
 * Get the singleton TokenEncryptionService instance.
 *
 * @returns TokenEncryptionService instance
 *
 * @example
 * import { getEncryptionService } from '@lib/tokenEncryption';
 *
 * const encryption = getEncryptionService();
 * const encrypted = encryption.encrypt('my-token');
 */
export function getEncryptionService(): TokenEncryptionService {
  if (!encryptionServiceInstance) {
    encryptionServiceInstance = new TokenEncryptionService();
  }
  return encryptionServiceInstance;
}

/**
 * Convenience function to encrypt a token.
 *
 * @param plaintext - Token to encrypt
 * @returns Encrypted token (hex string)
 */
export function encryptToken(plaintext: string): string {
  return getEncryptionService().encrypt(plaintext);
}

/**
 * Convenience function to decrypt a token.
 *
 * @param ciphertext - Encrypted token (hex string)
 * @returns Decrypted plaintext token
 */
export function decryptToken(ciphertext: string): string {
  return getEncryptionService().decrypt(ciphertext);
}

export default TokenEncryptionService;
