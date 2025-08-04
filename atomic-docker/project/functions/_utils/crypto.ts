import crypto from 'crypto';

const ALGORITHM = 'aes-256-gcm';
const IV_LENGTH = 16;
const AUTH_TAG_LENGTH = 16;

export function encrypt(text: string, encryptionKey: string): string {
  if (!encryptionKey) {
    console.error('Encryption key is not set. Cannot encrypt token.');
    throw new Error('Server configuration error: Encryption key not set.');
  }
  const key = Buffer.from(encryptionKey, 'hex');
  if (key.length !== 32) {
    console.error(
      `Encryption key must be 32 bytes (64 hex characters), current length: ${key.length} bytes.`
    );
    throw new Error(
      'Server configuration error: Invalid encryption key length.'
    );
  }
  const iv = crypto.randomBytes(IV_LENGTH);
  const cipher = crypto.createCipheriv(ALGORITHM, key, iv);
  let encrypted = cipher.update(text, 'utf8', 'hex');
  encrypted += cipher.final('hex');
  const authTag = cipher.getAuthTag();
  return iv.toString('hex') + ':' + authTag.toString('hex') + ':' + encrypted;
}

export function decrypt(text: string, encryptionKey: string): string {
  if (!encryptionKey) {
    console.error('Encryption key is not set. Cannot decrypt token.');
    throw new Error(
      'Server configuration error: Encryption key not set for decryption.'
    );
  }
  const key = Buffer.from(encryptionKey, 'hex');
  if (key.length !== 32) {
    console.error(
      `Encryption key must be 32 bytes (64 hex characters) for decryption. Current length: ${key.length} bytes.`
    );
    throw new Error(
      'Server configuration error: Invalid encryption key length for decryption.'
    );
  }
  const parts = text.split(':');
  if (parts.length !== 3) {
    console.error(
      'Invalid encrypted text format. Expected iv:authTag:encryptedText'
    );
    throw new Error('Decryption error: Invalid encrypted text format.');
  }
  const iv = Buffer.from(parts[0], 'hex');
  const authTag = Buffer.from(parts[1], 'hex');
  const encryptedText = parts[2];

  const decipher = crypto.createDecipheriv(ALGORITHM, key, iv);
  decipher.setAuthTag(authTag);
  let decrypted = decipher.update(encryptedText, 'hex', 'utf8');
  decrypted += decipher.final('utf8');
  return decrypted;
}
