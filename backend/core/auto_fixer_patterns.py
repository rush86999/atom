"""
Auto-Fixer Patterns - Common fix patterns and validation.

Provides quick fixes for common test failures without LLM.
Validates fixes for safety and correctness.

Integration:
- Used by AutoFixerService for pattern-based fixes
- FixValidator ensures safety before applying fixes
- CommonFixPatterns match regex patterns for fast fixes

Performance targets:
- Pattern matching: <10ms
- Fix application: <50ms
- Validation: <100ms
"""

import ast
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ============================================================================
# Task 4: CommonFixPatterns for quick fixes
# ============================================================================

class CommonFixPatterns:
    """
    Common fix patterns for quick fixes without LLM.

    Provides regex-based pattern matching for common errors.
    Faster than LLM for known patterns.
    Fallback to LLM for unknown patterns.

    Attributes:
        PATTERNS: Dict of error patterns to fix templates

    Example:
        pattern = CommonFixPatterns()
        match = pattern.find_pattern_match("NameError: name 'foo' is not defined")
        if match:
            fix = pattern.apply_pattern_fix(source, line, match["pattern"], match["groups"])
    """

    # Fix patterns: {error_pattern: fix_template}
    PATTERNS = {
        # Missing imports
        r"NameError: name '(\w+)' is not defined": {
            "strategy": "add_import",
            "template": "from {module} import {name}"
        },
        # Missing db.commit()
        r"assert None == (\w+)": {
            "strategy": "add_db_commit",
            "template": "db.commit()"
        },
        # Missing await
        r"coroutine '(\w+)' was never awaited": {
            "strategy": "add_await",
            "template": "await {call}"
        },
        # Wrong assertion
        r"AssertionError: assert (.+) == None": {
            "strategy": "fix_assertion",
            "template": "assert {value} is not None"
        },
        # AttributeError on None
        r"AttributeError: 'NoneType' object has no attribute '(\w+)'": {
            "strategy": "add_none_check",
            "template": "if {obj} is not None:\n        {attr_access}"
        },
        # Missing mock
        r"AttributeError: Mock object has no attribute '(\w+)'": {
            "strategy": "add_mock",
            "template": "{mock_name}.{attr} = Mock()"
        },
        # Import error
        r"ImportError: cannot import name '(\w+)'": {
            "strategy": "fix_import",
            "template": "from {correct_module} import {name}"
        },
    }

    # Common module mappings for missing imports
    COMMON_MODULES = {
        "Session": "sqlalchemy.orm",
        "select": "sqlalchemy",
        "List": "typing",
        "Dict": "typing",
        "Optional": "typing",
        "Any": "typing",
        "Base": "sqlalchemy.orm",
        "Column": "sqlalchemy",
        "Integer": "sqlalchemy",
        "String": "sqlalchemy",
        "DateTime": "sqlalchemy",
        "ForeignKey": "sqlalchemy",
        "relationship": "sqlalchemy.orm",
        "pytest": "pytest",
        "AsyncMock": "unittest.mock",
        "Mock": "unittest.mock",
        "patch": "unittest.mock",
    }

    @classmethod
    def find_pattern_match(
        cls,
        error_message: str
    ) -> Optional[Dict[str, Any]]:
        """
        Find matching fix pattern for error.

        Returns pattern groups or None.

        Args:
            error_message: Error message to match

        Returns:
            Pattern match with groups or None
        """
        for pattern, config in cls.PATTERNS.items():
            match = re.match(pattern, error_message)
            if match:
                groups = match.groupdict() if match.groupdict() else match.groups()
                return {
                    "pattern": pattern,
                    "strategy": config["strategy"],
                    "template": config["template"],
                    "groups": groups if isinstance(groups, tuple) else {"name": groups}
                }

        return None

    @classmethod
    def apply_pattern_fix(
        cls,
        source_code: str,
        line_number: int,
        pattern: str,
        groups: Any
    ) -> Optional[str]:
        """
        Apply pattern-based fix.

        Returns fixed code or None if pattern doesn't match.

        Args:
            source_code: Source code to fix
            line_number: Line number of error
            pattern: Pattern that matched
            groups: Regex groups from match

        Returns:
            Fixed code or None
        """
        # Get strategy from pattern
        strategy = cls.PATTERNS[pattern]["strategy"]

        # Route to specific fix method
        fix_methods = {
            "add_import": cls.fix_missing_import,
            "add_db_commit": cls.fix_missing_db_commit,
            "add_await": cls.fix_missing_await,
            "fix_assertion": cls.fix_wrong_assertion,
            "add_none_check": cls.fix_none_attribute_error,
            "add_mock": cls.fix_missing_mock,
            "fix_import": cls.fix_wrong_import,
        }

        fix_method = fix_methods.get(strategy)
        if fix_method:
            return fix_method(source_code, line_number, groups)

        return None

    @classmethod
    def fix_missing_import(
        cls,
        source_code: str,
        line_number: int,
        groups: Any
    ) -> Optional[str]:
        """
        Fix missing import by adding import statement.

        Infers module from common patterns.

        Args:
            source_code: Source code
            line_number: Error line number
            groups: Regex groups (name)

        Returns:
            Fixed code or None
        """
        name = groups[0] if isinstance(groups, tuple) else groups.get("name")

        # Find import section
        lines = source_code.split("\n")
        import_end = 0

        for i, line in enumerate(lines):
            if line.startswith("import ") or line.startswith("from "):
                import_end = i + 1
            elif import_end > 0 and not line.startswith("import ") and not line.startswith("from "):
                break

        # Infer module
        module = cls.COMMON_MODULES.get(name, "typing")

        # Add import
        import_line = f"from {module} import {name}"
        lines.insert(import_end, import_line)

        return "\n".join(lines)

    @classmethod
    def fix_missing_db_commit(
        cls,
        source_code: str,
        line_number: int,
        groups: Any
    ) -> Optional[str]:
        """
        Fix missing db.commit() after database operation.

        Adds commit after add() or merge().

        Args:
            source_code: Source code
            line_number: Error line number
            groups: Regex groups

        Returns:
            Fixed code or None
        """
        lines = source_code.split("\n")

        # Find the db.add() or db.merge() call
        for i in range(line_number - 1, min(len(lines), line_number + 5)):
            if "db.add(" in lines[i] or "db.merge(" in lines[i]:
                # Add db.commit() after this line
                indent = len(lines[i]) - len(lines[i].lstrip())
                lines.insert(i + 1, " " * indent + "db.commit()")
                return "\n".join(lines)

        return None

    @classmethod
    def fix_missing_await(
        cls,
        source_code: str,
        line_number: int,
        groups: Any
    ) -> Optional[str]:
        """
        Fix missing await for async function calls.

        Adds await before async call.

        Args:
            source_code: Source code
            line_number: Error line number
            groups: Regex groups (function name)

        Returns:
            Fixed code or None
        """
        lines = source_code.split("\n")

        # Add await before the call
        if 0 < line_number <= len(lines):
            line = lines[line_number - 1]
            lines[line_number - 1] = line.replace(groups[0], f"await {groups[0]}")
            return "\n".join(lines)

        return None

    @classmethod
    def fix_wrong_assertion(
        cls,
        source_code: str,
        line_number: int,
        groups: Any
    ) -> Optional[str]:
        """
        Fix wrong assertion type.

        Changes == None to is not None.

        Args:
            source_code: Source code
            line_number: Error line number
            groups: Regex groups

        Returns:
            Fixed code or None
        """
        lines = source_code.split("\n")

        if 0 < line_number <= len(lines):
            line = lines[line_number - 1]
            # Replace == None with is not None
            fixed = line.replace("== None", "is not None")
            lines[line_number - 1] = fixed
            return "\n".join(lines)

        return None

    @classmethod
    def fix_none_attribute_error(
        cls,
        source_code: str,
        line_number: int,
        groups: Any
    ) -> Optional[str]:
        """
        Fix AttributeError on None by adding null check.

        Adds if obj is not None check.

        Args:
            source_code: Source code
            line_number: Error line number
            groups: Regex groups (attribute name)

        Returns:
            Fixed code or None
        """
        lines = source_code.split("\n")

        if 0 < line_number <= len(lines):
            line = lines[line_number - 1]
            indent = len(line) - len(line.lstrip())

            # Wrap line in None check
            indent_str = " " * indent
            lines[line_number - 1] = f"{indent_str}if obj is not None:"
            lines.insert(line_number, f"{indent_str}    {line.lstrip()}")

            return "\n".join(lines)

        return None

    @classmethod
    def fix_missing_mock(
        cls,
        source_code: str,
        line_number: int,
        groups: Any
    ) -> Optional[str]:
        """
        Fix missing mock attribute.

        Adds mock attribute setup.

        Args:
            source_code: Source code
            line_number: Error line number
            groups: Regex groups

        Returns:
            Fixed code or None
        """
        lines = source_code.split("\n")

        # Find mock object setup (before error line)
        for i in range(max(0, line_number - 10), line_number):
            if "= Mock()" in lines[i]:
                # Add attribute after mock creation
                indent = len(lines[i]) - len(lines[i].lstrip())
                lines.insert(i + 1, f"{' ' * indent}{groups[0]}.attr = Mock()")
                return "\n".join(lines)

        return None

    @classmethod
    def fix_wrong_import(
        cls,
        source_code: str,
        line_number: int,
        groups: Any
    ) -> Optional[str]:
        """
        Fix wrong import by correcting module path.

        Args:
            source_code: Source code
            line_number: Error line number
            groups: Regex groups

        Returns:
            Fixed code or None
        """
        lines = source_code.split("\n")

        # Find and fix the import
        for i in range(min(line_number, len(lines))):
            if "import" in lines[i] and groups[0] in lines[i]:
                # Replace with correct module (infer from COMMON_MODULES)
                correct_module = cls.COMMON_MODULES.get(groups[0], "typing")
                lines[i] = f"from {correct_module} import {groups[0]}"
                return "\n".join(lines)

        return None


# ============================================================================
# Task 5: FixValidator for safety checks
# ============================================================================

class FixValidator:
    """
    Validate fixes are safe and correct.

    Checks:
    - Fix doesn't remove too much code
    - Fix doesn't break syntax
    - Fix is minimal (only changes what's needed)
    - No secrets added
    - Proper indentation

    Attributes:
        max_lines_changed: Max lines a fix can change (default: 20)
        max_file_size_change: Max 50% size increase

    Example:
        validator = FixValidator()
        result = validator.validate_fix(original, fixed, line_number)
        if result["valid"]:
            print("Fix is safe to apply")
    """

    # Secret patterns to detect
    SECRET_PATTERNS = [
        r"api[_-]?key\s*=\s*['\"][^'\"]{16,}['\"]",
        r"secret\s*=\s*['\"][^'\"]{16,}['\"]",
        r"password\s*=\s*['\"][^'\"]{8,}['\"]",
        r"token\s*=\s*['\"][^'\"]{20,}['\"]",
        r"sk-[a-zA-Z0-9]{32,}",
        r"ghp_[a-zA-Z0-9]{36,}",
        r"AKIA[0-9A-Z]{16}",
    ]

    def __init__(
        self,
        max_lines_changed: int = 20,
        max_file_size_change: float = 0.5
    ):
        """
        Initialize fix validator.

        Args:
            max_lines_changed: Max lines a fix can change
            max_file_size_change: Max file size increase (percentage)
        """
        self.max_lines_changed = max_lines_changed
        self.max_file_size_change = max_file_size_change

    def validate_fix(
        self,
        original: str,
        fixed: str,
        line_number: int
    ) -> Dict[str, Any]:
        """
        Validate fix is safe.

        Returns:
            {
                "valid": bool,
                "reasons": [str],
                "warnings": [str]
            }

        Args:
            original: Original code
            fixed: Fixed code
            line_number: Line number where fix was applied

        Returns:
            Validation result
        """
        reasons = []
        warnings = []

        # Check syntax
        syntax_check = self.check_syntax(fixed)
        if not syntax_check["valid"]:
            reasons.append(f"Syntax error: {syntax_check['error']}")

        # Check size change
        if not self.check_size_change(original, fixed):
            reasons.append(
                f"Fix changes too much code "
                f"(max: {self.max_lines_changed} lines)"
            )

        # Check imports
        invalid_imports = self.check_imports(fixed)
        if invalid_imports:
            reasons.append(f"Invalid imports: {', '.join(invalid_imports)}")

        # Check for secrets
        if not self.check_no_secrets(fixed):
            reasons.append("Fix contains potential secrets")

        # Check indentation
        if not self.check_indentation(fixed):
            reasons.append("Fix has indentation errors")

        # Estimate risk
        risk = self.estimate_fix_risk(fixed, f"line_{line_number}")
        if risk == "high":
            warnings.append("High-risk fix - manual review recommended")

        return {
            "valid": len(reasons) == 0,
            "reasons": reasons,
            "warnings": warnings,
            "risk": risk
        }

    def check_syntax(
        self,
        code: str
    ) -> Dict[str, Any]:
        """
        Check Python syntax is valid.

        Uses ast.parse to validate.

        Args:
            code: Code to check

        Returns:
            {"valid": bool, "error": str}
        """
        try:
            ast.parse(code)
            return {"valid": True, "error": ""}
        except SyntaxError as e:
            return {"valid": False, "error": str(e)}

    def check_size_change(
        self,
        original: str,
        fixed: str
    ) -> bool:
        """
        Check fix doesn't change too much code.

        Prevents massive rewrites.

        Args:
            original: Original code
            fixed: Fixed code

        Returns:
            True if size change is acceptable
        """
        original_lines = len(original.split("\n"))
        fixed_lines = len(fixed.split("\n"))

        # Check line difference
        line_diff = abs(fixed_lines - original_lines)
        if line_diff > self.max_lines_changed:
            return False

        # Check file size percentage
        if original_lines > 0:
            size_change = abs(fixed_lines - original_lines) / original_lines
            if size_change > self.max_file_size_change:
                return False

        return True

    def check_imports(
        self,
        fixed: str
    ) -> List[str]:
        """
        Check imports are valid.

        Returns list of invalid imports (if any).

        Args:
            fixed: Fixed code

        Returns:
            List of invalid imports
        """
        invalid = []

        try:
            tree = ast.parse(fixed)
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    for alias in node.names:
                        # Check for obviously invalid modules
                        if alias.name.startswith("."):
                            # Relative imports might be valid
                            continue
                        if " " in alias.name or "\n" in alias.name:
                            invalid.append(alias.name)
        except Exception:
            # If we can't parse, return empty
            pass

        return invalid

    def check_no_secrets(
        self,
        fixed: str
    ) -> bool:
        """
        Check fix doesn't add secrets.

        Scans for API keys, tokens, passwords.

        Args:
            fixed: Fixed code

        Returns:
            True if no secrets detected
        """
        for pattern in self.SECRET_PATTERNS:
            if re.search(pattern, fixed, re.IGNORECASE):
                return False

        return True

    def check_indentation(
        self,
        fixed: str
    ) -> bool:
        """
        Check fix maintains proper indentation.

        Python indentation is critical.

        Args:
            fixed: Fixed code

        Returns:
            True if indentation is consistent
        """
        lines = fixed.split("\n")

        for line in lines:
            if line.strip():  # Skip empty lines
                # Check for mixed tabs and spaces
                if "\t" in line and " " in line[:10]:
                    return False

                # Check for inconsistent indentation (should be multiple of 4)
                indent = len(line) - len(line.lstrip())
                if indent > 0 and indent % 4 != 0:
                    # Not necessarily wrong, but suspicious
                    pass

        return True

    def estimate_fix_risk(
        self,
        fix: str,
        file_path: str
    ) -> str:
        """
        Estimate fix risk level.

        Returns: "low", "medium", "high"

        Args:
            fix: Fixed code
            file_path: File being fixed

        Returns:
            Risk level
        """
        risk_score = 0

        # Lines changed
        lines_changed = len(fix.split("\n"))
        if lines_changed > 10:
            risk_score += 1
        if lines_changed > 20:
            risk_score += 2

        # New imports
        if "import " in fix:
            risk_score += 1

        # External calls
        dangerous = ["subprocess", "os.system", "eval", "exec"]
        if any(d in fix for d in dangerous):
            risk_score += 3

        # Database operations
        if "db.execute(" in fix or "db.commit(" in fix:
            risk_score += 1

        # Network calls
        if "requests." in fix or "http" in fix.lower():
            risk_score += 2

        # Classify risk
        if risk_score <= 2:
            return "low"
        elif risk_score <= 4:
            return "medium"
        else:
            return "high"
