import * as crypto from 'crypto';

const ENCRYPTION_KEY = process.env.ENCRYPTION_KEY || 'default-dev-key-must-be-32-bytes-long!';
const IV_LENGTH = 16; // GCM standard is 12, but 16 is accepted; keeping for back-compat

/**
 * Encrypt text using AES-256-GCM (authenticated encryption).
 *
 * Format: `iv_hex:tag_hex:ciphertext_hex`
 *
 * GCM provides integrity — any tampering with the IV, ciphertext, or auth tag
 * is detected on decrypt and throws (unlike the previous unauthenticated CBC,
 * where flipping an IV bit silently produced wrong plaintext). BUG-031.
 */
export function encrypt(text: string): string {
    const iv = crypto.randomBytes(IV_LENGTH);
    const key = ENCRYPTION_KEY.slice(0, 32).padEnd(32, '0');
    // Buffer from @types/node 17 doesn't satisfy the newer Uint8Array<ArrayBuffer> generic shapes
    const cipher = crypto.createCipheriv('aes-256-gcm', key, iv as unknown as crypto.BinaryLike);
    let encrypted = cipher.update(text, 'utf8', 'hex');
    encrypted += cipher.final('hex');
    const tag = cipher.getAuthTag();
    return iv.toString('hex') + ':' + tag.toString('hex') + ':' + encrypted;
}

/**
 * Decrypt text produced by encrypt(). Throws on tampering (GCM auth-tag
 * verification fails) or malformed input.
 */
export function decrypt(text: string): string {
    const textParts = text.split(':');
    if (textParts.length < 3) throw new Error('Invalid encrypted text format');
    const ivHex = textParts[0];
    const tagHex = textParts[1];
    const encryptedText = textParts.slice(2).join(':');
    if (!ivHex || !tagHex) throw new Error('Invalid encrypted text format');
    const iv = Buffer.from(ivHex, 'hex');
    const tag = Buffer.from(tagHex, 'hex');
    const key = ENCRYPTION_KEY.slice(0, 32).padEnd(32, '0');
    const decipher = crypto.createDecipheriv('aes-256-gcm', key, iv as unknown as crypto.BinaryLike);
    decipher.setAuthTag(tag as unknown as NodeJS.ArrayBufferView);
    let decrypted = decipher.update(encryptedText, 'hex', 'utf8');
    decrypted += decipher.final('utf8');
    return decrypted;
}
