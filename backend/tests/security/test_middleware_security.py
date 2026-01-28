import sys
import unittest
import os

# Add the project root and backend directory to path
current_file_path = os.path.abspath(__file__)
security_dir = os.path.dirname(current_file_path)
tests_dir = os.path.dirname(security_dir)
backend_dir = os.path.dirname(tests_dir)
project_root = os.path.dirname(backend_dir)

sys.path.insert(0, backend_dir)
sys.path.insert(0, project_root)

class TestMiddlewareSecurity(unittest.TestCase):
    def test_secure_hash_delegation(self):
        """Ensure middleware.security.hash_password now uses the secure core.auth implementation"""
        from middleware.security import hash_password
        
        # This will now use bcrypt if BCRYPT_AVAILABLE is True in core.auth
        # Which we enforced in the previous steps.
        password = "test_password"
        h1 = hash_password(password)
        
        # In the old code, this was a sha256 hex string (64 chars)
        # In the new code, it's a bcrypt hash (usually starting with $2b$)
        self.assertTrue(h1.startswith("$2b$") or h1.startswith("$2a$"))
        
        # Verify it's not SHA256 (SHA256 of "test_password" is 15e697... but checking length is easier)
        self.assertNotEqual(len(h1), 64)

if __name__ == "__main__":
    unittest.main()
