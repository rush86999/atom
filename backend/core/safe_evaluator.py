"""
Safe Expression Evaluator - AST-based validation for eval() safety.

Provides a safe alternative to eval() that only allows:
- Literals (numbers, strings, booleans, None)
- Variable names (from provided context)
- Basic operators (+, -, *, /, //, %, **)
- Comparisons (==, !=, <, >, <=, >=)
- Boolean operators (and, or, not)
- Whitelisted function calls (sum, min, max, abs, round, sqrt, pow, etc.)
- Parentheses for grouping

BLOCKS:
- Non-whitelisted function calls
- Attribute access (obj.attr, obj.__class__)
- Imports
- Lambda expressions
- Comprehensions
- Any other dangerous operations

Reference: CWE-94 Code Injection
"""

import ast
import logging
from typing import Any, Dict, Optional, Set

logger = logging.getLogger(__name__)


class SafeEvalError(Exception):
    """Raised when safe evaluation fails."""
    pass


class SafeEvaluator(ast.NodeVisitor):
    """
    AST validator for safe expression evaluation.

    Only allows a limited set of AST nodes to prevent code injection.
    Function calls are only allowed to whitelisted safe functions.
    """

    # Whitelist of safe function names that can be called
    SAFE_FUNCTIONS: Set[str] = {
        'sum', 'min', 'max', 'abs', 'round', 'len',
        'sqrt', 'pow', 'log', 'log10', 'exp',
        'sin', 'cos', 'tan',
        'int', 'float', 'str', 'bool',
    }

    # Allowed AST node types for safe evaluation
    # Note: Python 3.8+ uses ast.Constant for all literals
    _BASE_NODES = {
        # Expression types
        ast.Expression, ast.Expr,
        # Literals (Python 3.8+)
        ast.Constant,
        # Variables
        ast.Name,
        # Operators
        ast.UnaryOp, ast.UAdd, ast.USub, ast.Not, ast.Invert,
        ast.BinOp, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv,
        ast.Mod, ast.Pow, ast.BitAnd, ast.BitOr, ast.BitXor,
        ast.LShift, ast.RShift,
        # Comparisons
        ast.Compare, ast.Eq, ast.NotEq, ast.Lt, ast.LtE,
        ast.Gt, ast.GtE, ast.Is, ast.IsNot, ast.In, ast.NotIn,
        # Boolean operators
        ast.BoolOp, ast.And, ast.Or,
        # Control flow
        ast.IfExp,  # Ternary operator (x if condition else y)
        # Containers
        ast.Tuple, ast.List, ast.Set, ast.Dict,
        # Subscript (for dict/list access: obj[key])
        ast.Subscript,
        # Function calls (with validation)
        ast.Call,
    }

    # Add deprecated node types for backward compatibility
    ALLOWED_NODES = _BASE_NODES.copy()
    if hasattr(ast, 'Num'):
        ALLOWED_NODES.add(ast.Num)
    if hasattr(ast, 'Str'):
        ALLOWED_NODES.add(ast.Str)
    if hasattr(ast, 'Bytes'):
        ALLOWED_NODES.add(ast.Bytes)
    if hasattr(ast, 'NameConstant'):
        ALLOWED_NODES.add(ast.NameConstant)
    if hasattr(ast, 'Index'):
        ALLOWED_NODES.add(ast.Index)
    if hasattr(ast, 'Slice'):
        ALLOWED_NODES.add(ast.Slice)

    def __init__(self, allow_function_calls: bool = False):
        """
        Initialize the SafeEvaluator.

        Args:
            allow_function_calls: If True, allow calls to whitelisted safe functions
        """
        self._is_safe = True
        self._errors = []
        self._allow_function_calls = allow_function_calls

    def validate(self, expression: str) -> bool:
        """
        Validate an expression for safe evaluation.

        Args:
            expression: String expression to validate

        Returns:
            True if expression is safe, False otherwise

        Raises:
            SafeEvalError: If expression contains unsafe operations
        """
        self._is_safe = True
        self._errors = []

        try:
            # Parse the expression into an AST
            tree = ast.parse(expression, mode='eval')

            # Walk the AST and validate each node
            self.visit(tree)

            if not self._is_safe:
                raise SafeEvalError(f"Unsafe expression: {', '.join(self._errors)}")

            return True

        except SyntaxError as e:
            raise SafeEvalError(f"Syntax error in expression: {e}")
        except SafeEvalError:
            raise
        except Exception as e:
            raise SafeEvalError(f"Validation error: {e}")

    def visit_Call(self, node):
        """
        Validate a function call node.

        Only allow calls to whitelisted safe functions.
        """
        if not self._allow_function_calls:
            self._is_safe = False
            self._errors.append("Function calls are not allowed")
            logger.warning("SafeEval blocked: Function calls are not allowed")
            return

        # Check if the function being called is a whitelisted name
        func_name = None
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            # Block attribute access calls like obj.method()
            self._is_safe = False
            self._errors.append("Method calls (obj.attr()) are not allowed")
            logger.warning("SafeEval blocked: Method calls are not allowed")
            return

        if func_name and func_name not in self.SAFE_FUNCTIONS:
            self._is_safe = False
            self._errors.append(f"Function '{func_name}' is not in the safe whitelist")
            logger.warning(f"SafeEval blocked: Function '{func_name}' is not whitelisted")
            return

        # Continue validating the arguments
        for arg in node.args:
            self.visit(arg)

        # Validate keyword arguments
        for keyword in node.keywords:
            self.visit(keyword.value)

    def visit(self, node):
        """
        Visit an AST node and check if it's allowed.

        Raises SafeEvalError if node type is not allowed.
        """
        # Handle special case for Call nodes first
        if isinstance(node, ast.Call):
            self.visit_Call(node)
            return

        # Check if this node type is allowed
        node_type = type(node)

        if node_type not in self.ALLOWED_NODES:
            # Special case for ast.Load (ctx attribute)
            if node_type == ast.Load:
                return

            # Block dangerous node types
            self._is_safe = False

            # Get a human-readable name for the node type
            node_name = node_type.__name__
            error_msg = f"Disallowed operation: {node_name}"

            # Add specific error messages for common dangerous operations
            if node_type == ast.Attribute:
                error_msg = "Attribute access (obj.attr) is not allowed"
            elif node_type == ast.Lambda:
                error_msg = "Lambda expressions are not allowed"
            elif node_type == ast.Import:
                error_msg = "Import statements are not allowed"
            elif node_type == ast.ImportFrom:
                error_msg = "Import statements are not allowed"
            elif node_type == ast.ListComp:
                error_msg = "List comprehensions are not allowed"
            elif node_type == ast.DictComp:
                error_msg = "Dict comprehensions are not allowed"
            elif node_type == ast.SetComp:
                error_msg = "Set comprehensions are not allowed"
            elif node_type == ast.GeneratorExp:
                error_msg = "Generator expressions are not allowed"
            elif node_type == ast.Starred:
                error_msg = "Unpacking operations are not allowed"

            self._errors.append(error_msg)
            logger.warning(f"SafeEval blocked: {error_msg}")

        # Continue visiting child nodes
        self.generic_visit(node)

    def generic_visit(self, node):
        """Visit all child nodes."""
        for field, old_value in ast.iter_fields(node):
            if isinstance(old_value, list):
                for item in old_value:
                    if isinstance(item, ast.AST):
                        self.visit(item)
            elif isinstance(old_value, ast.AST):
                self.visit(old_value)


def safe_eval(expression: str, context: Optional[Dict[str, Any]] = None) -> Any:
    """
    Safely evaluate an expression with AST validation.

    This is a drop-in replacement for eval() that validates the AST
    before evaluation to prevent code injection attacks.

    Args:
        expression: String expression to evaluate
        context: Dictionary of variables available to the expression

    Returns:
        Result of evaluating the expression

    Raises:
        SafeEvalError: If expression contains unsafe operations

    Example:
        result = safe_eval("x + y", {"x": 1, "y": 2})
        # Returns: 3

        safe_eval("__import__('os').system('rm -rf /')", {})
        # Raises: SafeEvalError
    """
    if context is None:
        context = {}

    # Validate the expression AST (no function calls allowed by default)
    validator = SafeEvaluator(allow_function_calls=False)
    validator.validate(expression)

    # If validation passes, evaluate with restricted globals
    safe_globals = {"__builtins__": {}}

    # Add safe built-in functions
    safe_globals.update({
        "True": True,
        "False": False,
        "None": None,
        "true": True,
        "false": False,
        "null": None,
    })

    try:
        return eval(expression, safe_globals, context)
    except Exception as e:
        raise SafeEvalError(f"Evaluation failed: {e}")


def safe_eval_with_math(
    expression: str,
    inputs: Optional[Dict[str, Any]] = None
) -> Any:
    """
    Safely evaluate a mathematical expression with math functions.

    Includes safe math functions: sum, min, max, abs, round, sqrt, pow.

    Args:
        expression: String expression to evaluate
        inputs: Dictionary of variables available to the expression

    Returns:
        Result of evaluating the expression

    Raises:
        SafeEvalError: If expression contains unsafe operations
    """
    if inputs is None:
        inputs = {}

    # Validate the expression AST (allow whitelisted function calls)
    validator = SafeEvaluator(allow_function_calls=True)
    validator.validate(expression)

    # If validation passes, evaluate with restricted globals and math functions
    safe_globals = {"__builtins__": {}}

    # Add math functions
    import math
    safe_globals.update({
        "True": True,
        "False": False,
        "None": None,
        "sum": sum,
        "min": min,
        "max": max,
        "abs": abs,
        "round": round,
        "sqrt": math.sqrt,
        "pow": pow,
        "log": math.log,
        "log10": math.log10,
        "exp": math.exp,
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "pi": math.pi,
        "e": math.e,
    })

    try:
        return eval(expression, safe_globals, inputs)
    except Exception as e:
        raise SafeEvalError(f"Evaluation failed: {e}")
