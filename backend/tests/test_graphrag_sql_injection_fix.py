"""
Test suite for GraphRAG SQL injection fix verification.

GREEN PHASE: These tests verify the SQL injection fix.
"""

import pytest
from core.graphrag_engine import GraphRAGEngine


class TestGraphRAGSQLInjectionFix:
    """Tests for verifying the SQL injection fix."""

    def test_escape_like_pattern_method_exists(self):
        """
        Test that _escape_like_pattern method now exists.

        GREEN PHASE: After the fix, this method should exist.
        """
        graph_engine = GraphRAGEngine()

        # The fix should add an escape method
        assert hasattr(graph_engine, '_escape_like_pattern'), \
            "Fix applied: _escape_like_pattern method now exists"

    def test_validate_search_input_method_exists(self):
        """
        Test that _validate_search_input method now exists.

        GREEN PHASE: After the fix, this method should exist.
        """
        graph_engine = GraphRAGEngine()

        # The fix should add validation
        assert hasattr(graph_engine, '_validate_search_input'), \
            "Fix applied: _validate_search_input method now exists"

    def test_escape_like_percent(self):
        """
        Test that % character is properly escaped.

        GREEN PHASE: After the fix, % should be escaped to \\%.
        """
        graph_engine = GraphRAGEngine()

        # Test % escaping
        result = graph_engine._escape_like_pattern("test%")
        assert result == "test\\%", "Fix applied: % is escaped to \\%"

    def test_escape_like_underscore(self):
        """
        Test that _ character is properly escaped.

        GREEN PHASE: After the fix, _ should be escaped to \\_.
        """
        graph_engine = GraphRAGEngine()

        # Test _ escaping - ALL underscores are escaped (correctly)
        result = graph_engine._escape_like_pattern("user_data")
        assert result == "user\\_data", f"Fix applied: _ is escaped to \\_. Got: {result}"
        result = graph_engine._escape_like_pattern("test_data")
        assert result == "test\\_data", f"Fix applied: _ is escaped to \\_. Got: {result}"
        # Test single underscore
        result = graph_engine._escape_like_pattern("_")
        assert result == "\\_", f"Fix applied: Single _ is escaped. Got: {result}"

    def test_escape_like_backslash(self):
        """
        Test that backslash is properly escaped.

        GREEN PHASE: After the fix, \\ should be escaped to \\\\.
        """
        graph_engine = GraphRAGEngine()

        # Test backslash escaping
        result = graph_engine._escape_like_pattern("test\\data")
        assert result == "test\\\\data", "Fix applied: \\ is escaped to \\\\"

    def test_validate_search_input_accepts_normal_input(self):
        """
        Test that validation accepts normal input.

        GREEN PHASE: Normal input should pass validation.
        """
        graph_engine = GraphRAGEngine()

        # Normal input should work
        result = graph_engine._validate_search_input("test user")
        assert result == "test user"

    def test_validate_search_input_rejects_long_input(self):
        """
        Test that validation rejects excessively long input.

        GREEN PHASE: Long input should raise ValueError.
        """
        graph_engine = GraphRAGEngine()

        # Long input should raise ValueError
        long_input = "a" * 1000
        with pytest.raises(ValueError, match="too long"):
            graph_engine._validate_search_input(long_input)

    def test_validate_search_input_handles_empty(self):
        """
        Test that validation handles empty input.

        GREEN PHASE: Empty input should return empty string.
        """
        graph_engine = GraphRAGEngine()

        # Empty input should return empty string
        result = graph_engine._validate_search_input("")
        assert result == ""

    def test_source_code_fixed(self):
        """
        Test that source code has been fixed.

        GREEN PHASE: Source should now use validation and escaping.
        """
        import inspect

        # Get the source code of _resolve_canonical_entity
        source = inspect.getsource(GraphRAGEngine._resolve_canonical_entity)

        # Verify the fix - source should call validation (actual pattern: name = self._validate_search_input(name))
        assert '_validate_search_input(' in source, \
            f"Fix applied: Source calls _validate_search_input. Source: {source[:500]}"
        assert '_escape_like_pattern(' in source, \
            f"Fix applied: Source calls _escape_like_pattern. Source: {source[:500]}"

        # Also verify canonical_search uses the methods
        source_search = inspect.getsource(GraphRAGEngine.canonical_search)
        assert '_validate_search_input(' in source_search, \
            "Fix applied: canonical_search calls _validate_search_input"
        assert '_escape_like_pattern(' in source_search, \
            "Fix applied: canonical_search calls _escape_like_pattern"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
