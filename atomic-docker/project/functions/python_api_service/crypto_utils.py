import os
import base64
import logging
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# --- Encryption Key Management ---
# Load a master encryption key from environment variable.
# For Fernet, this key MUST be 32 bytes and URL-safe base64 encoded.
# It's critical this key is kept secret and managed securely.
# In a real production system, this might come from a secrets manager.
RAW_ENCRYPTION_KEY_STR = os.environ.get("ATOM_OAUTH_ENCRYPTION_KEY")

_fernet_cipher_suite: Optional[Fernet] = None

def _initialize_cipher_suite():
    """Initializes the Fernet cipher suite from the environment key."""
    global _fernet_cipher_suite
    if _fernet_cipher_suite is not None:
        return True

    if not RAW_ENCRYPTION_KEY_STR:
        logger.critical("ATOM_OAUTH_ENCRYPTION_KEY environment variable is not set. Cannot perform encryption/decryption.")
        # In a real app, this might raise an exception to prevent startup or insecure operation.
        return False

    try:
        # Ensure the key is 32 bytes. If it's a passphrase, derive a key.
        # For simplicity here, we'll assume RAW_ENCRYPTION_KEY_STR IS the base64 encoded 32-byte key.
        # If it's a passphrase, key derivation (e.g., PBKDF2) should be used.
        # Example of key derivation if RAW_ENCRYPTION_KEY_STR was a passphrase:
        # salt = os.urandom(16) # Store salt securely or derive from non-sensitive static app data
        # kdf = PBKDF2HMAC(
        #     algorithm=hashes.SHA256(),
        #     length=32,
        #     salt=salt, # Store this salt or make it derivable
        #     iterations=480000, # NIST recommended minimum
        # )
        # derived_key = base64.urlsafe_b64encode(kdf.derive(RAW_ENCRYPTION_KEY_STR.encode()))

        # Assuming RAW_ENCRYPTION_KEY_STR is already a Fernet key:
        key_bytes = RAW_ENCRYPTION_KEY_STR.encode('utf-8')
        # Validate key length for Fernet (must be base64 of 32 random bytes)
        # base64.urlsafe_b64decode will throw error if not valid base64
        decoded_key = base64.urlsafe_b64decode(key_bytes)
        if len(decoded_key) != 32:
            logger.critical(f"ATOM_OAUTH_ENCRYPTION_KEY, after base64 decoding, is not 32 bytes long (is {len(decoded_key)} bytes). It must be a URL-safe base64 encoded 32-byte key.")
            return False

        _fernet_cipher_suite = Fernet(key_bytes)
        logger.info("Fernet cipher suite initialized successfully for OAuth token encryption.")
        return True
    except Exception as e:
        logger.critical(f"Failed to initialize Fernet cipher suite from ATOM_OAUTH_ENCRYPTION_KEY: {e}", exc_info=True)
        return False

# Attempt to initialize on module load
if not _initialize_cipher_suite():
    logger.warning("OAuth token encryption/decryption will not be available due to key initialization failure.")

def encrypt_data(data_str: str) -> Optional[str]:
    """Encrypts a string using Fernet symmetric encryption."""
    if not _fernet_cipher_suite:
        logger.error("Encryption failed: Cipher suite not initialized. ATOM_OAUTH_ENCRYPTION_KEY might be missing or invalid.")
        return None
    if not isinstance(data_str, str):
        logger.error("Encryption failed: Input data must be a string.")
        return None
    try:
        encrypted_bytes = _fernet_cipher_suite.encrypt(data_str.encode('utf-8'))
        return encrypted_bytes.decode('utf-8')
    except Exception as e:
        logger.error(f"Error during data encryption: {e}", exc_info=True)
        return None

def decrypt_data(encrypted_str: str) -> Optional[str]:
    """Decrypts a Fernet-encrypted string."""
    if not _fernet_cipher_suite:
        logger.error("Decryption failed: Cipher suite not initialized. ATOM_OAUTH_ENCRYPTION_KEY might be missing or invalid.")
        return None
    if not isinstance(encrypted_str, str):
        logger.error("Decryption failed: Input encrypted_data must be a string.")
        return None
    try:
        decrypted_bytes = _fernet_cipher_suite.decrypt(encrypted_str.encode('utf-8'))
        return decrypted_bytes.decode('utf-8')
    except InvalidToken:
        logger.error("Decryption failed: Invalid token. This could be due to incorrect key, corrupted data, or data not encrypted with Fernet.")
        return None
    except Exception as e:
        logger.error(f"Error during data decryption: {e}", exc_info=True)
        return None

# --- Key Generation Utility (for generating a new key if needed) ---
def generate_fernet_key() -> str:
    """Generates a new Fernet key (URL-safe base64-encoded 32 random bytes)."""
    key = Fernet.generate_key()
    return key.decode('utf-8')

if __name__ == '__main__':
    # This section is for utility; typically, you'd generate a key once and store it securely.
    # print("--- Fernet Key Generation Utility ---")
    # new_key = generate_fernet_key()
    # print(f"Generated Fernet Key (store this in ATOM_OAUTH_ENCRYPTION_KEY environment variable):\n{new_key}\n")

    # Test encryption/decryption if key is set
    if RAW_ENCRYPTION_KEY_STR and _fernet_cipher_suite:
        print("\n--- Encryption/Decryption Test ---")
        original_text = "my_secret_access_token_data_12345!"
        print(f"Original:    {original_text}")

        encrypted = encrypt_data(original_text)
        if encrypted:
            print(f"Encrypted:   {encrypted}")
            decrypted = decrypt_data(encrypted)
            if decrypted:
                print(f"Decrypted:   {decrypted}")
                assert original_text == decrypted, "Decryption test failed!"
                print("Test successful: Original and decrypted text match.")
            else:
                print("Decryption test failed: Could not decrypt.")
        else:
            print("Encryption test failed: Could not encrypt.")
    elif not RAW_ENCRYPTION_KEY_STR:
        print("\nSkipping encryption/decryption test as ATOM_OAUTH_ENCRYPTION_KEY is not set.")
    else: # _fernet_cipher_suite is None due to init error
        print("\nSkipping encryption/decryption test due to cipher suite initialization failure.")

```
