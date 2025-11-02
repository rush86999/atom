/**
 * ATOM Encryption Service
 * BYOK (Bring Your Own Key) compatible
 * AES-256-GCM encryption for Box files
 * Cross-platform: Next.js & Tauri
 */

class EncryptionService {
  constructor() {
    this.initialized = false;
    this.algorithm = 'AES-GCM';
    this.keyLength = 256;
    this.ivLength = 12;
  }

  async initialize() {
    if (this.initialized) return true;

    try {
      // Initialize Web Crypto API (Browser) or Node.js Crypto (Desktop)
      if (typeof window !== 'undefined' && window.crypto) {
        this.crypto = window.crypto.subtle;
      } else {
        // Node.js environment (Tauri)
        this.crypto = await import('crypto').then(crypto => crypto.webcrypto.subtle);
      }

      this.initialized = true;
      return true;
    } catch (error) {
      console.error('Encryption service initialization failed:', error);
      return false;
    }
  }

  // Generate encryption key
  async generateKey() {
    if (!this.initialized) {
      throw new Error('Encryption service not initialized');
    }

    return await this.crypto.generateKey(
      {
        name: this.algorithm,
        length: this.keyLength
      },
      true,
      ['encrypt', 'decrypt']
    );
  }

  // Encrypt data
  async encryptData(data, key) {
    if (!this.initialized) {
      throw new Error('Encryption service not initialized');
    }

    try {
      // Generate random IV
      const iv = crypto.getRandomValues(new Uint8Array(this.ivLength));

      // Convert data to bytes
      const encoder = new TextEncoder();
      const dataBytes = encoder.encode(JSON.stringify(data));

      // Encrypt
      const encryptedData = await this.crypto.encrypt(
        {
          name: this.algorithm,
          iv: iv
        },
        key,
        dataBytes
      );

      // Return encrypted data with IV
      return {
        encryptedData: Array.from(new Uint8Array(encryptedData)),
        iv: Array.from(iv),
        algorithm: this.algorithm
      };
    } catch (error) {
      console.error('Encryption failed:', error);
      throw error;
    }
  }

  // Decrypt data
  async decryptData(encryptedPayload, key) {
    if (!this.initialized) {
      throw new Error('Encryption service not initialized');
    }

    try {
      const { encryptedData, iv, algorithm } = encryptedPayload;

      // Convert to Uint8Array
      const encryptedBytes = new Uint8Array(encryptedData);
      const ivBytes = new Uint8Array(iv);

      // Decrypt
      const decryptedData = await this.crypto.decrypt(
        {
          name: algorithm,
          iv: ivBytes
        },
        key,
        encryptedBytes
      );

      // Convert back to string and parse JSON
      const decoder = new TextDecoder();
      const decryptedString = decoder.decode(decryptedData);
      
      return JSON.parse(decryptedString);
    } catch (error) {
      console.error('Decryption failed:', error);
      throw error;
    }
  }

  // Encrypt file (for large files)
  async encryptFile(file, key) {
    if (!this.initialized) {
      throw new Error('Encryption service not initialized');
    }

    try {
      const iv = crypto.getRandomValues(new Uint8Array(this.ivLength));
      const chunkSize = 64 * 1024; // 64KB chunks
      const encryptedChunks = [];

      // Read and encrypt file in chunks
      for (let offset = 0; offset < file.size; offset += chunkSize) {
        const chunk = file.slice(offset, Math.min(offset + chunkSize, file.size));
        const chunkArray = await chunk.arrayBuffer();
        
        const encryptedChunk = await this.crypto.encrypt(
          {
            name: this.algorithm,
            iv: iv // Use same IV for all chunks (alternative: chunk-specific IVs)
          },
          key,
          new Uint8Array(chunkArray)
        );

        encryptedChunks.push(Array.from(new Uint8Array(encryptedChunk)));
      }

      return {
        encryptedChunks,
        iv: Array.from(iv),
        algorithm: this.algorithm,
        originalSize: file.size,
        originalName: file.name,
        encryptedSize: encryptedChunks.reduce((sum, chunk) => sum + chunk.length, 0)
      };
    } catch (error) {
      console.error('File encryption failed:', error);
      throw error;
    }
  }

  // Decrypt file (for large files)
  async decryptFile(encryptedFileData, key) {
    if (!this.initialized) {
      throw new Error('Encryption service not initialized');
    }

    try {
      const { encryptedChunks, iv, algorithm, originalSize, originalName } = encryptedFileData;
      const ivBytes = new Uint8Array(iv);

      // Decrypt chunks
      const decryptedChunks = [];
      for (const encryptedChunk of encryptedChunks) {
        const chunkBytes = new Uint8Array(encryptedChunk);
        
        const decryptedChunk = await this.crypto.decrypt(
          {
            name: algorithm,
            iv: ivBytes
          },
          key,
          chunkBytes
        );

        decryptedChunks.push(new Uint8Array(decryptedChunk));
      }

      // Combine chunks
      const totalDecryptedSize = decryptedChunks.reduce((sum, chunk) => sum + chunk.length, 0);
      const decryptedData = new Uint8Array(totalDecryptedSize);
      let offset = 0;
      
      for (const chunk of decryptedChunks) {
        decryptedData.set(chunk, offset);
        offset += chunk.length;
      }

      // Create Blob and return
      const blob = new Blob([decryptedData], { type: 'application/octet-stream' });
      return new File([blob], originalName, {
        size: originalSize,
        lastModified: Date.now()
      });
    } catch (error) {
      console.error('File decryption failed:', error);
      throw error;
    }
  }

  // Derive key from password (PBKDF2)
  async deriveKeyFromPassword(password, salt) {
    if (!this.initialized) {
      throw new Error('Encryption service not initialized');
    }

    const encoder = new TextEncoder();
    const keyMaterial = await this.crypto.importKey(
      'raw',
      encoder.encode(password),
      'PBKDF2',
      false,
      ['deriveKey']
    );

    return await this.crypto.deriveKey(
      {
        name: 'PBKDF2',
        salt: salt,
        iterations: 100000,
        hash: 'SHA-256'
      },
      keyMaterial,
      { name: this.algorithm, length: this.keyLength },
      true,
      ['encrypt', 'decrypt']
    );
  }

  // Generate random salt
  generateSalt() {
    return Array.from(crypto.getRandomValues(new Uint8Array(16)));
  }

  // Import key from base64
  async importKey(base64Key) {
    if (!this.initialized) {
      throw new Error('Encryption service not initialized');
    }

    try {
      const keyBytes = Uint8Array.from(atob(base64Key), c => c.charCodeAt(0));
      return await this.crypto.importKey(
        'raw',
        keyBytes,
        { name: this.algorithm, length: this.keyLength },
        true,
        ['encrypt', 'decrypt']
      );
    } catch (error) {
      console.error('Key import failed:', error);
      throw error;
    }
  }

  // Export key to base64
  async exportKey(key) {
    if (!this.initialized) {
      throw new Error('Encryption service not initialized');
    }

    try {
      const keyBytes = await this.crypto.exportKey('raw', key);
      return btoa(String.fromCharCode(...new Uint8Array(keyBytes)));
    } catch (error) {
      console.error('Key export failed:', error);
      throw error;
    }
  }

  // Encrypt and store file metadata
  encryptFileMetadata(metadata, key) {
    const encryptionInfo = {
      version: '1.0',
      algorithm: this.algorithm,
      ivLength: this.ivLength,
      timestamp: new Date().toISOString()
    };

    return this.encryptData({ metadata, encryptionInfo }, key);
  }

  // Decrypt file metadata
  async decryptFileMetadata(encryptedMetadata, key) {
    const decrypted = await this.decryptData(encryptedMetadata, key);
    return {
      metadata: decrypted.metadata,
      encryptionInfo: decrypted.encryptionInfo
    };
  }
}

// Create singleton instance
const encryptionService = new EncryptionService();

export default encryptionService;