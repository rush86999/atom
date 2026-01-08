"""
Unit Tests for Formula Memory System
Tests formula storage, search, lineage, and execution.
"""

import pytest
import json
from unittest.mock import MagicMock, patch, AsyncMock


class TestFormulaMemoryManager:
    """Tests for FormulaMemoryManager class."""

    def test_add_formula_basic(self):
        """Test adding a basic formula."""
        with patch('core.formula_memory.get_lancedb_handler') as mock_handler:
            mock_db = MagicMock()
            mock_db.add_document.return_value = True
            mock_db.get_table.return_value = MagicMock()
            mock_handler.return_value = mock_db
            
            from core.formula_memory import FormulaMemoryManager
            manager = FormulaMemoryManager("test_workspace")
            
            formula_id = manager.add_formula(
                expression="Revenue - Cost",
                name="Net Profit",
                domain="finance",
                use_case="Calculate the net profit from revenue and cost"
            )
            
            # Should return a formula ID
            assert formula_id is not None

    def test_search_formulas(self):
        """Test searching for formulas."""
        with patch('core.formula_memory.get_lancedb_handler') as mock_handler:
            mock_db = MagicMock()
            mock_db.search.return_value = [
                {
                    "id": "formula_1",
                    "text": "Net Profit. Calculate profit. Domain: finance",
                    "metadata": json.dumps({
                        "expression": "Revenue - Cost",
                        "name": "Net Profit",
                        "domain": "finance",
                        "parameters": "[]"
                    }),
                    "_distance": 0.15
                }
            ]
            mock_db.get_table.return_value = MagicMock()
            mock_handler.return_value = mock_db
            
            from core.formula_memory import FormulaMemoryManager
            manager = FormulaMemoryManager("test_workspace")
            
            results = manager.search_formulas("calculate profit")
            
            assert len(results) == 1
            assert results[0]["name"] == "Net Profit"
            assert results[0]["expression"] == "Revenue - Cost"

    def test_apply_formula_success(self):
        """Test executing a formula with valid inputs."""
        with patch('core.formula_memory.get_lancedb_handler') as mock_handler:
            mock_db = MagicMock()
            mock_db.search.return_value = [
                {
                    "id": "formula_1",
                    "text": "Net Profit calculation",
                    "metadata": json.dumps({
                        "expression": "Revenue - Cost",
                        "name": "Net Profit",
                        "domain": "finance",
                        "parameters": json.dumps([
                            {"name": "Revenue", "type": "number"},
                            {"name": "Cost", "type": "number"}
                        ]),
                        "example_input": "{}",
                        "example_output": "",
                        "dependencies": "[]"
                    })
                }
            ]
            mock_db.get_table.return_value = MagicMock()
            mock_handler.return_value = mock_db
            
            from core.formula_memory import FormulaMemoryManager
            manager = FormulaMemoryManager("test_workspace")
            
            result = manager.apply_formula(
                formula_id="formula_1",
                inputs={"Revenue": 1000, "Cost": 400}
            )
            
            assert result["success"] is True
            assert result["result"] == 600

    def test_apply_formula_missing_param(self):
        """Test formula execution with missing parameter."""
        with patch('core.formula_memory.get_lancedb_handler') as mock_handler:
            mock_db = MagicMock()
            mock_db.search.return_value = [
                {
                    "id": "formula_1",
                    "text": "Net Profit calculation",
                    "metadata": json.dumps({
                        "expression": "Revenue - Cost",
                        "name": "Net Profit",
                        "domain": "finance",
                        "parameters": json.dumps([
                            {"name": "Revenue", "type": "number"},
                            {"name": "Cost", "type": "number"}
                        ]),
                        "example_input": "{}",
                        "example_output": "",
                        "dependencies": "[]"
                    })
                }
            ]
            mock_db.get_table.return_value = MagicMock()
            mock_handler.return_value = mock_db
            
            from core.formula_memory import FormulaMemoryManager
            manager = FormulaMemoryManager("test_workspace")
            
            result = manager.apply_formula(
                formula_id="formula_1",
                inputs={"Revenue": 1000}  # Missing Cost
            )
            
            assert result["success"] is False
            assert "Missing required parameter" in result["error"]


class TestFormulaExtractor:
    """Tests for FormulaExtractor class."""

    def test_detect_domain(self):
        """Test domain detection from column names."""
        from core.formula_extractor import FormulaExtractor
        
        extractor = FormulaExtractor()
        
        assert extractor._detect_domain("Net Profit", ["Revenue", "Cost"]) == "finance"
        assert extractor._detect_domain("Sales Target", ["Quota"]) == "sales"
        assert extractor._detect_domain("Random Column", ["Other"]) == "general"

    def test_column_letter_to_number(self):
        """Test Excel column letter conversion."""
        from core.formula_extractor import FormulaExtractor
        
        extractor = FormulaExtractor()
        
        assert extractor._column_letter_to_number("A") == 1
        assert extractor._column_letter_to_number("B") == 2
        assert extractor._column_letter_to_number("Z") == 26
        assert extractor._column_letter_to_number("AA") == 27

    def test_detect_formula_type(self):
        """Test formula type detection."""
        from core.formula_extractor import FormulaExtractor
        
        extractor = FormulaExtractor()
        
        assert extractor._detect_formula_type("=SUM(A1:B2)") == "SUM"
        assert extractor._detect_formula_type("=AVERAGE(C1:C10)") == "AVERAGE"
        assert extractor._detect_formula_type("=A1-B1") == "ARITHMETIC"
        assert extractor._detect_formula_type("=CUSTOM(X)") == "CUSTOM"


class TestFormulaRoutes:
    """Tests for Formula API routes."""

    @pytest.mark.asyncio
    async def test_create_formula_endpoint(self):
        """Test POST /api/formulas endpoint."""
        with patch('api.formula_routes.get_formula_manager') as mock_manager:
            mock_instance = MagicMock()
            mock_instance.add_formula.return_value = "test_formula_id"
            mock_manager.return_value = mock_instance
            
            from api.formula_routes import create_formula, FormulaCreateRequest
            
            request = FormulaCreateRequest(
                expression="Revenue - Cost",
                name="Net Profit",
                domain="finance"
            )
            
            result = await create_formula(request, "default", "user1")
            
            assert result["success"] is True
            assert result["formula_id"] == "test_formula_id"

    @pytest.mark.asyncio
    async def test_search_formulas_endpoint(self):
        """Test GET /api/formulas/search endpoint."""
        with patch('api.formula_routes.get_formula_manager') as mock_manager:
            mock_instance = MagicMock()
            mock_instance.search_formulas.return_value = [
                {"id": "f1", "name": "Net Profit", "expression": "Revenue - Cost"}
            ]
            mock_manager.return_value = mock_instance
            
            from api.formula_routes import search_formulas
            
            result = await search_formulas(q="profit", limit=10, workspace_id="default")
            
            assert result.count == 1
            assert result.formulas[0]["name"] == "Net Profit"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
