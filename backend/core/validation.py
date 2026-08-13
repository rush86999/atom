"""
Centralized input validation and sanitization utilities.

All user input MUST pass through validation before:
- Database operations
- API responses
- Dynamic code execution
- External API calls
"""

import re
import html
import json
from typing import Any, Optional, Union, List, Dict
from pydantic import model_validator, ConfigDict
from pydantic import BaseModel as PydanticBaseModel

# Common injection patterns to detect
INJECTION_PATTERNS = [
    r'<script[^>]*>.*?</script>',  # Script tags
    r'javascript:',                # JavaScript protocol
    r'on\w+\s*=',                  # Event handlers (onclick, etc.)
    r'<iframe[^>]*>',              # Iframes
    r'<embed[^>]*>',               # Embed tags
    r'<object[^>]*>',              # Object tags
]

SQL_INJECTION_PATTERNS = [
    r"(''')",                      # SQL comment bypass
    r'--',                          # SQL comment
    # BUG 79-12: the alternation was uppercase (DROP|DELETE|...) but is matched
    # against a lowercased value — it could NEVER match, so statement-chained
    # injection like "x'; DROP TABLE t;" went undetected.
    r';\s*(drop|delete|exec|execute)',  # SQL commands after statement terminator
    r'union\s+select',             # SQL injection
]

PATH_TRAVERSAL_PATTERNS = [
    r'\.\./',                       # Parent directory traversal
    r'\.\./\.\./',                  # Double parent traversal
    r'%2e%2e%2f',                   # URL encoded parent traversal
]


class ValidationError(Exception):
    """Custom validation error with field context."""
    def __init__(self, message: str, field: str = None):
        self.message = message
        self.field = field
        super().__init__(f"{field}: {message}" if field else message)


def sanitize_string(
    value: str,
    max_length: int = 10000,
    allow_html: bool = False,
    strip_tags: bool = True
) -> str:
    """
    Sanitize string input to prevent XSS and injection attacks.

    Args:
        value: The string to sanitize
        max_length: Maximum allowed length (truncate if longer)
        allow_html: Whether to allow HTML tags (still sanitizes dangerous tags)
        strip_tags: Whether to strip all HTML tags

    Returns:
        Sanitized string
    """
    if not isinstance(value, str):
        raise ValidationError("Value must be a string", "value")

    # Truncate to max length
    if len(value) > max_length:
        value = value[:max_length]

    if not allow_html:
        # Remove HTML tags completely
        if strip_tags:
            value = re.sub(r'<[^>]+>', '', value)
        else:
            # Escape HTML entities
            value = html.escape(value)

    # Always escape dangerous patterns
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, value, re.IGNORECASE):
            # Don't fail, just remove the dangerous content
            value = re.sub(pattern, '', value, flags=re.IGNORECASE)

    # Remove null bytes
    value = value.replace('\x00', '')

    return value.strip()


def validate_html_content(content: str, allowed_tags: List[str] = None) -> str:
    """
    Validate and sanitize HTML content.

    Only allows specific safe HTML tags. Removes all others.

    Args:
        content: HTML content to validate
        allowed_tags: List of allowed tag names (defaults to safe tags only)

    Returns:
        Sanitized HTML string
    """
    if allowed_tags is None:
        allowed_tags = [
            'p', 'br', 'strong', 'em', 'u', 's', 'code', 'pre',
            'blockquote', 'ul', 'ol', 'li', 'a', 'h1', 'h2', 'h3',
            'h4', 'h5', 'h6', 'table', 'thead', 'tbody', 'tr', 'th',
            'td', 'div', 'span', 'b', 'i'
        ]

    # Remove script tags and their content
    content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.IGNORECASE | re.DOTALL)

    # Remove event handlers from all tags
    content = re.sub(r'\s+on\w+\s*=\s*["\'][^"\']*["\']', '', content, flags=re.IGNORECASE)

    # Remove javascript: protocol
    content = re.sub(r'javascript:', '', content, flags=re.IGNORECASE)

    # Remove iframe, embed, object tags
    for dangerous_tag in ['iframe', 'embed', 'object']:
        content = re.sub(rf'<{dangerous_tag}[^>]*>.*?</{dangerous_tag}>', '', content, flags=re.IGNORECASE | re.DOTALL)
        content = re.sub(rf'<{dangerous_tag}[^>]*/?>', '', content, flags=re.IGNORECASE)

    # Remove tags not in allowed list
    # BUG 79-8: the guard was `if allowed_tags:` — an EMPTY allowlist (allow
    # nothing) is falsy, so the filter was skipped and ALL tags survived.
    # Only None means "use the defaults".
    if allowed_tags is not None:
        tag_pattern = r'<(\/?)(\w+)(?:\s[^>]*)?(/?)>'
        def replace_tag(match):
            close, tag, self_close = match.groups()
            if tag.lower() in [t.lower() for t in allowed_tags]:
                return match.group(0)
            return ''
        content = re.sub(tag_pattern, replace_tag, content, flags=re.IGNORECASE)

    return content


def detect_sql_injection(value: str) -> bool:
    """
    Detect potential SQL injection patterns.

    Args:
        value: String to check

    Returns:
        True if SQL injection pattern detected
    """
    if not isinstance(value, str):
        return False

    value_lower = value.lower()

    for pattern in SQL_INJECTION_PATTERNS:
        if re.search(pattern, value_lower):
            return True

    return False


def detect_path_traversal(value: str) -> bool:
    """
    Detect potential path traversal patterns.

    Args:
        value: String to check

    Returns:
        True if path traversal pattern detected
    """
    if not isinstance(value, str):
        return False

    for pattern in PATH_TRAVERSAL_PATTERNS:
        if re.search(pattern, value, re.IGNORECASE):
            return True

    return False


def validate_json_schema(data: Any, schema: Dict[str, Any]) -> bool:
    """
    Validate data against a JSON schema.

    Simple schema validation. For complex validation, use jsonschema library.

    Args:
        data: Data to validate
        schema: Schema definition with keys: required, type, min_length, max_length, pattern

    Returns:
        True if valid, raises ValidationError otherwise
    """
    if not isinstance(data, dict):
        raise ValidationError("Data must be a dictionary", "data")

    # Check required fields
    required = schema.get('required', [])
    for field in required:
        if field not in data:
            raise ValidationError(f"Required field '{field}' is missing", field)

    # Validate each field
    for field, rules in schema.get('properties', {}).items():
        if field not in data:
            continue

        value = data[field]

        # Type validation
        expected_type = rules.get('type')
        if expected_type:
            if expected_type == 'string' and not isinstance(value, str):
                raise ValidationError(f"Field '{field}' must be a string", field)
            elif expected_type == 'integer' and not isinstance(value, int):
                raise ValidationError(f"Field '{field}' must be an integer", field)
            elif expected_type == 'number' and not isinstance(value, (int, float)):
                raise ValidationError(f"Field '{field}' must be a number", field)
            elif expected_type == 'boolean' and not isinstance(value, bool):
                raise ValidationError(f"Field '{field}' must be a boolean", field)
            elif expected_type == 'array' and not isinstance(value, list):
                raise ValidationError(f"Field '{field}' must be an array", field)

        # String validations
        if isinstance(value, str):
            min_length = rules.get('min_length')
            max_length = rules.get('max_length')
            pattern = rules.get('pattern')

            if min_length and len(value) < min_length:
                raise ValidationError(
                    f"Field '{field}' must be at least {min_length} characters",
                    field
                )

            if max_length and len(value) > max_length:
                raise ValidationError(
                    f"Field '{field}' must be at most {max_length} characters",
                    field
                )

            if pattern and not re.match(pattern, value):
                raise ValidationError(
                    f"Field '{field}' does not match required pattern",
                    field
                )

    return True


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename to prevent path traversal and invalid characters.

    Args:
        filename: The filename to sanitize

    Returns:
        Safe filename
    """
    if not isinstance(filename, str):
        raise ValidationError("Filename must be a string", "filename")

    # Remove path components
    filename = filename.replace('\\', '/').split('/')[-1]

    # Remove dangerous characters
    filename = re.sub(r'[<>:"|?*\x00-\x1f]', '', filename)

    # Limit length
    if len(filename) > 255:
        name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
        filename = name[:250] + ('.' + ext if ext else '')

    return filename.strip()


class BaseModel(PydanticBaseModel):
    """
    Base Pydantic model with automatic validation.

    All API request models should inherit from this class.
    """

    model_config = ConfigDict(
        # Validate assignment to catch errors at assignment time
        validate_assignment=True,
        # Use enum values (not just enum objects)
        use_enum_values=True,
        # Extra fields are forbidden (catch typos)
        extra='forbid'
    )

    @model_validator(mode='before')
    @classmethod
    def validate_strings(cls, data: Any) -> Any:
        """Validate and sanitize all string fields."""
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, str):
                    # Check for SQL injection
                    if detect_sql_injection(value):
                        raise ValidationError(f"SQL injection detected in field '{key}'", key)
                    # Check for path traversal in file-related fields
                    if 'file' in key.lower() or 'path' in key.lower():
                        if detect_path_traversal(value):
                            raise ValidationError(f"Path traversal detected in field '{key}'", key)
        return data


# Common validators for use in Pydantic models
def validated_string(
    max_length: int = 1000,
    min_length: int = 0,
    pattern: Optional[str] = None,
    sanitize: bool = True
):
    """
    Create a Pydantic string field type with length/pattern/sanitize rules.

    BUG 79-9: this previously used a nested ``@field_validator(mode='before')
    @classmethod`` inside the factory — pydantic raised
    ``TypeError: field_validator() missing 1 required positional argument:
    'field'`` at class-definition time, so the helper was unusable. Rewritten
    as pydantic v2 ``Annotated[str, AfterValidator(...)]`` metadata:

    Usage:
        class Model(BaseModel):
            code: validated_string(min_length=2, max_length=5, pattern=r'^[a-z]+$')

    Args:
        max_length: Maximum allowed length (truncated, like before)
        min_length: Minimum allowed length
        pattern: Regex pattern the string must match
        sanitize: Whether to sanitize the string

    Returns:
        Annotated[str, AfterValidator] type usable as a field annotation
    """
    from typing import Annotated
    from pydantic import AfterValidator

    def _check(v: Any) -> str:
        # Defensive: the Annotated[str, ...] annotation means pydantic already
        # enforces str (and coerces non-str in lax mode), so this branch is
        # unreachable through normal model validation.
        if not isinstance(v, str):  # pragma: no cover - defensive
            raise ValueError('Must be a string')

        if len(v) < min_length:
            raise ValueError(f'Must be at least {min_length} characters')

        if len(v) > max_length:
            v = v[:max_length]

        if pattern and not re.match(pattern, v):
            raise ValueError(f'Does not match required pattern')

        if sanitize:
            v = sanitize_string(v, max_length=max_length)

        return v

    return Annotated[str, AfterValidator(_check)]
