"""
Cron Expression Parser and Natural Language to Cron Converter

Supports:
- Standard cron expression parsing
- Natural language to cron conversion
- Next run calculation
"""

import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class CronParser:
    """
    Parser for cron expressions and natural language schedules.

    Cron format: minute hour day month weekday
    Example: "0 9 * * *" = Every day at 9:00 AM
    """

    # Natural language patterns
    PATTERNS = {
        # Hourly
        r"every\s+hour": "0 * * * *",
        r"hourly": "0 * * * *",

        # Daily
        r"daily": "0 9 * * *",
        r"every\s+day": "0 9 * * *",

        # Weekly
        r"weekly": "0 9 * * 1",
        r"every\s+week": "0 9 * * 1",

        # Monthly
        r"monthly": "0 9 1 * *",
        r"every\s+month": "0 9 1 * *",

        # Yearly
        r"yearly": "0 9 1 1 *",
        r"every\s+year": "0 9 1 1 *",
        r"annually": "0 9 1 1 *",
    }

    WEEKDAY_MAP = {
        "monday": "1",
        "tuesday": "2",
        "wednesday": "3",
        "thursday": "4",
        "friday": "5",
        "saturday": "6",
        "sunday": "0",
    }

    def __init__(self):
        """Initialize the cron parser."""
        pass

    def get_next_run(
        self,
        cron_expression: str,
        after: Optional[datetime] = None,
    ) -> datetime:
        """
        Calculate the next run time for a cron expression.

        Args:
            cron_expression: Cron expression (5 parts: minute hour day month weekday)
            after: Calculate next run after this time (default: now)

        Returns:
            Next run datetime (UTC)

        Raises:
            ValueError: If cron expression is invalid
        """
        if after is None:
            after = datetime.now(timezone.utc)

        try:
            parts = cron_expression.split()
            if len(parts) != 5:
                raise ValueError(
                    f"Invalid cron expression: {cron_expression}. "
                    "Must have 5 parts: minute hour day month weekday"
                )

            minute, hour, day, month, weekday = parts

            # Simple implementation: Start from 'after' and increment until match
            # For production, consider using 'croniter' library
            next_run = after.replace(second=0, microsecond=0) + timedelta(minutes=1)

            # Try to find next match (max iterations: 365 days * 24 hours * 60 minutes)
            for _ in range(525600):  # ~1 year of minutes
                if self._matches_cron(next_run, minute, hour, day, month, weekday):
                    return next_run
                next_run += timedelta(minutes=1)

            raise ValueError(
                f"Could not find next run for cron expression: {cron_expression}"
            )

        except Exception as e:
            logger.error(f"Error calculating next run for cron '{cron_expression}': {e}")
            raise ValueError(f"Invalid cron expression: {e}")

    def _matches_cron(
        self,
        dt: datetime,
        cron_minute: str,
        cron_hour: str,
        cron_day: str,
        cron_month: str,
        cron_weekday: str,
    ) -> bool:
        """Check if a datetime matches a cron expression."""
        # Check minute
        if not self._matches_field(dt.minute, cron_minute, 0, 59):
            return False

        # Check hour
        if not self._matches_field(dt.hour, cron_hour, 0, 23):
            return False

        # Check day
        if not self._matches_field(dt.day, cron_day, 1, 31):
            return False

        # Check month
        if not self._matches_field(dt.month, cron_month, 1, 12):
            return False

        # Check weekday (0=Sunday, 6=Saturday)
        if not self._matches_field(dt.weekday(), cron_weekday, 0, 6):
            return False

        return True

    def _matches_field(
        self,
        value: int,
        cron_field: str,
        min_val: int,
        max_val: int,
    ) -> bool:
        """Check if a value matches a cron field."""
        # Wildcard
        if cron_field == "*":
            return True

        # Exact match
        if cron_field.isdigit():
            return value == int(cron_field)

        # Range (e.g., "1-5")
        if "-" in cron_field:
            parts = cron_field.split("-")
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                start, end = int(parts[0]), int(parts[1])
                return start <= value <= end

        # Step (e.g., "*/5" or "1-10/2")
        if "/" in cron_field:
            base, step = cron_field.split("/")
            step = int(step)

            if base == "*":
                return value % step == 0

            if "-" in base:
                parts = base.split("-")
                if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                    start, end = int(parts[0]), int(parts[1])
                    if start <= value <= end:
                        return (value - start) % step == 0
                    return False

        # List (e.g., "1,3,5")
        if "," in cron_field:
            values = [int(v.strip()) for v in cron_field.split(",") if v.strip().isdigit()]
            return value in values

        return False

    def _to_24h(self, hour: str, minute: str, ampm: Optional[str]) -> str:
        """Convert 12-hour time to 24-hour format for cron."""
        h = int(hour)
        m = minute

        if ampm:
            ampm = ampm.lower()
            if ampm == "pm" and h != 12:
                h += 12
            elif ampm == "am" and h == 12:
                h = 0

        return f"{h} {m}"

    def _weekday_to_num(self, weekday: str) -> str:
        """Convert weekday name to cron number (0=Sunday)."""
        return self.WEEKDAY_MAP.get(weekday.lower(), "1")


def natural_language_to_cron(text: str) -> str:
    """
    Convert natural language schedule to cron expression.

    Supports:
    - "every day at 9:00am" → "0 9 * * *"
    - "every monday at 2:30pm" → "30 14 * * 1"
    - "hourly" → "0 * * * *"
    - "daily" → "0 9 * * *"
    - "weekly" → "0 9 * * 1"
    - "monthly" → "0 9 1 * *"
    - "yearly" → "0 9 1 1 *"

    Args:
        text: Natural language schedule

    Returns:
        Cron expression (5 parts)

    Raises:
        ValueError: If text cannot be parsed
    """
    text_lower = text.lower().strip()

    # Custom patterns with special handling
    # Every day at specific time (supports both "9am" and "9:30am" formats)
    match = re.match(r"every\s+day\s+at\s+(\d{1,2})(:(\d{2}))?\s*(am|pm)", text_lower)
    if match:
        hour = match.group(1)
        minute = match.group(3) if match.group(3) else "0"
        # Normalize minute: "00" -> "0"
        if minute == "00":
            minute = "0"
        ampm = match.group(4)
        hour_24 = _to_24h_static(hour, minute, ampm)
        return f"{minute} {hour_24} * * *"

    # Every weekday at specific time (supports both "2pm" and "2:30pm" formats)
    match = re.match(r"every\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+at\s+(\d{1,2})(:(\d{2}))?\s*(am|pm)", text_lower)
    if match:
        weekday = match.group(1)
        hour = match.group(2)
        minute = match.group(4) if match.group(4) else "0"
        # Normalize minute: "00" -> "0"
        if minute == "00":
            minute = "0"
        ampm = match.group(5)
        hour_24 = _to_24h_static(hour, minute, ampm)
        weekday_num = _weekday_to_num_static(weekday)
        return f"{minute} {hour_24} * * {weekday_num}"

    parser = CronParser()

    # Try each pattern
    for pattern, replacement in parser.PATTERNS.items():
        if callable(replacement):
            match = re.match(pattern, text_lower)
            if match:
                try:
                    return replacement(match)
                except Exception as e:
                    logger.warning(f"Pattern matched but conversion failed: {e}")
                    continue
        else:
            if re.match(pattern, text_lower):
                return replacement

    raise ValueError(
        f"Could not parse natural language schedule: '{text}'. "
        f"Supported patterns include: 'every day at 9:00am', "
        f"'every monday at 2:30pm', 'hourly', 'daily', 'weekly', 'monthly', 'yearly'"
    )


def _to_24h_static(hour: str, minute: str, ampm: Optional[str]) -> str:
    """Static version of _to_24h for use in module-level functions."""
    h = int(hour)
    m = minute

    if ampm:
        ampm = ampm.lower()
        if ampm == "pm" and h != 12:
            h += 12
        elif ampm == "am" and h == 12:
            h = 0

    # Normalize minute: "00" -> "0"
    if m == "00":
        m = "0"

    return f"{h}"


def _weekday_to_num_static(weekday: str) -> str:
    """Static version of _weekday_to_num for use in module-level functions."""
    WEEKDAY_MAP = {
        "monday": "1",
        "tuesday": "2",
        "wednesday": "3",
        "thursday": "4",
        "friday": "5",
        "saturday": "6",
        "sunday": "0",
    }
    return WEEKDAY_MAP.get(weekday.lower(), "1")


def validate_cron_expression(cron_expression: str) -> bool:
    """
    Validate a cron expression.

    Args:
        cron_expression: Cron expression to validate

    Returns:
        True if valid, False otherwise
    """
    try:
        parts = cron_expression.split()
        if len(parts) != 5:
            return False

        # Basic validation: each part should be valid
        minute, hour, day, month, weekday = parts

        # Validate ranges (basic check)
        # minute: 0-59, hour: 0-23, day: 1-31, month: 1-12, weekday: 0-6
        if not CronParser()._is_valid_field(minute, 0, 59):
            return False
        if not CronParser()._is_valid_field(hour, 0, 23):
            return False
        if not CronParser()._is_valid_field(day, 1, 31):
            return False
        if not CronParser()._is_valid_field(month, 1, 12):
            return False
        if not CronParser()._is_valid_field(weekday, 0, 6):
            return False

        return True

    except Exception:
        return False


# Extend CronParser with validation helper
def _is_valid_field(self, field: str, min_val: int, max_val: int) -> bool:
    """Check if a cron field is valid."""
    if field == "*":
        return True

    # Exact match
    if field.isdigit():
        return min_val <= int(field) <= max_val

    # Range
    if "-" in field:
        parts = field.split("-")
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            return min_val <= int(parts[0]) <= max_val and min_val <= int(parts[1]) <= max_val

    # Step
    if "/" in field:
        base, step = field.split("/")
        if step.isdigit():
            if base == "*":
                return True
            if "-" in base:
                parts = base.split("-")
                if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                    return True

    # List
    if "," in field:
        values = [v.strip() for v in field.split(",")]
        for v in values:
            if not v.isdigit():
                return False
            if not (min_val <= int(v) <= max_val):
                return False
        return True

    return False


CronParser._is_valid_field = _is_valid_field
