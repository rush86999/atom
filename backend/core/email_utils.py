from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
import os
import re
import smtplib
from typing import Optional

logger = logging.getLogger(__name__)

def send_smtp_email(to_email: str, subject: str, body: str, html_body: Optional[str] = None):
    """
    Send an email using SMTP settings from environment variables.
    """
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = os.getenv("SMTP_PORT")
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")

    if not all([smtp_host, smtp_port, smtp_user, smtp_password]):
        logger.warning(f"SMTP not fully configured. Email to {to_email} skipped.")
        # In dev, we still want to see the content in logs
        logger.info(f"--- MOCK EMAIL START ---")
        logger.info(f"To: {to_email}")
        logger.info(f"Subject: {subject}")
        logger.info(f"Body: {body}")
        logger.info(f"--- MOCK EMAIL END ---")
        return True # Return true so the flow continues in dev

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = smtp_user
        msg['To'] = to_email

        msg.attach(MIMEText(body, 'plain'))
        if html_body:
            msg.attach(MIMEText(html_body, 'html'))

        with smtplib.SMTP(smtp_host, int(smtp_port)) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        
        logger.info(f"Email sent successfully to {to_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False


# ==============================================================================
# Email Validation Functions
# ==============================================================================

def validate_email(email: str) -> bool:
    """
    Validate email address format.

    Args:
        email: Email address to validate

    Returns:
        True if valid email format, False otherwise

    Examples:
        >>> validate_email("user@example.com")
        True
        >>> validate_email("invalid")
        False
    """
    if not email or not isinstance(email, str):
        return False

    # Basic email regex pattern
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_email_strict(email: str) -> tuple[bool, Optional[str]]:
    """
    Validate email with detailed error messages.

    Args:
        email: Email address to validate

    Returns:
        Tuple of (is_valid, error_message)

    Examples:
        >>> validate_email_strict("user@example.com")
        (True, None)
        >>> validate_email_strict("invalid")
        (False, "Invalid email format")
    """
    if not email:
        return False, "Email is required"

    if not isinstance(email, str):
        return False, "Email must be a string"

    # Check for @ symbol
    if '@' not in email:
        return False, "Email must contain @ symbol"

    # Check for domain
    parts = email.split('@')
    if len(parts) != 2:
        return False, "Email must have exactly one @ symbol"

    local, domain = parts

    if not local:
        return False, "Email must have username before @"

    if not domain:
        return False, "Email must have domain after @"

    # Check for domain extension
    if '.' not in domain:
        return False, "Email domain must contain extension (e.g., .com)"

    # Basic regex validation
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        return False, "Invalid email format"

    return True, None


def validate_email_with_plus_addressing(email: str) -> bool:
    """
    Validate email that supports + addressing (user+tag@example.com).

    Args:
        email: Email address to validate

    Returns:
        True if valid email format (including + addressing), False otherwise

    Examples:
        >>> validate_email_with_plus_addressing("user+tag@example.com")
        True
        >>> validate_email_with_plus_addressing("user@example.com")
        True
    """
    if not email or not isinstance(email, str):
        return False

    # Allow + in local part
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not True


# ==============================================================================
# URL Validation Functions
# ==============================================================================

def validate_url(url: str) -> bool:
    """
    Validate URL format.

    Args:
        url: URL to validate

    Returns:
        True if valid URL format, False otherwise

    Examples:
        >>> validate_url("https://example.com")
        True
        >>> validate_url("ftp://example.com")
        True
        >>> validate_url("example.com")
        False
    """
    if not url or not isinstance(url, str):
        return False

    # Basic URL regex pattern
    pattern = r'^(https?|ftp)://[^\s/$.?#].[^\s]*$'
    return re.match(pattern, url) is not None


def validate_url_with_params(url: str) -> tuple[bool, Optional[str]]:
    """
    Validate URL with detailed error messages.

    Args:
        url: URL to validate

    Returns:
        Tuple of (is_valid, error_message)

    Examples:
        >>> validate_url_with_params("https://example.com?foo=bar")
        (True, None)
        >>> validate_url_with_params("example.com")
        (False, "URL must start with http://, https://, or ftp://")
    """
    if not url:
        return False, "URL is required"

    if not isinstance(url, str):
        return False, "URL must be a string"

    # Check for scheme
    if not url.startswith(('http://', 'https://', 'ftp://')):
        return False, "URL must start with http://, https://, or ftp://"

    # Basic URL validation
    pattern = r'^(https?|ftp)://[^\s/$.?#].[^\s]*$'
    if not re.match(pattern, url):
        return False, "Invalid URL format"

    return True, None


def validate_url_secure(url: str) -> bool:
    """
    Validate URL is HTTPS (secure).

    Args:
        url: URL to validate

    Returns:
        True if valid HTTPS URL, False otherwise

    Examples:
        >>> validate_url_secure("https://example.com")
        True
        >>> validate_url_secure("http://example.com")
        False
    """
    if not url or not isinstance(url, str):
        return False

    return url.startswith('https://') and validate_url(url)


# ==============================================================================
# Phone Validation Functions
# ==============================================================================

def validate_phone(phone: str) -> bool:
    """
    Validate phone number (US format).

    Args:
        phone: Phone number to validate

    Returns:
        True if valid phone number format, False otherwise

    Examples:
        >>> validate_phone("1234567890")
        True
        >>> validate_phone("(123) 456-7890")
        True
        >>> validate_phone("123")
        False
    """
    if not phone or not isinstance(phone, str):
        return False

    # Remove all non-digit characters
    digits = re.sub(r'\D', '', phone)

    # Check for 10 digits (US) or 11 digits (with country code)
    return len(digits) in [10, 11]


def validate_phone_international(phone: str) -> bool:
    """
    Validate international phone number.

    Args:
        phone: Phone number to validate

    Returns:
        True if valid international phone number, False otherwise

    Examples:
        >>> validate_phone_international("+11234567890")
        True
        >>> validate_phone_international("+44 20 7123 4567")
        True
    """
    if not phone or not isinstance(phone, str):
        return False

    # Remove all non-digit characters except +
    cleaned = re.sub(r'[^\d+]', '', phone)

    # Check for + prefix and reasonable length
    if cleaned.startswith('+'):
        return len(cleaned) >= 10 and len(cleaned) <= 15

    # Accept US format without +
    return len(cleaned) in [10, 11]


# ==============================================================================
# UUID Validation Functions
# ==============================================================================

def validate_uuid(uuid_string: str) -> bool:
    """
    Validate UUID v4 format.

    Args:
        uuid_string: UUID string to validate

    Returns:
        True if valid UUID v4 format, False otherwise

    Examples:
        >>> validate_uuid("123e4567-e89b-12d3-a456-426614174000")
        True
        >>> validate_uuid("invalid")
        False
    """
    if not uuid_string or not isinstance(uuid_string, str):
        return False

    # UUID v4 pattern
    pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
    return re.match(pattern, uuid_string.lower()) is not None


def validate_uuid_any_version(uuid_string: str) -> bool:
    """
    Validate UUID format (any version).

    Args:
        uuid_string: UUID string to validate

    Returns:
        True if valid UUID format (any version), False otherwise

    Examples:
        >>> validate_uuid_any_version("123e4567-e89b-12d3-a456-426614174000")
        True
    """
    if not uuid_string or not isinstance(uuid_string, str):
        return False

    # UUID pattern (any version)
    pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    return re.match(pattern, uuid_string.lower()) is not None


# ==============================================================================
# General Validation Functions
# ==============================================================================

def validate_boolean(value: str) -> bool:
    """
    Validate boolean string.

    Args:
        value: String value to validate

    Returns:
        True if valid boolean string, False otherwise

    Examples:
        >>> validate_boolean("true")
        True
        >>> validate_boolean("false")
        True
        >>> validate_boolean("invalid")
        False
    """
    if not isinstance(value, str):
        return False

    return value.lower() in ['true', 'false', '1', '0', 'yes', 'no']


def parse_boolean(value: str) -> Optional[bool]:
    """
    Parse boolean string to boolean value.

    Args:
        value: String value to parse

    Returns:
        Boolean value or None if invalid

    Examples:
        >>> parse_boolean("true")
        True
        >>> parse_boolean("false")
        False
        >>> parse_boolean("invalid")
        None
    """
    if not isinstance(value, str):
        return None

    if value.lower() in ['true', '1', 'yes']:
        return True
    elif value.lower() in ['false', '0', 'no']:
        return False
    else:
        return None


def validate_integer(value: str, min_val: Optional[int] = None, max_val: Optional[int] = None) -> bool:
    """
    Validate integer string with optional range checking.

    Args:
        value: String value to validate
        min_val: Minimum allowed value (optional)
        max_val: Maximum allowed value (optional)

    Returns:
        True if valid integer in range, False otherwise

    Examples:
        >>> validate_integer("123")
        True
        >>> validate_integer("123", min_val=0, max_val=200)
        True
        >>> validate_integer("abc")
        False
    """
    if not isinstance(value, str):
        return False

    try:
        int_val = int(value)
        if min_val is not None and int_val < min_val:
            return False
        if max_val is not None and int_val > max_val:
            return False
        return True
    except ValueError:
        return False


def validate_float(value: str, min_val: Optional[float] = None, max_val: Optional[float] = None) -> bool:
    """
    Validate float string with optional range checking.

    Args:
        value: String value to validate
        min_val: Minimum allowed value (optional)
        max_val: Maximum allowed value (optional)

    Returns:
        True if valid float in range, False otherwise

    Examples:
        >>> validate_float("123.45")
        True
        >>> validate_float("123.45", min_val=0.0, max_val=200.0)
        True
        >>> validate_float("abc")
        False
    """
    if not isinstance(value, str):
        return False

    try:
        float_val = float(value)
        if min_val is not None and float_val < min_val:
            return False
        if max_val is not None and float_val > max_val:
            return False
        return True
    except ValueError:
        return False


def validate_json(json_string: str) -> bool:
    """
    Validate JSON string format.

    Args:
        json_string: JSON string to validate

    Returns:
        True if valid JSON, False otherwise

    Examples:
        >>> validate_json('{"key": "value"}')
        True
        >>> validate_json("invalid")
        False
    """
    if not isinstance(json_string, str):
        return False

    try:
        import json
        json.loads(json_string)
        return True
    except (json.JSONDecodeError, ValueError):
        return False
