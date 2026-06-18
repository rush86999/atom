"""
Test suite for Error Handling gaps.

RED PHASE: These tests expose error handling bugs.

The bugs:
1. lancedb_handler.py:847, 898 - bare except clauses
2. llm/byok_handler.py:1130, 1833 - bare except clauses
3. cache.py: multiple lines - except Exception: pass (silent failures)
4. directory_permission.py:200 - bare except clause
5. local_agent_service.py:355, 443 - bare except clauses
"""

import pytest
import inspect


class TestErrorHandlingGaps:
    """
    Test suite revealing error handling gaps.

    The bug: Bare except clauses and silent failures hide errors,
    making debugging difficult and allowing failures to go unnoticed.
    """

    def test_lancedb_bare_except(self):
        """
        Test that lancedb_handler has bare except clauses.

        BUG: Lines 847, 898 use bare except: which catches SystemExit/KeyboardInterrupt.
        """
        from core.lancedb_handler import LanceDBHandler

        source = inspect.getsource(LanceDBHandler)

        # Verify the bug - bare except exists
        assert 'except:' in source, \
            "Bug confirmed: Bare except clause catches all exceptions including SystemExit"

    def test_byok_handler_bare_except(self):
        """
        Test that byok_handler has bare except clauses.

        BUG: Lines 1130, 1833 use bare except: without handling.
        """
        from core.llm.byok_handler import BYOKHandler

        source = inspect.getsource(BYOKHandler)

        # Verify the bug - bare except exists
        assert 'except:' in source, \
            "Bug confirmed: Bare except clause catches all exceptions"

    def test_cache_silent_failures(self):
        """
        Test that cache has silent failures.

        BUG: Multiple lines use 'except Exception: pass' which hides errors.
        """
        # Read the file directly to check for the pattern
        with open('/Users/rushiparikh/projects/atom/backend/core/cache.py', 'r') as f:
            content = f.read()

        # Verify the bug - silent exceptions
        assert 'except Exception: pass' in content, \
            "Bug confirmed: Silent failures with 'except Exception: pass'"

    def test_directory_permission_bare_except(self):
        """
        Test that directory_permission has bare except clause.

        BUG: Line 200 uses bare except: without handling.
        """
        from core.directory_permission import DirectoryPermissionService

        source = inspect.getsource(DirectoryPermissionService)

        # Verify the bug - bare except exists
        assert 'except:' in source, \
            "Bug confirmed: Bare except clause without error handling"

    def test_local_agent_bare_except(self):
        """
        Test that local_agent_service has bare except clauses.

        BUG: Lines 355, 443 use bare except: without handling.
        """
        from core.local_agent_service import LocalAgentService

        source = inspect.getsource(LocalAgentService)

        # Verify the bug - bare except exists
        assert 'except:' in source, \
            "Bug confirmed: Bare except clause without error logging"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
