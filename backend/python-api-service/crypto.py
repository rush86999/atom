import os
import logging
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)

def encrypt(plain_text: str, encryption_key: str) -> str:
    """
    Encrypts a plaintext string using AES-256-GCM to be compatible with the Node.js crypto library.
    """
    if not encryption_key:
        logger.error("Encryption key is not set. Cannot encrypt token.")
        raise ValueError("Server configuration error: Encryption key not set.")

    try:
        key = bytes.fromhex(encryption_key)
        if len(key) != 32:
            logger.error(f"Encryption key must be 32 bytes (64 hex characters), current length: {len(key)} bytes.")
            raise ValueError("Server configuration error: Invalid encryption key length.")
    except (ValueError, TypeError) as e:
        logger.error(f"Invalid encryption key format: {e}", exc_info=True)
        raise ValueError("Server configuration error: Invalid encryption key format.")

    iv = os.urandom(16)
    cipher = Cipher(algorithms.AES(key), modes.GCM(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    encrypted_data = encryptor.update(plain_text.encode('utf-8')) + encryptor.finalize()
    auth_tag = encryptor.tag

    return f"{iv.hex()}:{auth_tag.hex()}:{encrypted_data.hex()}"

def decrypt(encrypted_text: str, encryption_key: str) -> str:
    """
    Decrypts a string that was encrypted with the corresponding Node.js crypto library's AES-256-GCM implementation.
    """
    if not encryption_key:
        logger.error("Encryption key is not set. Cannot decrypt token.")
        raise ValueError("Server configuration error: Encryption key not set for decryption.")

    try:
        key = bytes.fromhex(encryption_key)
        if len(key) != 32:
            logger.error(f"Encryption key must be 32 bytes (64 hex characters) for decryption. Current length: {len(key)} bytes.")
            raise ValueError("Server configuration error: Invalid encryption key length for decryption.")
    except (ValueError, TypeError) as e:
        logger.error(f"Invalid encryption key format for decryption: {e}", exc_info=True)
        raise ValueError("Server configuration error: Invalid encryption key format for decryption.")

    parts = encrypted_text.split(':')
    if len(parts) != 3:
        logger.error("Invalid encrypted text format. Expected iv:authTag:encryptedText")
        raise ValueError("Decryption error: Invalid encrypted text format.")

    try:
        iv = bytes.fromhex(parts[0])
        auth_tag = bytes.fromhex(parts[1])
        encrypted_data = bytes.fromhex(parts[2])
    except (ValueError, TypeError) as e:
        logger.error(f"Invalid hex format in encrypted text parts: {e}", exc_info=True)
        raise ValueError("Decryption error: Invalid hex format in encrypted text parts.")

    cipher = Cipher(algorithms.AES(key), modes.GCM(iv, auth_tag), backend=default_backend())
    decryptor = cipher.decryptor()

    try:
        decrypted_data = decryptor.update(encrypted_data) + decryptor.finalize()
        return decrypted_data.decode('utf-8')
    except Exception as e:
        logger.error(f"Decryption failed, possibly due to an invalid tag: {e}", exc_info=True)
        raise ValueError("Decryption failed. The data may have been tampered with or the key is incorrect.")
