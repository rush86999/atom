import os
import base64
import logging
from typing import Optional, Type, Any

# --- Mock Implementations for Local Testing ---
# These classes are defined upfront to be used as fallbacks if the 'cryptography'
# library is not installed.

class MockInvalidToken(Exception):
    """A mock exception to simulate cryptography.fernet.InvalidToken."""
    pass

class MockFernet:
    """A mock class to simulate the behavior of cryptography.fernet.Fernet."""
    def __init__(self, key: bytes):
        if not isinstance(key, bytes) or len(base64.urlsafe_b64decode(key)) != 32:
            raise ValueError("MockFernet key must be 32 url-safe base64-encoded bytes.")
        self.key = key

    def encrypt(self, data: bytes) -> bytes:
        """Simulates encryption by base64 encoding the data with a prefix."""
        encoded = base64.urlsafe_b64encode(data)
        return b"mock_encrypted_" + encoded

    def decrypt(self, token: bytes) -> bytes:
        """Simulates decryption by removing the prefix and base64 decoding."""
        prefix = b"mock_encrypted_"
        if not token.startswith(prefix):
            raise MockInvalidToken("Invalid mock token format")
        try:
            import binascii
            return base64.urlsafe_b64decode(token[len(prefix):])
        except (binascii.Error, ValueError):
            raise MockInvalidToken("Invalid base64 in mock token")

    @staticmethod
    def generate_key() -> bytes:
        """Generates a URL-safe base64-encoded 32-byte key."""
        return base64.urlsafe_b64encode(os.urandom(32))


# --- Dynamic Import of Cryptography Library ---
# We assign the real or mock classes to a consistent name for use throughout the module.
# This allows the application to function with or without the library installed.

try:
    from cryptography.fernet import Fernet, InvalidToken
    logging.info("Successfully imported 'cryptography' library.")
    FernetCipher: Type = Fernet
    InvalidTokenException: Type = InvalidToken
except ImportError:
    logging.warning("'cryptography' library not found. Using mock implementation.")
    FernetCipher = MockFernet
    InvalidTokenException = MockInvalidToken


# --- Global Variables & Initialization ---

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# The encryption key is loaded from the environment.
# It MUST be a URL-safe base64-encoded 32-byte key.
RAW_ENCRYPTION_KEY_STR: Optional[str] = os.environ.get("ATOM_OAUTH_ENCRYPTION_KEY")
_fernet_cipher_suite: Optional[Any] = None


def _initialize_cipher_suite() -> bool:
    """
    Initializes the Fernet cipher suite from the environment variable.
    Returns True on success, False on failure.
    """
    global _fernet_cipher_suite
    if _fernet_cipher_suite:
        return True

    if not RAW_ENCRYPTION_KEY_STR:
        logger.critical("ATOM_OAUTH_ENCRYPTION_KEY is not set. Encryption will be disabled.")
        return False

    try:
        key_bytes = RAW_ENCRYPTION_KEY_STR.encode('utf-8')
        # This check is required by the real Fernet library.
        if len(base64.urlsafe_b64decode(key_bytes)) != 32:
            logger.critical("Invalid ATOM_OAUTH_ENCRYPTION_KEY: key must be 32 bytes long after base64 decoding.")
            return False

        _fernet_cipher_suite = FernetCipher(key_bytes)
        logger.info("Fernet cipher suite initialized successfully.")
        return True
    except Exception as e:
        logger.critical(f"Failed to initialize Fernet cipher suite: {e}", exc_info=True)
        _fernet_cipher_suite = None
        return False

CRYPTO_INITIALIZED_SUCCESSFULLY = _initialize_cipher_suite()


# --- Public API ---

def encrypt_data(data_str: str) -> Optional[str]:
    """Encrypts a string using the initialized Fernet cipher suite."""
    if not CRYPTO_INITIALIZED_SUCCESSFULLY or not _fernet_cipher_suite:
        logger.error("Encryption failed: Cipher suite not initialized.")
        return None
    if not isinstance(data_str, str):
        logger.error("Encryption failed: Input must be a string.")
        return None

    try:
        encrypted_bytes = _fernet_cipher_suite.encrypt(data_str.encode('utf-8'))
        return encrypted_bytes.decode('utf-8')
    except Exception as e:
        logger.error(f"Error during data encryption: {e}", exc_info=True)
        return None

def decrypt_data(encrypted_str: str) -> Optional[str]:
    """Decrypts a string using the initialized Fernet cipher suite."""
    if not CRYPTO_INITIALIZED_SUCCESSFULLY or not _fernet_cipher_suite:
        logger.error("Decryption failed: Cipher suite not initialized.")
        return None
    if not isinstance(encrypted_str, str):
        logger.error("Decryption failed: Input must be a string.")
        return None

    try:
        decrypted_bytes = _fernet_cipher_suite.decrypt(encrypted_str.encode('utf-8'))
        return decrypted_bytes.decode('utf-8')
    except InvalidTokenException:
        logger.error("Decryption failed: Invalid token. Key may be wrong or data may be corrupted.")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred during decryption: {e}", exc_info=True)
        return None

def generate_fernet_key() -> str:
    """Generates a new URL-safe base64-encoded 32-byte Fernet key."""
    key = FernetCipher.generate_key()
    return key.decode('utf-8')


# --- Key Generation and Test Utility ---

if __name__ == '__main__':
    print("--- Fernet Key Generation and Test Utility ---")
    print("\n1. Generate a New Key")
    print("Run this script to generate a new key for the ATOM_OAUTH_ENCRYPTION_KEY environment variable.")
    new_key = generate_fernet_key()
    print(f"\n  Generated Key: {new_key}\n")
    print("Set this key as an environment variable in your production and development environments.")

    print("\n2. Test Encryption/Decryption")
    if CRYPTO_INITIALIZED_SUCCESSFULLY:
        print("--- Testing with provided ATOM_OAUTH_ENCRYPTION_KEY ---")
        original_text = "This is a secret message!"
        print(f"Original:    '{original_text}'")

        encrypted = encrypt_data(original_text)
        if encrypted:
            print(f"Encrypted:   '{encrypted}'")
            decrypted = decrypt_data(encrypted)
            if decrypted:
                print(f"Decrypted:   '{decrypted}'")
                assert original_text == decrypted, "FAILURE: Decrypted text does not match original!"
                print("\nSUCCESS: Round-trip encryption/decryption test passed.")
            else:
                print("\nFAILURE: Decryption returned None.")
        else:
            print("\nFAILURE: Encryption returned None.")
    elif not RAW_ENCRYPTION_KEY_STR:
        print("--- Test SKIPPED: ATOM_OAUTH_ENCRYPTION_KEY environment variable not set. ---")
    else:
        print("--- Test SKIPPED: Cipher suite failed to initialize. See logs above. ---")
