import os
import base64
import logging
from typing import Optional # Added Optional for type hinting
from cryptography.fernet import Fernet, InvalidToken
# from cryptography.hazmat.primitives import hashes # Not used in current simple key setup
# from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC # Not used

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# --- Encryption Key Management ---
# ATOM_OAUTH_ENCRYPTION_KEY: Environment variable storing the Fernet key.
# This key MUST be a URL-safe base64-encoded 32-byte key.
# Use generate_fernet_key() from this module to create a suitable key.
RAW_ENCRYPTION_KEY_STR = os.environ.get("ATOM_OAUTH_ENCRYPTION_KEY")

_fernet_cipher_suite: Optional[Fernet] = None

def _initialize_cipher_suite() -> bool:
    """
    Initializes the Fernet cipher suite from the ATOM_OAUTH_ENCRYPTION_KEY environment variable.
    Returns True on success, False on failure.
    """
    global _fernet_cipher_suite
    if _fernet_cipher_suite is not None:
        return True # Already initialized

    if not RAW_ENCRYPTION_KEY_STR:
        logger.critical("ATOM_OAUTH_ENCRYPTION_KEY environment variable is not set. OAuth token encryption/decryption will be disabled.")
        return False

    try:
        key_bytes_for_fernet_constructor = RAW_ENCRYPTION_KEY_STR.encode('utf-8')

        # Validate that the key_bytes_for_fernet_constructor, when decoded from base64, results in 32 raw bytes.
        # This ensures the key provided in the environment is a valid Fernet key.
        decoded_key_for_validation = base64.urlsafe_b64decode(key_bytes_for_fernet_constructor)
        if len(decoded_key_for_validation) != 32:
            logger.critical(
                f"ATOM_OAUTH_ENCRYPTION_KEY, after base64 decoding, is not 32 bytes long (it's {len(decoded_key_for_validation)} bytes). "
                "It must be a URL-safe base64 encoded 32-byte key. Use generate_fernet_key() to create one."
            )
            return False

        _fernet_cipher_suite = Fernet(key_bytes_for_fernet_constructor)
        logger.info("Fernet cipher suite initialized successfully for OAuth token encryption.")
        return True
    except Exception as e:
        logger.critical(f"Failed to initialize Fernet cipher suite from ATOM_OAUTH_ENCRYPTION_KEY: {e}", exc_info=True)
        _fernet_cipher_suite = None # Ensure it's None on failure
        return False

# Global flag indicating if crypto is usable
CRYPTO_INITIALIZED_SUCCESSFULLY = _initialize_cipher_suite()

if not CRYPTO_INITIALIZED_SUCCESSFULLY:
    logger.warning("OAuth token encryption/decryption will NOT be available due to key initialization failure.")

def encrypt_data(data_str: str) -> Optional[str]:
    """Encrypts a string using Fernet symmetric encryption."""
    if not CRYPTO_INITIALIZED_SUCCESSFULLY or _fernet_cipher_suite is None:
        logger.error("Encryption failed: Cipher suite not initialized. ATOM_OAUTH_ENCRYPTION_KEY might be missing or invalid.")
        return None
    if not isinstance(data_str, str):
        logger.error("Encryption failed: Input data must be a string.")
        return None # Or raise TypeError
    try:
        encrypted_bytes = _fernet_cipher_suite.encrypt(data_str.encode('utf-8'))
        return encrypted_bytes.decode('utf-8')
    except Exception as e:
        logger.error(f"Error during data encryption: {e}", exc_info=True)
        return None

def decrypt_data(encrypted_str: str) -> Optional[str]:
    """Decrypts a Fernet-encrypted string."""
    if not CRYPTO_INITIALIZED_SUCCESSFULLY or _fernet_cipher_suite is None:
        logger.error("Decryption failed: Cipher suite not initialized. ATOM_OAUTH_ENCRYPTION_KEY might be missing or invalid.")
        return None
    if not isinstance(encrypted_str, str):
        logger.error("Decryption failed: Input encrypted_data must be a string.")
        return None # Or raise TypeError
    try:
        decrypted_bytes = _fernet_cipher_suite.decrypt(encrypted_str.encode('utf-8'))
        return decrypted_bytes.decode('utf-8')
    except InvalidToken:
        logger.error("Decryption failed: Invalid token. This could be due to incorrect key, corrupted data, or data not encrypted with this Fernet instance.")
        return None
    except Exception as e:
        logger.error(f"Error during data decryption: {e}", exc_info=True)
        return None

# --- Key Generation Utility (for developers to generate a new key) ---
def generate_fernet_key() -> str:
    """Generates a new Fernet key (URL-safe base64-encoded 32 random bytes)."""
    key = Fernet.generate_key()
    return key.decode('utf-8')

if __name__ == '__main__':
    print("--- Fernet Key Generation Utility & Test ---")

    # First, show how to generate a key
    print("\nTo generate a new key for ATOM_OAUTH_ENCRYPTION_KEY, run this script and copy the output below.")
    new_key_example = generate_fernet_key()
    print(f"Example Generated Fernet Key:\n{new_key_example}\n")
    print("Set this key as the ATOM_OAUTH_ENCRYPTION_KEY environment variable for the application.")
    print("Ensure it's kept secret and secure.\n")

    # Test encryption/decryption if key is set in environment for this run
    if RAW_ENCRYPTION_KEY_STR:
        print(f"--- Testing with ATOM_OAUTH_ENCRYPTION_KEY: '{RAW_ENCRYPTION_KEY_STR[:10]}...' ---")
        if CRYPTO_INITIALIZED_SUCCESSFULLY:
            original_text = "my_very_secret_oauth_token_data_!@#$%^&*()_+"
            print(f"Original:    '{original_text}'")

            encrypted = encrypt_data(original_text)
            if encrypted:
                print(f"Encrypted:   '{encrypted}'")
                decrypted = decrypt_data(encrypted)
                if decrypted:
                    print(f"Decrypted:   '{decrypted}'")
                    if original_text == decrypted:
                        print("SUCCESS: Encryption and decryption roundtrip successful.")
                    else:
                        print("FAILURE: Decrypted text does not match original text!")
                else:
                    print("FAILURE: Decryption test failed: Could not decrypt the encrypted text.")
            else:
                print("FAILURE: Encryption test failed: Could not encrypt the original text.")
        else:
            print("SKIPPED: Encryption/decryption test skipped due to cipher suite initialization failure (check logs above).")
    else:
        print("SKIPPED: Encryption/decryption test skipped as ATOM_OAUTH_ENCRYPTION_KEY is not set in the current environment.")

```
