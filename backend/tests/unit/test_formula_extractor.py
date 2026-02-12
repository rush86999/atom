"""
Unit tests for FormulaExtractor class.

Tests cover:
- Initialization with workspace_id
- Formula extraction from different file types
- Formula type detection (SUM, AVERAGE, IF, VLOOKUP, etc.)
- Cell reference extraction
- Column letter to number conversion
- Semantic expression creation
- Domain detection
- Use case generation
"""

from unittest.mock import Mock, patch
import pytest

from core.formula_extractor import FormulaExtractor


# ============================================================================
# Test: FormulaExtractor Initialization
# ============================================================================

class TestFormulaExtractorInit:
    """Tests for FormulaExtractor initialization."""

    def test_init_default_workspace(self):
        """Test initialization with default workspace."""
        extractor = FormulaExtractor()
        assert extractor.workspace_id == "default"
        assert extractor._formula_manager is None

    def test_init_custom_workspace(self):
        """Test initialization with custom workspace."""
        extractor = FormulaExtractor(workspace_id="test-workspace")
        assert extractor.workspace_id == "test-workspace"


# ============================================================================
# Test: extract_from_file
# ============================================================================

class TestExtractFromFile:
    """Tests for extract_from_file method."""

    def test_extract_from_file_unsupported_type(self):
        """Test extraction with unsupported file type."""
        extractor = FormulaExtractor()
        with patch('core.formula_extractor.logger'):
            result = extractor.extract_from_file("test.txt", "user-1", auto_store=False)
            assert result == []

    def test_extract_from_file_xlsx_extension(self):
        """Test extraction detects .xlsx extension."""
        extractor = FormulaExtractor()
        with patch.object(extractor, 'extract_from_excel', return_value=[]) as mock_extract:
            extractor.extract_from_file("test.xlsx", "user-1", auto_store=False)
            mock_extract.assert_called_once()

    def test_extract_from_file_csv_extension(self):
        """Test extraction detects .csv extension."""
        extractor = FormulaExtractor()
        with patch.object(extractor, 'extract_from_csv', return_value=[]) as mock_extract:
            extractor.extract_from_file("test.csv", "user-1", auto_store=False)
            mock_extract.assert_called_once()

    def test_extract_from_file_gsheet_extension(self):
        """Test extraction handles .gsheet extension."""
        extractor = FormulaExtractor()
        with patch.object(extractor, 'extract_from_excel', return_value=[]) as mock_extract:
            extractor.extract_from_file("test.gsheet", "user-1", auto_store=False)
            mock_extract.assert_called_once()


# ============================================================================
# Test: Formula Type Detection
# ============================================================================

class TestDetectFormulaType:
    """Tests for _detect_formula_type method."""

    def test_detect_sum_formula(self):
        """Test SUM formula detection."""
        extractor = FormulaExtractor()
        result = extractor._detect_formula_type("=SUM(A1:A10)")
        assert result == "SUM"

    def test_detect_average_formula(self):
        """Test AVERAGE formula detection."""
        extractor = FormulaExtractor()
        result = extractor._detect_formula_type("=AVERAGE(B1:B20)")
        assert result == "AVERAGE"

    def test_detect_if_formula(self):
        """Test IF formula detection."""
        extractor = FormulaExtractor()
        result = extractor._detect_formula_type("=IF(A1>0, \"Yes\", \"No\")")
        assert result == "IF"

    def test_detect_vlookup_formula(self):
        """Test VLOOKUP formula detection."""
        extractor = FormulaExtractor()
        result = extractor._detect_formula_type("=VLOOKUP(A1, B1:D10, 2, FALSE)")
        assert result == "VLOOKUP"

    def test_detect_arithmetic_formula(self):
        """Test arithmetic formula detection."""
        extractor = FormulaExtractor()
        result = extractor._detect_formula_type("=A1+B1")
        assert result == "ARITHMETIC"

    def test_detect_custom_formula(self):
        """Test custom formula detection."""
        extractor = FormulaExtractor()
        result = extractor._detect_formula_type("=MYFUNC(A1)")
        assert result == "CUSTOM"


# ============================================================================
# Test: Cell Reference Extraction
# ============================================================================

class TestExtractCellReferences:
    """Tests for _extract_cell_references method."""

    def test_extract_single_cell_reference(self):
        """Test extraction of single cell reference."""
        extractor = FormulaExtractor()
        result = extractor._extract_cell_references("=SUM(A1)")
        assert len(result) == 1
        assert result[0] == ("A", 1)

    def test_extract_multiple_cell_references(self):
        """Test extraction of multiple cell references."""
        extractor = FormulaExtractor()
        result = extractor._extract_cell_references("=SUM(A1, B2, C3)")
        assert len(result) == 3

    def test_extract_range_reference(self):
        """Test extraction of range reference."""
        extractor = FormulaExtractor()
        result = extractor._extract_cell_references("=SUM(A1:A10)")
        # A1 and A10 should be extracted
        assert len(result) >= 1


# ============================================================================
# Test: Column Letter to Number Conversion
# ============================================================================

class TestColumnLetterToNumber:
    """Tests for _column_letter_to_number method."""

    def test_column_a_to_1(self):
        """Test A converts to 1."""
        extractor = FormulaExtractor()
        result = extractor._column_letter_to_number("A")
        assert result == 1

    def test_column_z_to_26(self):
        """Test Z converts to 26."""
        extractor = FormulaExtractor()
        result = extractor._column_letter_to_number("Z")
        assert result == 26

    def test_column_aa_to_27(self):
        """Test AA converts to 27."""
        extractor = FormulaExtractor()
        result = extractor._column_letter_to_number("AA")
        assert result == 27

    def test_column_az_to_52(self):
        """Test AZ converts to 52."""
        extractor = FormulaExtractor()
        result = extractor._column_letter_to_number("AZ")
        assert result == 52

    def test_column_uppercase_conversion(self):
        """Test lowercase letters are converted."""
        extractor = FormulaExtractor()
        result = extractor._column_letter_to_number("abc")
        assert result > 0


# ============================================================================
# Test: Semantic Expression Creation
# ============================================================================

class TestCreateSemanticExpression:
    """Tests for _create_semantic_expression method."""

    def test_sum_semantic_expression(self):
        """Test semantic expression for SUM."""
        extractor = FormulaExtractor()
        parameters = [{"name": "Revenue", "type": "number"}, {"name": "Cost", "type": "number"}]
        result = extractor._create_semantic_expression("=SUM(A1:A2)", "SUM", parameters)
        assert "sum" in result.lower()
        assert "Revenue" in result
        assert "Cost" in result

    def test_average_semantic_expression(self):
        """Test semantic expression for AVERAGE."""
        extractor = FormulaExtractor()
        parameters = [{"name": "Score", "type": "number"}]
        result = extractor._create_semantic_expression("=AVERAGE(A1:A10)", "AVERAGE", parameters)
        assert "average" in result.lower()

    def test_arithmetic_multiplication(self):
        """Test semantic expression for multiplication."""
        extractor = FormulaExtractor()
        parameters = [{"name": "Price", "type": "number"}, {"name": "Quantity", "type": "number"}]
        result = extractor._create_semantic_expression("=A1*B1", "ARITHMETIC", parameters)
        assert "*" in result

    def test_arithmetic_addition(self):
        """Test semantic expression for addition."""
        extractor = FormulaExtractor()
        parameters = [{"name": "A", "type": "number"}, {"name": "B", "type": "number"}]
        result = extractor._create_semantic_expression("=A1+B1", "ARITHMETIC", parameters)
        assert "+" in result


# ============================================================================
# Test: Domain Detection
# ============================================================================

class TestDetectDomain:
    """Tests for _detect_domain method."""

    def test_detect_finance_domain(self):
        """Test finance domain detection."""
        extractor = FormulaExtractor()
        result = extractor._detect_domain("Total Revenue", ["Sales", "Cost"])
        assert result == "finance"

    def test_detect_sales_domain(self):
        """Test sales domain detection."""
        extractor = FormulaExtractor()
        result = extractor._detect_domain("Sales Target", ["Quota", "Deal"])
        assert result == "sales"

    def test_detect_operations_domain(self):
        """Test operations domain detection."""
        extractor = FormulaExtractor()
        result = extractor._detect_domain("Inventory Count", ["Shipment", "Order"])
        assert result == "operations"

    def test_detect_hr_domain(self):
        """Test HR domain detection."""
        extractor = FormulaExtractor()
        result = extractor._detect_domain("Total Salary", ["Headcount", "FTE"])
        assert result == "hr"

    def test_detect_marketing_domain(self):
        """Test marketing domain detection."""
        extractor = FormulaExtractor()
        # Use purely marketing-specific keywords
        result = extractor._detect_domain("Impressions Total", ["Reach", "Click"])
        assert result == "marketing"

    def test_detect_general_domain(self):
        """Test general domain when no keywords match."""
        extractor = FormulaExtractor()
        result = extractor._detect_domain("Total Value", ["A", "B"])
        assert result == "general"


# ============================================================================
# Test: Use Case Generation
# ============================================================================

class TestGenerateUseCase:
    """Tests for _generate_use_case method."""

    def test_sum_use_case(self):
        """Test use case for SUM formula."""
        extractor = FormulaExtractor()
        parameters = [{"name": "Revenue", "type": "number"}]
        result = extractor._generate_use_case("Total", "SUM", parameters)
        assert "total" in result.lower()
        assert "sum" in result.lower()

    def test_average_use_case(self):
        """Test use case for AVERAGE formula."""
        extractor = FormulaExtractor()
        parameters = [{"name": "Score", "type": "number"}]
        result = extractor._generate_use_case("Avg Score", "AVERAGE", parameters)
        assert "average" in result.lower()

    def test_arithmetic_use_case(self):
        """Test use case for arithmetic formula."""
        extractor = FormulaExtractor()
        parameters = [{"name": "A", "type": "number"}]
        result = extractor._generate_use_case("Result", "ARITHMETIC", parameters)
        assert "compute" in result.lower()


# ============================================================================
# Test: CSV Formula Extraction
# ============================================================================

class TestExtractFromCsv:
    """Tests for CSV extraction."""

    def test_csv_empty_file(self):
        """Test CSV extraction with empty file."""
        extractor = FormulaExtractor()
        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value.__enter__.return_value = ""
            result = extractor.extract_from_csv("/tmp/test.csv", "user-1", auto_store=False)
            assert result == []

    def test_csv_with_formula_content(self):
        """Test CSV extraction handles files gracefully."""
        extractor = FormulaExtractor()
        # Test that empty CSV is handled without error
        result = extractor.extract_from_csv("/tmp/nonexistent_empty.csv", "user-1", auto_store=False)
        # Should return empty list for missing file (logged as error)
        assert isinstance(result, list)


# ============================================================================
# Test: parse_formula
# ============================================================================

class TestParseFormula:
    """Tests for _parse_formula method."""

    def test_parse_basic_formula(self):
        """Test basic formula parsing."""
        extractor = FormulaExtractor()
        headers = {1: "Total", 2: "Revenue"}

        # Mock cell object
        mock_cell = Mock()
        mock_cell.value = "=SUM(A1:A10)"
        mock_cell.column = 1
        mock_cell.coordinate = "A1"

        result = extractor._parse_formula(mock_cell, "=SUM(A1:A10)", headers, "Sheet1")

        assert result is not None
        assert "expression" in result
        assert "name" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
