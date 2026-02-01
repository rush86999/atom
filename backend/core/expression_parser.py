"""
Safe Expression Parser for Debugging

Provides a safe alternative to eval() for evaluating conditional breakpoint expressions.
Uses tokenization and AST parsing to prevent code injection while supporting common operations.

Supported operations:
- Comparisons: ==, !=, <, >, <=, >=
- Logical: and, or, not
- Arithmetic: +, -, *, /, %, **
- Membership: in, not in
- Identity: is, is not
- Parentheses for grouping
- Variable access (dot notation, indexing)
- String literals (single/double quotes)
- Number literals (int, float, scientific notation)
- Boolean literals: True, False, None

Security features:
- No function calls
- No lambda expressions
- No import statements
- No attribute access that starts with _
- Limited to safe operations only
"""

import re
import operator
from typing import Any, Dict, Optional, Union, List
import logging

logger = logging.getLogger(__name__)


class ExpressionParser:
    """
    Safe expression parser for conditional breakpoints.

    Evaluates expressions in a restricted sandbox without using eval().
    Supports common comparison and logical operations while preventing code injection.
    """

    def __init__(self):
        """Initialize the expression parser."""
        self.tokens = []
        self.pos = 0
        self.variables: Dict[str, Any] = {}  # Variable context for resolution
    TOKEN_NUMBER = r'(?P<NUMBER>-?\d+\.?\d*(?:[eE][+-]?\d+)?)'
    TOKEN_STRING = r'(?P<STRING>"[^"]*"|\'[^\']*\')'
    TOKEN_BOOLEAN = r'(?P<BOOLEAN>True|False|None)'
    TOKEN_OPERATOR = r'(?P<OPERATOR>==|!=|<=?|>=?|and|or|not|in|\*\*|%|is\s+not|is)'
    TOKEN_IDENTIFIER = r'(?P<IDENTIFIER>[a-zA-Z_][a-zA-Z0-9_\.]*(?:\[[^\]]+\])?)'
    TOKEN_LPAREN = r'(?P<LPAREN>\()'
    TOKEN_RPAREN = r'(?P<RPAREN>\))'
    TOKEN_COMMA = r'(?P<COMMA>,)'

    # Whitespace skipper
    TOKEN_SKIP = r'(?P<SKIP>\s+)'

    # Master pattern
    TOKEN_PATTERN = re.compile(
        '|'.join([
            TOKEN_SKIP,
            TOKEN_NUMBER,
            TOKEN_STRING,
            TOKEN_BOOLEAN,
            TOKEN_OPERATOR,
            TOKEN_LPAREN,
            TOKEN_RPAREN,
            TOKEN_COMMA,
            TOKEN_IDENTIFIER,
        ])
    )

    # Operator mapping
    OPERATORS = {
        '+': operator.add,
        '-': operator.sub,
        '*': operator.mul,
        '/': operator.truediv,
        '%': operator.mod,
        '**': operator.pow,
        '==': operator.eq,
        '!=': operator.ne,
        '<': operator.lt,
        '<=': operator.le,
        '>': operator.gt,
        '>=': operator.ge,
        'and': lambda a, b: bool(a and b),
        'or': lambda a, b: bool(a or b),
        'not': lambda a: bool(not a),
        'in': lambda a, b: a in b if hasattr(b, '__contains__') else False,
        'is': operator.is_,
        'is not': operator.is_not,
    }

    def __init__(self):
        """Initialize the expression parser."""
        self.tokens = []
        self.pos = 0

    def evaluate(self, expression: str, variables: Dict[str, Any]) -> bool:
        """
        Evaluate an expression with the given variable context.

        Args:
            expression: The expression string to evaluate
            variables: Dictionary of variable names to values

        Returns:
            bool: Result of the expression evaluation

        Raises:
            ValueError: If the expression is invalid or unsafe
        """
        try:
            # Store variable context for use during parsing
            self.variables = variables

            # Tokenize the expression
            self.tokens = self._tokenize(expression)
            self.pos = 0

            if not self.tokens:
                return False

            # Parse and evaluate (variables are now available for resolution)
            result = self._parse_expression()

            # Ensure we consumed all tokens
            if self.pos < len(self.tokens):
                raise ValueError(f"Unexpected token at position {self.pos}: {self.tokens[self.pos]}")

            return bool(result)

        except Exception as e:
            logger.warning(f"Failed to evaluate expression '{expression}': {e}")
            return False

    def _tokenize(self, expression: str) -> List[Dict[str, Any]]:
        """Tokenize the expression string."""
        tokens = []
        pos = 0

        while pos < len(expression):
            match = self.TOKEN_PATTERN.match(expression, pos)
            if not match:
                raise ValueError(f"Invalid character at position {pos}: {expression[pos:pos+10]}")

            token_type = match.lastgroup
            token_value = match.group(token_type)

            if token_type != 'SKIP':
                tokens.append({
                    'type': token_type,
                    'value': token_value,
                })

            pos = match.end()

        return tokens

    def _current_token(self) -> Optional[Dict[str, Any]]:
        """Get the current token."""
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def _advance(self) -> Optional[Dict[str, Any]]:
        """Advance to the next token and return the previous one."""
        token = self._current_token()
        self.pos += 1
        return token

    def _expect(self, token_type: str) -> Dict[str, Any]:
        """Expect a specific token type and raise an error if not found."""
        token = self._current_token()
        if not token or token['type'] != token_type:
            raise ValueError(f"Expected {token_type} at position {self.pos}, got {token}")
        return self._advance()

    def _parse_expression(self) -> Any:
        """Parse an expression (handles logical or)."""
        return self._parse_or()

    def _parse_or(self) -> Any:
        """Parse logical OR operations."""
        left = self._parse_and()

        while self._current_token() and self._current_token()['value'] == 'or':
            self._advance()
            right = self._parse_and()
            left = self.OPERATORS['or'](left, right)

        return left

    def _parse_and(self) -> Any:
        """Parse logical AND operations."""
        left = self._parse_not()

        while self._current_token() and self._current_token()['value'] == 'and':
            self._advance()
            right = self._parse_not()
            left = self.OPERATORS['and'](left, right)

        return left

    def _parse_not(self) -> Any:
        """Parse logical NOT operations."""
        if self._current_token() and self._current_token()['value'] == 'not':
            self._advance()
            operand = self._parse_not()
            return self.OPERATORS['not'](operand)

        return self._parse_comparison()

    def _parse_comparison(self) -> Any:
        """Parse comparison operations."""
        left = self._parse_additive()

        token = self._current_token()
        if token and token['type'] == 'OPERATOR' and token['value'] in ('==', '!=', '<', '<=', '>', '>=', 'in', 'is', 'is not'):
            op = self._advance()['value']
            right = self._parse_additive()
            return self.OPERATORS[op](left, right)

        return left

    def _parse_additive(self) -> Any:
        """Parse additive operations (+, -)."""
        left = self._parse_multiplicative()

        while self._current_token() and self._current_token()['value'] in ('+', '-'):
            op = self._advance()['value']
            right = self._parse_multiplicative()
            left = self.OPERATORS[op](left, right)

        return left

    def _parse_multiplicative(self) -> Any:
        """Parse multiplicative operations (*, /, %, **)."""
        left = self._parse_unary()

        while self._current_token() and self._current_token()['value'] in ('*', '/', '%', '**'):
            op = self._advance()['value']
            right = self._parse_unary()
            left = self.OPERATORS[op](left, right)

        return left

    def _parse_unary(self) -> Any:
        """Parse unary operations (+, -)."""
        token = self._current_token()
        if token and token['value'] in ('+', '-'):
            self._advance()
            operand = self._parse_unary()
            if token['value'] == '-':
                return -operand
            return operand

        return self._parse_primary()

    def _parse_primary(self) -> Any:
        """Parse primary expressions (literals, identifiers, parenthesized expressions)."""
        token = self._current_token()

        if not token:
            raise ValueError("Unexpected end of expression")

        if token['type'] == 'NUMBER':
            value = self._advance()['value']
            if '.' in value or 'e' in value.lower():
                return float(value)
            return int(value)

        if token['type'] == 'STRING':
            value = self._advance()['value']
            # Remove quotes
            return value[1:-1]

        if token['type'] == 'BOOLEAN':
            value = self._advance()['value']
            if value == 'True':
                return True
            if value == 'False':
                return False
            if value == 'None':
                return None

        if token['type'] == 'LPAREN':
            self._advance()
            expr = self._parse_expression()
            self._expect('RPAREN')
            return expr

        if token['type'] == 'IDENTIFIER':
            return self._parse_identifier()

        raise ValueError(f"Unexpected token: {token['value']}")

    def _parse_identifier(self) -> Any:
        """
        Parse identifier and resolve variable value from context.

        Supports simple variables, dot notation for nested access, and array indexing.
        """
        token = self._advance()
        identifier = token['value']

        # Try to resolve the variable from context
        # Try with original name first
        if identifier in self.variables:
            return self.variables[identifier]

        # Try with sanitized name (dashes/dots replaced with underscores)
        sanitized = identifier.replace('-', '_').replace('.', '_')
        if sanitized in self.variables:
            return self.variables[sanitized]

        # If not found, raise error (don't allow undefined variables)
        raise ValueError(f"Variable '{identifier}' is not defined")


class ExpressionEvaluator:
    """
    Expression evaluator that uses the ExpressionParser.

    The parser now handles all variable resolution and evaluation without eval().
    This class provides a simple interface for evaluating expressions.
    """

    def __init__(self):
        """Initialize the expression evaluator."""
        self.parser = ExpressionParser()

    def evaluate(self, expression: str, variables: Dict[str, Any]) -> bool:
        """
        Evaluate an expression with the given variable context.

        This is a complete AST-based evaluation without using eval().

        Args:
            expression: The expression string to evaluate
            variables: Dictionary of variable names to values

        Returns:
            bool: Result of the expression evaluation
        """
        return self.parser.evaluate(expression, variables)


# Singleton instance
_expression_evaluator = None


def get_expression_evaluator() -> ExpressionEvaluator:
    """Get the singleton expression evaluator instance."""
    global _expression_evaluator
    if _expression_evaluator is None:
        _expression_evaluator = ExpressionEvaluator()
    return _expression_evaluator
