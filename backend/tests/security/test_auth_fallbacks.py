import os
import sys
import unittest

# Add the project root and backend directory to path
current_file_path = os.path.abspath(__file__)
security_dir = os.path.dirname(current_file_path)
tests_dir = os.path.dirname(security_dir)
backend_dir = os.path.dirname(tests_dir)
project_root = os.path.dirname(backend_dir)

print(f"DEBUG: current_file_path: {current_file_path}")
print(f"DEBUG: backend_dir: {backend_dir}")
print(f"DEBUG: project_root: {project_root}")

sys.path.insert(0, backend_dir)
sys.path.insert(0, project_root)

print(f"DEBUG: sys.path[:2]: {sys.path[:2]}")

class TestSecurityFixes(unittest.TestCase):
    def test_bcrypt_hard_import(self):
        """Ensure bcrypt is now a hard import and not optional"""
        try:
            import core.auth as auth
            self.assertTrue(auth.BCRYPT_AVAILABLE)
        except ImportError as e:
            self.fail(f"bcrypt should be a required dependency now: {e}")

    def test_verify_password_failure_on_plain_text(self):
        """Ensure plain-text passwords no longer verify against themselves"""
        from core.auth import verify_password

        # In the old code, 'password' == 'password' would return True if bcrypt was missing
        # Now it should always fail unless it's a valid bcrypt hash
        self.assertFalse(verify_password("password", "password"))

    def test_password_truncation(self):
        """Ensure passwords are truncated to 71 bytes for bcrypt safety"""
        from core.auth import get_password_hash, verify_password
        long_password = "a" * 100
        password_hash = get_password_hash(long_password)
        
        # Should verify with the full long password (because it's truncated consistently)
        self.assertTrue(verify_password(long_password, password_hash))
        
        # Should also verify with just the first 71 characters
        self.assertTrue(verify_password("a" * 71, password_hash))
        
        # Should NOT verify if even one character in the first 71 is wrong
        self.assertFalse(verify_password("b" + "a" * 70, password_hash))

if __name__ == "__main__":
    unittest.main()
