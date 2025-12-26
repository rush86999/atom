"""
Formula Extractor for ATOM Platform
Extracts formulas from Excel spreadsheets and stores them in Atom's memory.
"""

import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class FormulaExtractor:
    """
    Extracts formulas from Excel files and maps them to semantic descriptions.
    Uses column headers as parameter names for better searchability.
    """

    # Common Excel formula patterns
    FORMULA_PATTERNS = {
        "SUM": r"=SUM\(([^)]+)\)",
        "AVERAGE": r"=AVERAGE\(([^)]+)\)",
        "IF": r"=IF\(([^)]+)\)",
        "VLOOKUP": r"=VLOOKUP\(([^)]+)\)",
        "COUNT": r"=COUNT\(([^)]+)\)",
        "MAX": r"=MAX\(([^)]+)\)",
        "MIN": r"=MIN\(([^)]+)\)",
        "SUMIF": r"=SUMIF\(([^)]+)\)",
        "CONCATENATE": r"=CONCATENATE\(([^)]+)\)",
    }

    # Domain keywords for classification
    DOMAIN_KEYWORDS = {
        "finance": ["revenue", "cost", "profit", "expense", "budget", "margin", "roi", "income", "loss", "tax"],
        "sales": ["sales", "quota", "target", "commission", "deal", "pipeline", "conversion", "lead"],
        "operations": ["inventory", "order", "shipment", "delivery", "capacity", "utilization", "efficiency"],
        "hr": ["salary", "headcount", "turnover", "retention", "attendance", "fte", "employee"],
        "marketing": ["cac", "ltv", "engagement", "reach", "impression", "click", "conversion", "campaign"]
    }

    def __init__(self, workspace_id: str = "default"):
        self.workspace_id = workspace_id
        self._formula_manager = None

    def _get_formula_manager(self):
        """Lazy load formula manager."""
        if self._formula_manager is None:
            from core.formula_memory import get_formula_manager
            self._formula_manager = get_formula_manager(self.workspace_id)
        return self._formula_manager

    def extract_from_excel(
        self,
        file_path: str,
        user_id: str = "default_user",
        auto_store: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Extract all formulas from an Excel file.

        Args:
            file_path: Path to the Excel file
            user_id: Owner of the extracted formulas
            auto_store: If True, automatically store in Atom's memory

        Returns:
            List of extracted formula definitions
        """
        try:
            import openpyxl
        except ImportError:
            logger.error("openpyxl not installed. Run: pip install openpyxl")
            return []

        extracted = []

        try:
            workbook = openpyxl.load_workbook(file_path, data_only=False)

            for sheet_name in workbook.sheetnames:
                sheet = workbook[sheet_name]
                sheet_formulas = self._extract_from_sheet(sheet, sheet_name)
                extracted.extend(sheet_formulas)

            workbook.close()

            if auto_store and extracted:
                self._store_formulas(extracted, user_id, file_path)

            logger.info(f"Extracted {len(extracted)} formulas from {file_path}")
            return extracted

        except Exception as e:
            logger.error(f"Failed to extract formulas from {file_path}: {e}")
            return []

    def _extract_from_sheet(
        self,
        sheet,
        sheet_name: str
    ) -> List[Dict[str, Any]]:
        """Extract formulas from a single worksheet."""
        formulas = []
        headers = self._get_column_headers(sheet)

        for row in sheet.iter_rows():
            for cell in row:
                if cell.value and isinstance(cell.value, str) and cell.value.startswith("="):
                    formula_def = self._parse_formula(
                        cell=cell,
                        formula_str=cell.value,
                        headers=headers,
                        sheet_name=sheet_name
                    )
                    if formula_def:
                        formulas.append(formula_def)

        return formulas

    def _get_column_headers(self, sheet) -> Dict[int, str]:
        """Get column headers from the first row."""
        headers = {}
        for idx, cell in enumerate(sheet[1], start=1):
            if cell.value:
                headers[idx] = str(cell.value).strip()
        return headers

    def _parse_formula(
        self,
        cell,
        formula_str: str,
        headers: Dict[int, str],
        sheet_name: str
    ) -> Optional[Dict[str, Any]]:
        """Parse a formula cell and create a definition."""
        # Get result column name
        result_name = headers.get(cell.column, f"Column_{cell.column}")

        # Detect formula type
        formula_type = self._detect_formula_type(formula_str)

        # Extract cell references and map to headers
        referenced_cols = self._extract_cell_references(formula_str)
        parameters = []
        semantic_parts = []

        for col_letter, col_num in referenced_cols:
            param_name = headers.get(col_num, col_letter)
            parameters.append({"name": param_name, "type": "number"})
            semantic_parts.append(param_name)

        # Create semantic expression
        semantic_expression = self._create_semantic_expression(
            formula_str=formula_str,
            formula_type=formula_type,
            parameters=parameters
        )

        # Detect domain
        domain = self._detect_domain(result_name, semantic_parts)

        # Generate use case description
        use_case = self._generate_use_case(
            result_name=result_name,
            formula_type=formula_type,
            parameters=parameters
        )

        return {
            "expression": semantic_expression,
            "original_formula": formula_str,
            "name": result_name,
            "domain": domain,
            "use_case": use_case,
            "parameters": parameters,
            "source_sheet": sheet_name,
            "source_cell": cell.coordinate
        }

    def _detect_formula_type(self, formula_str: str) -> str:
        """Detect the type of Excel formula."""
        formula_upper = formula_str.upper()

        for func_name in self.FORMULA_PATTERNS.keys():
            if func_name in formula_upper:
                return func_name

        # Check for simple arithmetic
        if any(op in formula_str for op in ["+", "-", "*", "/"]):
            return "ARITHMETIC"

        return "CUSTOM"

    def _extract_cell_references(self, formula_str: str) -> List[Tuple[str, int]]:
        """Extract cell references and their column numbers."""
        # Match patterns like A1, B2, $C$3
        pattern = r"\$?([A-Z]+)\$?\d+"
        matches = re.findall(pattern, formula_str.upper())

        results = []
        for col_letter in set(matches):
            col_num = self._column_letter_to_number(col_letter)
            results.append((col_letter, col_num))

        return results

    def _column_letter_to_number(self, col_letter: str) -> int:
        """Convert column letter to number (A=1, B=2, etc.)."""
        result = 0
        for char in col_letter.upper():
            result = result * 26 + (ord(char) - ord('A') + 1)
        return result

    def _create_semantic_expression(
        self,
        formula_str: str,
        formula_type: str,
        parameters: List[Dict[str, str]]
    ) -> str:
        """Create a semantic expression from the formula."""
        param_names = [p["name"] for p in parameters]

        if formula_type == "SUM":
            return f"sum({', '.join(param_names)})"
        elif formula_type == "AVERAGE":
            return f"average({', '.join(param_names)})"
        elif formula_type == "ARITHMETIC" and len(param_names) == 2:
            # Try to infer the operation
            if "-" in formula_str:
                return f"{param_names[0]} - {param_names[1]}"
            elif "+" in formula_str:
                return f"{param_names[0]} + {param_names[1]}"
            elif "*" in formula_str:
                return f"{param_names[0]} * {param_names[1]}"
            elif "/" in formula_str:
                return f"{param_names[0]} / {param_names[1]}"

        # Default: use parameter names with the formula type
        return f"{formula_type.lower()}({', '.join(param_names)})"

    def _detect_domain(self, result_name: str, param_names: List[str]) -> str:
        """Detect the domain based on column names."""
        all_names = [result_name.lower()] + [n.lower() for n in param_names]
        text = " ".join(all_names)

        for domain, keywords in self.DOMAIN_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text:
                    return domain

        return "general"

    def _generate_use_case(
        self,
        result_name: str,
        formula_type: str,
        parameters: List[Dict[str, str]]
    ) -> str:
        """Generate a natural language use case description."""
        param_names = [p["name"] for p in parameters]

        if formula_type == "SUM":
            return f"Calculate the total {result_name} by summing {' and '.join(param_names)}"
        elif formula_type == "AVERAGE":
            return f"Calculate the average {result_name} from {' and '.join(param_names)}"
        elif formula_type == "ARITHMETIC":
            return f"Compute {result_name} using {' and '.join(param_names)}"
        else:
            return f"Calculate {result_name} using {formula_type} formula"

    def _store_formulas(
        self,
        formulas: List[Dict[str, Any]],
        user_id: str,
        source_file: str
    ):
        """Store extracted formulas in Atom's memory."""
        manager = self._get_formula_manager()
        source_name = Path(source_file).name

        stored_count = 0
        for formula in formulas:
            try:
                formula_id = manager.add_formula(
                    expression=formula["expression"],
                    name=formula["name"],
                    domain=formula["domain"],
                    use_case=formula["use_case"],
                    parameters=formula["parameters"],
                    source=f"excel:{source_name}",
                    user_id=user_id
                )
                if formula_id:
                    stored_count += 1
            except Exception as e:
                logger.warning(f"Failed to store formula {formula['name']}: {e}")

        logger.info(f"Stored {stored_count}/{len(formulas)} formulas from {source_name}")


def get_formula_extractor(workspace_id: str = "default") -> FormulaExtractor:
    """Get a formula extractor instance."""
    return FormulaExtractor(workspace_id)
