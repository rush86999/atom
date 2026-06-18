"""
Test suite for GraphRAG SQL injection vulnerabilities.

RED PHASE: These tests expose SQL injection vulnerabilities in graphrag_engine.py

The bugs:
1. Line 131: `.ilike(name)` - direct use of user input without escaping LIKE wildcards
2. Line 140: `.ilike(f"%{name}%")` - user input interpolated with special characters
3. Line 165: `.ilike(f"%{query}%")` - similar vulnerability in canonical_search

Note: SQLAlchemy's ILIKE does provide parameter binding which prevents
traditional SQL injection, but the LIKE special characters (% and _)
in user input act as wildcards which is unintended behavior.
"""

import pytest
from core.graphrag_engine import GraphRAGEngine


class TestGraphRAGSQLInjectionBugs:
    """Test suite revealing SQL injection vulnerabilities in GraphRAGEngine."""

    def test_escape_like_pattern_method_missing(self):
        """
        Test that _escape_like_pattern method is missing.

        BUG: There's no function to escape LIKE special characters.
        User input containing % or _ will act as wildcards.
        """
        graph_engine = GraphRAGEngine()

        # Verify the bug - no escape method exists
        assert not hasattr(graph_engine, '_escape_like_pattern'), \
            "Bug confirmed: No _escape_like_pattern method exists to escape LIKE wildcards"

    def test_validate_search_input_method_missing(self):
        """
        Test that _validate_search_input method is missing.

        BUG: There's no input validation for length or invalid characters.
        """
        graph_engine = GraphRAGEngine()

        # Verify the bug - no validation method exists
        assert not hasattr(graph_engine, '_validate_search_input'), \
            "Bug confirmed: No _validate_search_input method exists"

    def test_source_code_reveals_vulnerability(self):
        """
        Test that source code reveals the ILIKE vulnerability.

        BUG: User input is interpolated into ILIKE without escaping.
        """
        import inspect

        # Get the source code of _resolve_canonical_entity
        source = inspect.getsource(GraphRAGEngine._resolve_canonical_entity)

        # Verify the bug - source contains the vulnerable pattern
        assert 'search_term = f"%{name}%"' in source, \
            "Bug confirmed: Source interpolates user input without escaping"
        assert '.ilike(search_term)' in source, \
            "Bug confirmed: Source uses unescaped input in ILIKE"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
