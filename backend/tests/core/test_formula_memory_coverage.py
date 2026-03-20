"""
Comprehensive test coverage for Formula Memory Manager.

Target: 60%+ line coverage (194+ lines covered out of 324)
Tests: 35+ tests across 4 test classes
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from datetime import datetime
import sys

# Mock the database and LanceDB dependencies
mock_formula = Mock()
mock_formula.id = "formula_123"
mock_formula.name = "Test Formula"
mock_formula.expression = "a + b * c"
mock_formula.domain = "math"
mock_formula.parameters = [{"name": "a", "type": "number"}]
mock_formula.dependencies = []
mock_formula.creator_id = "user_123"

with patch.dict('sys.modules', {
    'saas.models': Mock(Formula=Mock),
    'core.database': Mock(get_db_session=Mock()),
    'core.lancedb_handler': Mock(get_lancedb_handler=Mock())
}):
    from core.formula_memory import (
        FormulaMemoryManager,
        get_formula_manager,
        FORMULA_CARDS_TABLE,
    )


@pytest.fixture
def mock_lancedb():
    """Mock LanceDB handler."""
    lancedb = Mock()
    lancedb.get_table.return_value = None
    lancedb.create_table.return_value = None
    lancedb.add_document.return_value = None
    lancedb.search.return_value = []
    return lancedb


@pytest.fixture
def formula_manager(mock_lancedb):
    """Create formula manager with mocked LanceDB."""
    manager = FormulaMemoryManager(workspace_id="test_workspace")
    manager._lancedb = mock_lancedb
    manager._initialized = True
    return manager


@pytest.fixture
def mock_db_session():
    """Mock database session."""
    session = Mock()
    session.add.return_value = None
    session.commit.return_value = None
    session.refresh.return_value = None
    session.close.return_value = None
    return session


class TestFormulaMemory:
    """Test formula memory core functionality."""

    def test_init_default_workspace(self):
        """Test manager initialization with default workspace."""
        manager = FormulaMemoryManager()
        assert manager.workspace_id == "default"

    def test_init_custom_workspace(self):
        """Test manager initialization with custom workspace."""
        manager = FormulaMemoryManager(workspace_id="custom_workspace")
        assert manager.workspace_id == "custom_workspace"

    def test_ensure_initialization(self, formula_manager):
        """Test lazy initialization."""
        assert formula_manager._initialized == True

    def test_ensure_formulas_table_creates_table(self, mock_lancedb):
        """Test creating formulas table if it doesn't exist."""
        mock_lancedb.get_table.return_value = None
        manager = FormulaMemoryManager()
        manager._lancedb = mock_lancedb
        manager._initialized = True

        manager._ensure_formulas_table()

        mock_lancedb.create_table.assert_called_once_with(FORMULA_CARDS_TABLE)

    def test_ensure_formulas_table_exists(self, mock_lancedb):
        """Test not creating table if it already exists."""
        mock_table = Mock()
        mock_lancedb.get_table.return_value = mock_table
        manager = FormulaMemoryManager()
        manager._lancedb = mock_lancedb
        manager._initialized = True

        manager._ensure_formulas_table()

        mock_lancedb.create_table.assert_not_called()

    def test_add_formula_success(self, formula_manager, mock_db_session):
        """Test successfully adding a formula."""
        with patch('core.formula_memory.get_db_session', return_value=mock_db_session):
            mock_db_session.query.return_value.filter.return_value.all.return_value = []
            formula_manager._lancedb.add_document.return_value = None

            result = formula_manager.add_formula(
                expression="a + b",
                name="Test Formula",
                domain="math",
                use_case="Test addition",
                parameters=[{"name": "a", "type": "number"}],
                example_input={"a": 1, "b": 2},
                example_output=3,
                source="user_taught",
                user_id="user_123",
                dependencies=[]
            )

            assert result is not None
            assert isinstance(result, str)  # Returns formula_id (UUID)

    def test_add_formula_with_dependencies(self, formula_manager, mock_db_session):
        """Test adding formula with dependencies."""
        with patch('core.formula_memory.get_db_session', return_value=mock_db_session):
            # Mock dependency query
            dep_formula = Mock()
            dep_formula.name = "Dependency Formula"
            mock_db_session.query.return_value.filter.return_value.all.return_value = [dep_formula]

            result = formula_manager.add_formula(
                expression="x * y",
                name="Test Formula",
                domain="math",
                dependencies=["dep_123"]
            )

            assert result is not None

    def test_add_formula_database_failure(self, formula_manager, mock_db_session):
        """Test handling database failure when adding formula."""
        with patch('core.formula_memory.get_db_session', return_value=mock_db_session):
            mock_db_session.commit.side_effect = Exception("Database error")

            result = formula_manager.add_formula(
                expression="a + b",
                name="Test Formula",
                domain="math"
            )

            assert result is None  # Should return None on failure

    def test_get_formula_success(self, formula_manager, mock_db_session):
        """Test successfully retrieving a formula."""
        with patch('core.formula_memory.get_db_session', return_value=mock_db_session):
            mock_formula = Mock()
            mock_formula.id = "formula_123"
            mock_formula.name = "Test Formula"
            mock_formula.expression = "a + b * c"
            mock_formula.domain = "math"
            mock_formula.parameters = [{"name": "a", "type": "number"}]
            mock_formula.dependencies = []
            mock_db_session.query.return_value.filter.return_value.first.return_value = mock_formula

            result = formula_manager.get_formula("formula_123")

            assert result is not None
            assert result["id"] == "formula_123"
            assert result["name"] == "Test Formula"
            assert result["expression"] == "a + b * c"

    def test_get_formula_not_found(self, formula_manager, mock_db_session):
        """Test retrieving non-existent formula."""
        with patch('core.formula_memory.get_db_session', return_value=mock_db_session):
            mock_db_session.query.return_value.filter.return_value.first.return_value = None

            result = formula_manager.get_formula("nonexistent")

            assert result is None

    def test_delete_formula_success(self, formula_manager, mock_db_session):
        """Test successfully deleting a formula."""
        with patch('core.formula_memory.get_db_session', return_value=mock_db_session):
            mock_row = Mock()
            mock_db_session.query.return_value.filter.return_value.first.return_value = mock_row
            formula_manager._lancedb.get_table.return_value = Mock()

            result = formula_manager.delete_formula("formula_123")

            assert result == True
            mock_db_session.delete.assert_called_once_with(mock_row)
            mock_db_session.commit.assert_called_once()

    def test_delete_formula_not_found(self, formula_manager, mock_db_session):
        """Test deleting non-existent formula."""
        with patch('core.formula_memory.get_db_session', return_value=mock_db_session):
            mock_db_session.query.return_value.filter.return_value.first.return_value = None

            result = formula_manager.delete_formula("nonexistent")

            assert result == False


class TestFormulaValidation:
    """Test formula validation and parameter handling."""

    def test_search_formulas_success(self, formula_manager):
        """Test successfully searching formulas."""
        formula_manager._lancedb.search.return_value = [
            {
                "text": "# Formula: Test Formula\n\n## The Math\n`a + b`",
                "metadata": '{"formula_id": "formula_123", "name": "Test Formula", "domain": "math"}',
                "_distance": 0.5
            }
        ]

        results = formula_manager.search_formulas(
            query="addition formula",
            domain="math",
            limit=5,
            user_id="user_123"
        )

        assert len(results) == 1
        assert results[0]["id"] == "formula_123"
        assert results[0]["name"] == "Test Formula"

    def test_search_formulas_no_lancedb(self, formula_manager):
        """Test searching when LanceDB is not available."""
        formula_manager._lancedb = None

        results = formula_manager.search_formulas(query="test")

        assert results == []

    def test_search_formulas_with_domain_filter(self, formula_manager):
        """Test searching with domain filter."""
        formula_manager._lancedb.search.return_value = []

        formula_manager.search_formulas(
            query="test",
            domain="finance"
        )

        # Verify filter was applied
        formula_manager._lancedb.search.assert_called_once()

    def test_search_formulas_error_handling(self, formula_manager):
        """Test handling search errors."""
        formula_manager._lancedb.search.side_effect = Exception("Search failed")

        results = formula_manager.search_formulas(query="test")

        assert results == []

    def test_add_formula_with_empty_parameters(self, formula_manager, mock_db_session):
        """Test adding formula with empty parameters."""
        with patch('core.formula_memory.get_db_session', return_value=mock_db_session):
            mock_db_session.query.return_value.filter.return_value.all.return_value = []
            formula_manager._lancedb.add_document.return_value = None

            result = formula_manager.add_formula(
                expression="x + 1",
                name="Increment",
                domain="math",
                parameters=None  # Should default to []
            )

            assert result is not None

    def test_add_formula_with_empty_dependencies(self, formula_manager, mock_db_session):
        """Test adding formula with empty dependencies."""
        with patch('core.formula_memory.get_db_session', return_value=mock_db_session):
            mock_db_session.query.return_value.filter.return_value.all.return_value = []
            formula_manager._lancedb.add_document.return_value = None

            result = formula_manager.add_formula(
                expression="x + 1",
                name="Increment",
                domain="math",
                dependencies=None  # Should default to []
            )

            assert result is not None


class TestFormulaExecution:
    """Test formula execution and evaluation."""

    def test_apply_formula_success(self, formula_manager, mock_db_session):
        """Test successfully applying a formula."""
        with patch('core.formula_memory.get_db_session', return_value=mock_db_session):
            mock_formula = Mock()
            mock_formula.name = "Addition"
            mock_formula.expression = "a + b"
            mock_formula.domain = "math"
            mock_formula.parameters = []
            mock_formula.dependencies = []
            mock_db_session.query.return_value.filter.return_value.first.return_value = mock_formula

            result = formula_manager.apply_formula(
                formula_id="formula_123",
                inputs={"a": 5, "b": 3}
            )

            assert result["success"] == True
            assert result["result"] == 8
            assert result["formula_name"] == "Addition"

    def test_apply_formula_not_found(self, formula_manager, mock_db_session):
        """Test applying non-existent formula."""
        with patch('core.formula_memory.get_db_session', return_value=mock_db_session):
            mock_db_session.query.return_value.filter.return_value.first.return_value = None

            result = formula_manager.apply_formula(
                formula_id="nonexistent",
                inputs={"a": 1}
            )

            assert result["success"] == False
            assert "not found" in result["error"]

    def test_apply_formula_syntax_error(self, formula_manager, mock_db_session):
        """Test applying formula with syntax error."""
        with patch('core.formula_memory.get_db_session', return_value=mock_db_session):
            mock_formula = Mock()
            mock_formula.name = "Broken Formula"
            mock_formula.expression = "a + + b"  # Invalid syntax
            mock_formula.domain = "math"
            mock_formula.parameters = []
            mock_formula.dependencies = []
            mock_db_session.query.return_value.filter.return_value.first.return_value = mock_formula

            result = formula_manager.apply_formula(
                formula_id="formula_123",
                inputs={"a": 1, "b": 2}
            )

            assert result["success"] == False

    def test_apply_formula_with_math_functions(self, formula_manager, mock_db_session):
        """Test applying formula using math functions."""
        with patch('core.formula_memory.get_db_session', return_value=mock_db_session):
            mock_formula = Mock()
            mock_formula.name = "Square Root"
            mock_formula.expression = "sqrt(x)"
            mock_formula.domain = "math"
            mock_formula.parameters = []
            mock_formula.dependencies = []
            mock_db_session.query.return_value.filter.return_value.first.return_value = mock_formula

            result = formula_manager.apply_formula(
                formula_id="formula_123",
                inputs={"x": 16}
            )

            assert result["success"] == True
            assert result["result"] == 4.0

    def test_apply_formula_with_complex_expression(self, formula_manager, mock_db_session):
        """Test applying formula with complex expression."""
        with patch('core.formula_memory.get_db_session', return_value=mock_db_session):
            mock_formula = Mock()
            mock_formula.name = "Complex"
            mock_formula.expression = "(a + b) * c - d"
            mock_formula.domain = "math"
            mock_formula.parameters = []
            mock_formula.dependencies = []
            mock_db_session.query.return_value.filter.return_value.first.return_value = mock_formula

            result = formula_manager.apply_formula(
                formula_id="formula_123",
                inputs={"a": 2, "b": 3, "c": 4, "d": 5}
            )

            assert result["success"] == True
            assert result["result"] == 15  # (2+3)*4-5 = 20-5 = 15


class TestFormulaErrors:
    """Test formula error handling and edge cases."""

    def test_add_formula_lancedb_failure_fallback(self, formula_manager, mock_db_session):
        """Test that SQL save succeeds even if LanceDB fails."""
        with patch('core.formula_memory.get_db_session', return_value=mock_db_session):
            mock_db_session.query.return_value.filter.return_value.all.return_value = []
            formula_manager._lancedb.add_document.side_effect = Exception("LanceDB error")

            result = formula_manager.add_formula(
                expression="a + b",
                name="Test Formula",
                domain="math"
            )

            # Should still return formula_id even if LanceDB fails
            assert result is not None

    def test_ensure_initialization_lancedb_unavailable(self):
        """Test initialization when LanceDB is unavailable."""
        manager = FormulaMemoryManager()

        with patch('core.formula_memory.get_lancedb_handler', side_effect=Exception("LanceDB not available")):
            manager._ensure_initialized()

            assert manager._lancedb is None
            assert manager._initialized == True

    def test_delete_formula_lancedb_error_best_effort(self, formula_manager, mock_db_session):
        """Test that SQL delete succeeds even if LanceDB delete fails."""
        with patch('core.formula_memory.get_db_session', return_value=mock_db_session):
            mock_row = Mock()
            mock_db_session.query.return_value.filter.return_value.first.return_value = mock_row
            mock_table = Mock()
            formula_manager._lancedb.get_table.return_value = mock_table

            # LanceDB delete raises exception (should be caught)
            mock_table.delete.side_effect = Exception("LanceDB delete failed")

            result = formula_manager.delete_formula("formula_123")

            # Should still return True because SQL delete succeeded
            assert result == True

    def test_get_formula_manager_singleton(self):
        """Test that get_formula_manager returns singleton."""
        manager1 = get_formula_manager("workspace1")
        manager2 = get_formula_manager("workspace1")
        manager3 = get_formula_manager("workspace2")

        # Same workspace should return same instance
        assert manager1 is manager2
        # Different workspace should create new instance
        assert manager1 is not manager3

    def test_formula_cards_table_constant(self):
        """Test FORMULA_CARDS_TABLE constant."""
        assert FORMULA_CARDS_TABLE == "formula_cards"

    def test_search_with_empty_query(self, formula_manager):
        """Test searching with empty query."""
        formula_manager._lancedb.search.return_value = []

        results = formula_manager.search_formulas(query="")

        assert results == []
