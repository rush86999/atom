"""
SQL Validator and Sanitizer for Entity Query Service.

Provides security validation for generated SQL queries:
- SQLValidator: Validates SQL against entity JSON schemas
- SQLSanitizer: Blocks dangerous operations (DROP, DELETE without WHERE, injection)
"""
import logging
import re
import sqlparse
from typing import Dict, Any, Set, List

logger = logging.getLogger(__name__)


class SecurityError(Exception):
    """Exception raised when SQL sanitization detects a security violation."""
    def __init__(self, message: str, blocked_content: str = None):
        self.message = message
        self.blocked_content = blocked_content
        super().__init__(self.message)


class SQLValidator:
    """Validates SQL queries against entity JSON schemas."""

    SYSTEM_FIELDS = {'id', 'workspace_id', 'created_at', 'updated_at'}

    def validate_sql_against_schema(
        self,
        sql_query: str,
        json_schema: Dict[str, Any]
    ) -> bool:
        """Validate SQL query against entity JSON schema."""
        if not sql_query or not sql_query.strip():
            raise ValueError("Empty SQL query")

        if not json_schema or 'properties' not in json_schema:
            raise ValueError("Invalid JSON schema: missing 'properties' key")

        schema_fields = set(json_schema['properties'].keys())
        allowed_fields = schema_fields | self.SYSTEM_FIELDS

        try:
            parsed = sqlparse.parse(sql_query)[0]
        except Exception as e:
            raise ValueError(f"Failed to parse SQL: {e}")

        referenced_fields = self._extract_column_references(parsed)
        invalid_fields = referenced_fields - allowed_fields

        if invalid_fields:
            raise ValueError(f"SQL references non-existent fields: {', '.join(sorted(invalid_fields))}")

        return True

    def _extract_column_references(self, parsed_sql: sqlparse.sql.Statement) -> Set[str]:
        columns = set()
        for token in parsed_sql.tokens:
            if token.ttype is sqlparse.tokens.Keyword and token.value.upper() == 'SELECT':
                select_tokens = []
                in_select = False
                for t in parsed_sql.flatten():
                    if t.ttype is sqlparse.tokens.Keyword and t.value.upper() == 'FROM':
                        break
                    if in_select:
                        select_tokens.append(t)
                    if t.ttype is sqlparse.tokens.Keyword and t.value.upper() == 'SELECT':
                        in_select = True
                column_str = ' '.join(str(t) for t in select_tokens)
                columns.update(self._parse_column_list(column_str))
                break
        columns.update(self._extract_where_columns(parsed_sql))
        return columns

    def _parse_column_list(self, column_str: str) -> Set[str]:
        columns = set()
        if column_str.strip() == '*':
            return columns
        for col in column_str.split(','):
            col = col.strip()
            if '.' in col: col = col.split('.')[-1]
            if '(' in col:
                arg_match = re.search(r'\((\w+)', col)
                if arg_match: col = arg_match.group(1)
                else: continue
            col = col.strip().strip('"').strip("'").strip('`')
            if col and col.isidentifier(): columns.add(col)
        return columns

    def _extract_where_columns(self, parsed_sql: sqlparse.sql.Statement) -> Set[str]:
        columns = set()
        in_where = False
        for token in parsed_sql.flatten():
            token_str = str(token).strip()
            if token.ttype is sqlparse.tokens.Keyword and token_str.upper() == 'WHERE':
                in_where = True
                continue
            elif token.ttype is sqlparse.tokens.Keyword and token_str.upper() in ('GROUP', 'ORDER', 'LIMIT', 'OFFSET', 'HAVING'):
                in_where = False
                continue
            if in_where and token.ttype is sqlparse.tokens.Name:
                col = token_str.strip().strip('"').strip("'").strip('`')
                if col and col.isidentifier(): columns.add(col)
        return columns


class SQLSanitizer:
    """Sanitizes SQL queries to block dangerous operations."""

    DANGEROUS_KEYWORDS = {
        'DROP', 'TRUNCATE', 'ALTER', 'CREATE', 'GRANT', 'REVOKE',
        'INSERT', 'UPDATE', 'DELETE'
    }

    DANGEROUS_PATTERNS = {
        'delete_without_where': re.compile(r'^\s*DELETE\s+FROM\s+\w+\s*(?:;|$)', re.I | re.M),
        'update_without_where': re.compile(r'^\s*UPDATE\s+\w+\s+SET\s+[\w\s]+\s*(?:;|$)', re.I | re.M),
        'sql_injection_semicolon': re.compile(r';\s*(?:DROP|DELETE|UPDATE|INSERT|ALTER|CREATE)', re.I),
        'sql_comment_dash': re.compile(r'--.*', re.M),
        'sql_comment_block': re.compile(r'/\*.*?\*/', re.S),
        'union_based_injection': re.compile(r'\bUNION\s+(?:ALL\s+)?SELECT\b', re.I),
    }

    def sanitize_sql(self, sql_query: str) -> bool:
        """Sanitize SQL query."""
        if not sql_query or not sql_query.strip():
            raise SecurityError("Empty SQL query")

        sql_upper = sql_query.upper().strip()

        for keyword in self.DANGEROUS_KEYWORDS:
            if re.search(rf'\b{keyword}\b', sql_upper):
                raise SecurityError(f"Dangerous SQL keyword detected: {keyword}")

        for pattern_name, pattern in self.DANGEROUS_PATTERNS.items():
            match = pattern.search(sql_query)
            if match:
                raise SecurityError(f"Dangerous SQL pattern detected: {pattern_name}")

        if not sql_upper.startswith('SELECT'):
            raise SecurityError("Only SELECT queries are allowed.")

        return True
