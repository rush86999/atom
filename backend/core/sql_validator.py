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
        # NOTE: sqlparse tokenizes DML verbs (SELECT/INSERT/UPDATE/DELETE) as
        # Token.Keyword.DML, a *subtype* of Token.Keyword. The `is` identity
        # check does not match subtypes, so we use `in` (membership) instead.
        # With `is`, the SELECT-list was never parsed and validate_sql_against_schema
        # silently approved queries referencing non-existent fields.
        if any(t.ttype in sqlparse.tokens.Keyword and t.value.upper() == 'SELECT'
               for t in parsed_sql.tokens):
            select_tokens = []
            in_select = False
            for t in parsed_sql.flatten():
                if t.ttype in sqlparse.tokens.Keyword and t.value.upper() == 'FROM':
                    break
                if in_select:
                    select_tokens.append(t)
                if t.ttype in sqlparse.tokens.Keyword and t.value.upper() == 'SELECT':
                    in_select = True
            column_str = ' '.join(str(t) for t in select_tokens)
            columns.update(self._parse_column_list(column_str))
        columns.update(self._extract_where_columns(parsed_sql))
        columns.update(self._extract_order_group_columns(parsed_sql))
        return columns

    def _parse_column_list(self, column_str: str) -> Set[str]:
        columns = set()
        if column_str.strip() == '*':
            return columns
        for col in column_str.split(','):
            col = col.strip()
            if '.' in col: col = col.split('.')[-1]
            if '(' in col:
                # W88: sqlparse joins tokens with spaces, so `COUNT(bogus)`
                # arrives as "COUNT ( bogus )" — the regex must tolerate
                # whitespace after the paren or the argument is silently
                # dropped and unknown columns are approved.
                arg_match = re.search(r'\(\s*(\w+)', col)
                if arg_match: col = arg_match.group(1)
                else: continue
            col = col.strip().strip('"').strip("'").strip('`')
            if col and col.isidentifier(): columns.add(col)
        return columns

    def _extract_where_columns(self, parsed_sql: sqlparse.sql.Statement) -> Set[str]:
        columns = set()
        in_where = False
        tokens = list(parsed_sql.flatten())
        for i, token in enumerate(tokens):
            token_str = str(token).strip()
            if token.ttype is sqlparse.tokens.Keyword and token_str.upper() == 'WHERE':
                in_where = True
                continue
            elif token.ttype is sqlparse.tokens.Keyword and token_str.upper() in ('GROUP', 'ORDER', 'LIMIT', 'OFFSET', 'HAVING'):
                in_where = False
                continue
            if in_where and token.ttype is sqlparse.tokens.Name:
                # W88: table-qualified columns (`WHERE u.status = 'x'`) emit
                # the alias `u` as a Name token — previously treated as a
                # column and rejected as non-existent. Skip aliases (Name
                # directly followed by a `.` punctuation token).
                if i + 1 < len(tokens) and str(tokens[i + 1]).strip() == '.':
                    continue
                col = token_str.strip().strip('"').strip("'").strip('`')
                if col and col.isidentifier(): columns.add(col)
        return columns

    def _extract_order_group_columns(self, parsed_sql: sqlparse.sql.Statement) -> Set[str]:
        # W88: ORDER BY / GROUP BY column references were never validated —
        # queries referencing non-existent fields in those clauses were
        # silently approved (same bug class as the SELECT-list gap fixed in
        # BUG-080). Collect Name tokens inside ORDER BY / GROUP BY clauses.
        columns = set()
        tokens = list(parsed_sql.flatten())
        for i, token in enumerate(tokens):
            tok_str = str(token).strip().upper()
            # sqlparse emits ORDER BY / GROUP BY as a single Keyword token
            # ("ORDER BY") — accept both that combined form and the split
            # form (ORDER + BY) for robustness.
            is_clause_start = (tok_str in ('ORDER BY', 'GROUP BY')
                               or (tok_str in ('ORDER', 'GROUP')
                                   and i + 1 < len(tokens)
                                   and str(tokens[i + 1]).strip().upper() == 'BY'))
            if token.ttype in sqlparse.tokens.Keyword and is_clause_start:
                for j in range(i + 2, len(tokens)):
                    nt = tokens[j]
                    nt_str = str(nt).strip()
                    if nt.ttype in sqlparse.tokens.Keyword:
                        # ASC/DESC sort directions (and the `,` separators
                        # below) keep the clause open so multi-column ORDER BY
                        # (e.g. `ORDER BY name ASC, ghost DESC`) is fully
                        # validated; any other keyword closes it.
                        if nt_str.upper() in ('ASC', 'DESC'):
                            continue
                        break
                    if nt.ttype is sqlparse.tokens.Name:
                        col = nt_str.strip().strip('"').strip("'").strip('`')
                        if col and col.isidentifier():
                            columns.add(col)
                    elif nt.ttype is sqlparse.tokens.Punctuation:
                        if nt_str != ',':
                            break
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
        # BUG-080: The old regex only matched specific verbs after `;`, allowing
        # stacked SELECT exfiltration (`SELECT 1; SELECT password FROM secrets`).
        # Now blocks ANY semicolon that separates multiple statements.
        'sql_injection_semicolon': re.compile(r';', re.I),
        'sql_comment_dash': re.compile(r'--.*', re.M),
        # MySQL / MariaDB line comment. Previously only -- and /* */ were
        # stripped, so `#` could truncate a query and hide an injection
        # (e.g. ``username='admin'#`` auth bypass, or ``... # UNION SELECT``).
        'sql_comment_hash': re.compile(r'#.*', re.M),
        'sql_comment_block': re.compile(r'/\*.*?\*/', re.S),
        'union_based_injection': re.compile(r'\bUNION\s+(?:ALL\s+)?SELECT\b', re.I),
        # W88: server-side file write/read exfiltration sinks. SELECT ... INTO
        # OUTFILE/DUMPFILE writes query results to a web-reachable file
        # (attacker fetches them later); LOAD_FILE() reads server files into
        # query results. Both previously passed sanitization.
        'into_outfile': re.compile(r'\bINTO\s+(?:OUTFILE|DUMPFILE)\b', re.I),
        'load_file': re.compile(r'\bLOAD_FILE\s*\(', re.I),
        # W88: metadata-schema probing (sqlite_master / information_schema /
        # pg_catalog). Table enumeration feeds column discovery, which turns a
        # schema-valid SELECT into a broad exfiltration campaign.
        'sqlite_meta_table': re.compile(r'\b(?:sqlite_(?:master|temp_master|schema|sequence))\b', re.I),
        'sql_meta_schema': re.compile(r'\b(?:information_schema|pg_catalog|mysql)\b', re.I),
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
