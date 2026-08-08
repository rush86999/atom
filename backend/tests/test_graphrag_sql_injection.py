"""
Test suite for GraphRAG SQL injection mitigations.

The LIKE-wildcard and unvalidated-input vulnerabilities in graphrag_engine.py
have been fixed. These tests assert the current SAFE behavior:

1. `_validate_search_input` exists and rejects over-long input (DoS guard)
2. `_escape_like_pattern` exists and escapes LIKE special characters
   (% and _) so user input cannot act as wildcards
3. `_resolve_canonical_entity` escapes user input before interpolating
   it into an ILIKE pattern
"""

import pytest
from core.graphrag_engine import GraphRAGEngine


class TestGraphRAGSQLInjectionBugs:
    """Test suite for GraphRAG SQL injection mitigations."""

    def test_escape_like_pattern_method_exists(self):
        """
        Test that _escape_like_pattern escapes LIKE wildcards.

        User input containing % or _ must not act as SQL LIKE wildcards.
        """
        graph_engine = GraphRAGEngine()

        # The escape method must exist and escape LIKE special characters
        assert hasattr(graph_engine, '_escape_like_pattern'), \
            "_escape_like_pattern method is missing"

        assert graph_engine._escape_like_pattern("test%") == "test\\%"
        assert graph_engine._escape_like_pattern("50%") == "50\\%"
        assert graph_engine._escape_like_pattern("user_name") == "user\\_name"
        assert graph_engine._escape_like_pattern("plain") == "plain"

    def test_validate_search_input_method_exists(self):
        """
        Test that _validate_search_input guards against over-long input.

        Over-long input must be rejected to prevent performance issues
        and DoS attempts.
        """
        graph_engine = GraphRAGEngine()

        # The validation method must exist and clamp input length
        assert hasattr(graph_engine, '_validate_search_input'), \
            "_validate_search_input method is missing"

        # Valid input passes through
        assert graph_engine._validate_search_input("Project Alpha") == "Project Alpha"

        # Over-long input is rejected (500 char default limit)
        with pytest.raises(ValueError):
            graph_engine._validate_search_input("A" * 501)

    def test_source_code_escapes_input(self):
        """
        Test that _resolve_canonical_entity escapes user input.

        User input must be validated and LIKE-escaped before being
        interpolated into an ILIKE pattern.
        """
        import inspect

        # Get the source code of _resolve_canonical_entity
        source = inspect.getsource(GraphRAGEngine._resolve_canonical_entity)

        # Input must be validated and escaped before building the pattern
        assert '_validate_search_input(name)' in source, \
            "Source does not validate search input before use"
        assert '_escape_like_pattern(name)' in source, \
            "Source does not escape LIKE wildcards before use"
        assert '.ilike(search_term)' in source, \
            "Source no longer uses the escaped pattern in ILIKE"
        # The raw vulnerable interpolation must be gone
        assert 'f"%{name}%"' not in source, \
            "Source still interpolates unescaped user input"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
