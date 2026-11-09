"""Execute the exact producer body with controlled DB/password/token doubles.
No module import, engine creation, or live identity operation is performed.
This is producer-unit evidence, not HTTP/authentication qualification.
"""
import ast
import asyncio
import sys
import types
import unittest
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime, timezone
from unittest.mock import Mock

source = Path(sys.argv.pop(1))
tree = ast.parse(source.read_text())
node = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == 'authenticate_mobile_user')

class User:
    email = 'controlled-column'

class MobileDevice:
    device_token = 'controlled-column'

class UserStatus:
    ACTIVE = 'active'

class LoginWorkspaceProducer(unittest.TestCase):
    def run_producer(self, workspace, password_ok=True):
        user = types.SimpleNamespace(id='owner-001', email='local@example.invalid', status='active', hashed_password='controlled-private-material', first_name='Local', last_name='Owner', role='member', workspace_id=workspace)
        device = types.SimpleNamespace(id='device-001', platform='ios', status='active')
        db = Mock()
        db.query.return_value.filter.return_value.first.side_effect = [user, device]
        create_token = Mock(return_value={'access_token': 'controlled-only', 'refresh_token': 'controlled-only'})
        namespace = {'Any': Any, 'Dict': Dict, 'Optional': Optional, 'Session': object, 'User': User, 'MobileDevice': MobileDevice, 'UserStatus': UserStatus, 'verify_password': lambda *_: password_ok, 'create_mobile_token': create_token, 'datetime': datetime, 'timezone': timezone}
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), 'exec'), namespace)
        result = asyncio.run(namespace['authenticate_mobile_user']('local@example.invalid', 'controlled-password', 'controlled-device-reference', 'ios', db))
        return result, create_token, db

    def test_authoritative_workspace_is_preserved(self):
        result, _, _ = self.run_producer('workspace-opaque-0001')
        self.assertEqual(result['user']['workspace_id'], 'workspace-opaque-0001')

    def test_missing_workspace_is_explicit_null_not_default(self):
        result, _, _ = self.run_producer(None)
        self.assertIn('workspace_id', result['user'])
        self.assertIsNone(result['user']['workspace_id'])

    def test_invalid_password_still_creates_no_token(self):
        result, create_token, db = self.run_producer('workspace-opaque-0001', False)
        self.assertIsNone(result)
        create_token.assert_not_called()
        db.commit.assert_not_called()

if __name__ == '__main__':
    unittest.main(verbosity=2)
