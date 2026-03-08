
from datetime import datetime
import json
import logging
import re
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

def parse_react_response(llm_output: str) -> Tuple[Optional[str], Optional[Dict[str, Any]], Optional[str]]:
    """
    Parse the LLM output to extract Thought, Action, and Final Answer.
    
    Expected Formats:
    
    Format 1 (JSON Action):
    Thought: I need to search for X.
    Action: {
        "tool": "tool_name",
        "params": { ... }
    }
    
    Format 2 (Final Answer):
    Thought: I have found the info.
    Final Answer: The answer is X.
    
    Returns:
        (thought_text, action_dict, final_answer_text)
    """
    # Normalize
    text = llm_output.strip()
    
    thought = None
    action = None
    final_answer = None
    
    # Extract Thought
    # Extract Thought
    # Lookahead for Action or Final Answer, allowing for whitespace/newlines
    thought_match = re.search(r"Thought:\s*(.*?)(?=\n\s*Action:|\n\s*Final Answer:|$)", text, re.DOTALL | re.IGNORECASE)
    if thought_match:
        thought = thought_match.group(1).strip()
    else:
        # If no explicit "Thought:", treat beginning as thought
        # But be careful if it starts with Action
        if not text.lower().strip().startswith("action:") and not text.lower().strip().startswith("final answer:"):
            # Try to grab everything until Action or Final Answer
            split_match = re.split(r"\n\s*Action:|\n\s*Final Answer:", text, flags=re.IGNORECASE)
            if split_match:
                thought = split_match[0].strip()

    # Extract Final Answer
    final_answer_match = re.search(r"Final Answer:\s*(.*)", text, re.DOTALL | re.IGNORECASE)
    if final_answer_match:
        final_answer = final_answer_match.group(1).strip()
        return thought, None, final_answer

    # Extract Action
    # Look for Action: ... json ...
    action_match = re.search(r"Action:\s*(.*)", text, re.DOTALL | re.IGNORECASE)
    if action_match:
        action_text = action_match.group(1).strip()

        # Try to find JSON blob in action text
        # Simple heuristic: find first { and last }
        try:
            json_start = action_text.find("{")
            json_end = action_text.rfind("}")

            if json_start != -1 and json_end != -1:
                json_str = action_text[json_start:json_end+1]
                action = json.loads(json_str)
            else:
                # No valid JSON structure found
                logger.warning(f"Action found but no valid JSON structure: {action_text[:200]}")
                raise ValueError(f"Invalid action format: no JSON structure found in '{action_text[:100]}...'")

        except json.JSONDecodeError as e:
            # JSON parsing failed - log error and raise
            logger.error(f"Failed to parse agent action JSON: {e}\nAction text: {action_text[:500]}")
            raise ValueError(f"Invalid JSON in agent action: {e}") from e

    return thought, action, final_answer


# ==============================================================================
# Agent Utility Formatters
# ==============================================================================

def format_agent_id(agent_id: str) -> str:
    """
    Format agent ID for display.

    Args:
        agent_id: Raw agent ID (e.g., "agent-abc123")

    Returns:
        Formatted agent ID with consistent capitalization and spacing

    Examples:
        >>> format_agent_id("agent-abc123")
        'Agent ABC123'
        >>> format_agent_id("workflow-xyz")
        'Workflow XYZ'
    """
    if not agent_id:
        return "Unknown Agent"

    # Split by common delimiters
    parts = re.split(r'[-_]', agent_id)

    # Capitalize each part
    formatted_parts = [part.upper() if part.lower() in ['id', 'uuid'] else part.capitalize() for part in parts if part]

    return ' '.join(formatted_parts)


def parse_agent_id(agent_id: str) -> Dict[str, Optional[str]]:
    """
    Parse agent ID into components.

    Args:
        agent_id: Agent ID string (e.g., "agent-abc123" or "workflow-v2-test")

    Returns:
        Dict with 'type', 'id', 'version' keys

    Examples:
        >>> parse_agent_id("agent-abc123")
        {'type': 'agent', 'id': 'abc123', 'version': None}
        >>> parse_agent_id("workflow-v2-test")
        {'type': 'workflow', 'id': 'test', 'version': 'v2'}
    """
    if not agent_id:
        return {'type': None, 'id': None, 'version': None}

    parts = agent_id.split('-')

    result = {
        'type': parts[0] if len(parts) > 0 else None,
        'id': parts[-1] if len(parts) > 1 else None,
        'version': None
    }

    # Check for version pattern (v1, v2, etc.)
    for part in parts:
        if re.match(r'^v\d+$', part.lower()):
            result['version'] = part.lower()
            # Remove version from id if it's there
            if result['id'] == part:
                result['id'] = parts[-2] if len(parts) > 2 else None

    return result


def format_maturity_level(maturity: str) -> str:
    """
    Format maturity level for display.

    Args:
        maturity: Maturity level (STUDENT, INTERN, SUPERVISED, AUTONOMOUS)

    Returns:
        Formatted display name

    Examples:
        >>> format_maturity_level("STUDENT")
        'Student Agent'
        >>> format_maturity_level("AUTONOMOUS")
        'Autonomous Agent'
    """
    maturity_map = {
        'STUDENT': 'Student Agent',
        'INTERN': 'Intern Agent',
        'SUPERVISED': 'Supervised Agent',
        'AUTONOMOUS': 'Autonomous Agent'
    }

    return maturity_map.get(maturity.upper(), maturity.capitalize() + ' Agent')


# ==============================================================================
# Date/Time Formatters
# ==============================================================================

def format_date_iso(date_string: str) -> str:
    """
    Format ISO date string to readable format.

    Args:
        date_string: ISO date string (YYYY-MM-DD)

    Returns:
        Formatted date (e.g., "March 8, 2026")

    Examples:
        >>> format_date_iso("2026-03-08")
        'March 8, 2026'
    """
    try:
        date_obj = datetime.fromisoformat(date_string)
        return date_obj.strftime("%B %d, %Y").replace(" 0", " ")
    except (ValueError, AttributeError):
        return date_string


def format_datetime(date_string: str) -> str:
    """
    Format ISO datetime string to readable format with time.

    Args:
        date_string: ISO datetime string (YYYY-MM-DDTHH:MM:SS)

    Returns:
        Formatted datetime (e.g., "March 8, 2026 at 2:30 PM")

    Examples:
        >>> format_datetime("2026-03-08T14:30:00")
        'March 8, 2026 at 2:30 PM'
    """
    try:
        date_obj = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
        return date_obj.strftime("%B %d, %Y at %I:%M %p").replace(" 0", " ").lstrip('0')
    except (ValueError, AttributeError):
        return date_string


def format_timestamp(timestamp: float) -> str:
    """
    Format Unix timestamp to readable date.

    Args:
        timestamp: Unix timestamp (seconds since epoch)

    Returns:
        Formatted date (e.g., "March 8, 2026")

    Examples:
        >>> format_timestamp(1772974705)
        'March 8, 2026'
    """
    try:
        date_obj = datetime.fromtimestamp(timestamp)
        return date_obj.strftime("%B %d, %Y").replace(" 0", " ")
    except (ValueError, TypeError, OSError):
        return str(timestamp)


def format_relative_time(timestamp: float) -> str:
    """
    Format timestamp as relative time (e.g., "2 hours ago").

    Args:
        timestamp: Unix timestamp

    Returns:
        Relative time string

    Examples:
        >>> format_relative_time(time.time() - 3600)
        '1 hour ago'
    """
    try:
        from datetime import timezone
        now = datetime.now(timezone.utc)
        past = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        diff = now - past

        seconds = diff.total_seconds()

        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif seconds < 604800:
            days = int(seconds / 86400)
            return f"{days} day{'s' if days != 1 else ''} ago"
        else:
            weeks = int(seconds / 604800)
            return f"{weeks} week{'s' if weeks != 1 else ''} ago"
    except (ValueError, TypeError, OSError):
        return "unknown time"


# ==============================================================================
# Number/Currency Formatters
# ==============================================================================

def format_currency_usd(amount: float) -> str:
    """
    Format amount as USD currency.

    Args:
        amount: Amount in USD

    Returns:
        Formatted currency string (e.g., "$1,000.00")

    Examples:
        >>> format_currency_usd(1000)
        '$1,000.00'
    """
    try:
        return f"${amount:,.2f}"
    except (ValueError, TypeError):
        return "$0.00"


def format_currency_eur(amount: float) -> str:
    """
    Format amount as EUR currency.

    Args:
        amount: Amount in EUR

    Returns:
        Formatted currency string (e.g., "€1,000.00")

    Examples:
        >>> format_currency_eur(1000)
        '€1,000.00'
    """
    try:
        return f"€{amount:,.2f}"
    except (ValueError, TypeError):
        return "€0.00"


def format_number(number: int) -> str:
    """
    Format number with thousands separators.

    Args:
        number: Number to format

    Returns:
        Formatted number string (e.g., "1,000,000")

    Examples:
        >>> format_number(1000000)
        '1,000,000'
    """
    try:
        return f"{number:,}"
    except (ValueError, TypeError):
        return "0"


def format_percentage(value: float, decimals: int = 1) -> str:
    """
    Format value as percentage.

    Args:
        value: Value as decimal (0.5 = 50%)
        decimals: Number of decimal places

    Returns:
        Formatted percentage string (e.g., "50.5%")

    Examples:
        >>> format_percentage(0.505)
        '50.5%'
    """
    try:
        return f"{value * 100:.{decimals}f}%"
    except (ValueError, TypeError):
        return "0.0%"


def format_decimal(value: float, precision: int = 2) -> str:
    """
    Format value with specified decimal precision.

    Args:
        value: Value to format
        precision: Number of decimal places

    Returns:
        Formatted decimal string

    Examples:
        >>> format_decimal(3.14159, 2)
        '3.14'
    """
    try:
        return f"{value:.{precision}f}"
    except (ValueError, TypeError):
        return "0.00"


# ==============================================================================
# String Formatters
# ==============================================================================

def format_phone(phone: str) -> str:
    """
    Format phone number to US format.

    Args:
        phone: Phone number string (digits only or with formatting)

    Returns:
        Formatted phone number (e.g., "(123) 456-7890")

    Examples:
        >>> format_phone("1234567890")
        '(123) 456-7890'
    """
    if not phone:
        return ""

    # Remove all non-digit characters
    digits = re.sub(r'\D', '', phone)

    # Format based on length
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    elif len(digits) == 11 and digits[0] == '1':
        return f"+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
    else:
        # Return original if can't format
        return phone


def format_name(name: str) -> str:
    """
    Format name with proper capitalization.

    Args:
        name: Name string

    Returns:
        Formatted name with each word capitalized

    Examples:
        >>> format_name("john doe")
        'John Doe'
    """
    if not name:
        return ""

    # Capitalize each word
    return ' '.join(word.capitalize() for word in name.split())


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate text to maximum length with suffix.

    Args:
        text: Text to truncate
        max_length: Maximum length (including suffix)
        suffix: Suffix to add when truncated

    Returns:
        Truncated text

    Examples:
        >>> truncate_text("This is a very long text", 10)
        'This is...'
    """
    if not text:
        return ""

    if len(text) <= max_length:
        return text

    # Truncate and add suffix
    return text[:max_length - len(suffix)] + suffix


def sanitize_string(text: str, remove_html: bool = True, remove_special: bool = False) -> str:
    """
    Sanitize string by removing HTML and/or special characters.

    Args:
        text: Text to sanitize
        remove_html: Remove HTML tags
        remove_special: Remove special characters (keep alphanumeric and spaces)

    Returns:
        Sanitized string

    Examples:
        >>> sanitize_string("<p>Hello</p>")
        'Hello'
    """
    if not text:
        return ""

    result = text

    # Remove HTML tags
    if remove_html:
        result = re.sub(r'<[^>]+>', '', result)

    # Remove special characters
    if remove_special:
        result = re.sub(r'[^a-zA-Z0-9\s]', '', result)

    return result.strip()
