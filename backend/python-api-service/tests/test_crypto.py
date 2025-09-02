import os
import unittest
from python_api_service.crypto import encrypt, decrypt

class TestCrypto(unittest.TestCase):

    def setUp(self):
        self.encryption_key = os.urandom(32).hex()
        self.plain_text = "This is a secret message."

    def test_encrypt_decrypt(self):
        encrypted_text = encrypt(self.plain_text, self.encryption_key)
        decrypted_text = decrypt(encrypted_text, self.encryption_key)
        self.assertEqual(self.plain_text, decrypted_text)

if __name__ == '__main__':
    unittest.main()
