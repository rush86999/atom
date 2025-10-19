"""
RRule Scheduler for Workflow Automation

This module provides RRule-based scheduling capabilities for workflow automation,
enabling complex recurring schedules using the iCalendar RRule standard.
"""

from dateutil import rrule
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging
from enum import Enum
import json

logger = logging.getLogger(__name__)


class ScheduleFrequency(Enum):
    """Schedule frequency types"""

    MINUTELY = "minutely"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


class RRuleScheduler:
    """
    RRule-based scheduler for workflow automation with natural language support
    """

    def __init__(self):
        self.schedule_patterns = {
            # Simple patterns
            "every minute": {"freq": rrule.MINUTELY, "interval": 1},
            "every hour": {"freq": rrule.HOURLY, "interval": 1},
            "every day": {"freq": rrule.DAILY, "interval": 1},
            "every week": {"freq": rrule.WEEKLY, "interval": 1},
            "every month": {"freq": rrule.MONTHLY, "interval": 1},
            "every year": {"freq": rrule.YEARLY, "interval": 1},
            # Multiple intervals
            "every 5 minutes": {"freq": rrule.MINUTELY, "interval": 5},
            "every 15 minutes": {"freq": rrule.MINUTELY, "interval": 15},
            "every 30 minutes": {"freq": rrule.MINUTELY, "interval": 30},
            "every 2 hours": {"freq": rrule.HOURLY, "interval": 2},
            "every 6 hours": {"freq": rrule.HOURLY, "interval": 6},
            "every 2 days": {"freq": rrule.DAILY, "interval": 2},
            "every 2 weeks": {"freq": rrule.WEEKLY, "interval": 2},
            # Weekday patterns
            "every monday": {"freq": rrule.WEEKLY, "byweekday": rrule.MO},
            "every tuesday": {"freq": rrule.WEEKLY, "byweekday": rrule.TU},
            "every wednesday": {"freq": rrule.WEEKLY, "byweekday": rrule.WE},
            "every thursday": {"freq": rrule.WEEKLY, "byweekday": rrule.TH},
            "every friday": {"freq": rrule.WEEKLY, "byweekday": rrule.FR},
            "every saturday": {"freq": rrule.WEEKLY, "byweekday": rrule.SA},
            "every sunday": {"freq": rrule.WEEKLY, "byweekday": rrule.SU},
            # Business days
            "every weekday": {
                "freq": rrule.WEEKLY,
                "byweekday": [rrule.MO, rrule.TU, rrule.WE, rrule.TH, rrule.FR],
            },
            "every weekend": {"freq": rrule.WEEKLY, "byweekday": [rrule.SA, rrule.SU]},
            # Monthly patterns
            "first day of month": {"freq": rrule.MONTHLY, "bymonthday": 1},
            "last day of month": {"freq": rrule.MONTHLY, "bymonthday": -1},
            "15th of month": {"freq": rrule.MONTHLY, "bymonthday": 15},
        }

    def parse_natural_language_schedule(
        self, schedule_text: str, start_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Parse natural language schedule text into RRule configuration

        Args:
            schedule_text: Natural language schedule description
            start_time: Optional start time for the schedule

        Returns:
            Dictionary with RRule configuration and metadata
        """
        if not start_time:
            start_time = datetime.now()

        schedule_text_lower = schedule_text.lower().strip()

        # Check for exact pattern matches
        for pattern, config in self.schedule_patterns.items():
            if pattern in schedule_text_lower:
                rrule_config = config.copy()
                rrule_config["dtstart"] = start_time
                return self._build_schedule_config(
                    schedule_text, rrule_config, start_time
                )

        # Parse complex patterns
        return self._parse_complex_schedule(schedule_text, start_time)

    def _parse_complex_schedule(
        self, schedule_text: str, start_time: datetime
    ) -> Dict[str, Any]:
        """
        Parse complex natural language schedule patterns
        """
        text_lower = schedule_text.lower()
        words = text_lower.split()

        # Initialize base configuration
        config = {"dtstart": start_time}

        # Frequency detection
        if "minute" in text_lower:
            config["freq"] = rrule.MINUTELY
        elif "hour" in text_lower:
            config["freq"] = rrule.HOURLY
        elif "day" in text_lower:
            config["freq"] = rrule.DAILY
        elif "week" in text_lower:
            config["freq"] = rrule.WEEKLY
        elif "month" in text_lower:
            config["freq"] = rrule.MONTHLY
        elif "year" in text_lower:
            config["freq"] = rrule.YEARLY
        else:
            # Default to daily
            config["freq"] = rrule.DAILY

        # Interval detection
        for i, word in enumerate(words):
            if word.isdigit() and i + 1 < len(words):
                next_word = words[i + 1]
                if any(
                    time_unit in next_word
                    for time_unit in ["minute", "hour", "day", "week", "month", "year"]
                ):
                    config["interval"] = int(word)

        # Weekday detection
        weekdays = []
        if "monday" in text_lower or "mon" in text_lower:
            weekdays.append(rrule.MO)
        if "tuesday" in text_lower or "tue" in text_lower:
            weekdays.append(rrule.TU)
        if "wednesday" in text_lower or "wed" in text_lower:
            weekdays.append(rrule.WE)
        if "thursday" in text_lower or "thu" in text_lower:
            weekdays.append(rrule.TH)
        if "friday" in text_lower or "fri" in text_lower:
            weekdays.append(rrule.FR)
        if "saturday" in text_lower or "sat" in text_lower:
            weekdays.append(rrule.SA)
        if "sunday" in text_lower or "sun" in text_lower:
            weekdays.append(rrule.SU)

        if weekdays:
            config["byweekday"] = weekdays

        # Time of day detection
        if "morning" in text_lower:
            config["byhour"] = 9  # 9 AM
        elif "afternoon" in text_lower:
            config["byhour"] = 14  # 2 PM
        elif "evening" in text_lower:
            config["byhour"] = 18  # 6 PM
        elif "night" in text_lower:
            config["byhour"] = 21  # 9 PM

        return self._build_schedule_config(schedule_text, config, start_time)

    def _build_schedule_config(
        self, schedule_text: str, rrule_config: Dict, start_time: datetime
    ) -> Dict[str, Any]:
        """
        Build complete schedule configuration with RRule string
        """
        try:
            # Generate RRule string
            rrule_str = rrule.rrule(**rrule_config).to_text()

            # Calculate next execution
            next_execution = self.get_next_execution(rrule_config)

            return {
                "schedule_text": schedule_text,
                "rrule_config": rrule_config,
                "rrule_string": rrule_str,
                "start_time": start_time.isoformat(),
                "next_execution": next_execution.isoformat()
                if next_execution
                else None,
                "is_valid": True,
                "frequency": self._get_frequency_name(
                    rrule_config.get("freq", rrule.DAILY)
                ),
            }
        except Exception as e:
            logger.error(f"Error building schedule config: {str(e)}")
            return {
                "schedule_text": schedule_text,
                "rrule_config": rrule_config,
                "rrule_string": "",
                "start_time": start_time.isoformat(),
                "next_execution": None,
                "is_valid": False,
                "error": str(e),
            }

    def get_next_execution(
        self, rrule_config: Dict, after: Optional[datetime] = None
    ) -> Optional[datetime]:
        """
        Get the next execution time for a schedule

        Args:
            rrule_config: RRule configuration dictionary
            after: Optional datetime to get next execution after

        Returns:
            Next execution datetime or None if no more executions
        """
        if not after:
            after = datetime.now()

        try:
            rule = rrule.rrule(**rrule_config)
            occurrences = rule.after(after, inc=False)
            return occurrences
        except Exception as e:
            logger.error(f"Error calculating next execution: {str(e)}")
            return None

    def get_next_n_executions(
        self, rrule_config: Dict, count: int = 5, after: Optional[datetime] = None
    ) -> List[datetime]:
        """
        Get the next N execution times for a schedule

        Args:
            rrule_config: RRule configuration dictionary
            count: Number of executions to return
            after: Optional datetime to get executions after

        Returns:
            List of next execution datetimes
        """
        if not after:
            after = datetime.now()

        try:
            rule = rrule.rrule(**rrule_config)
            occurrences = list(rule.after(after, inc=False))
            return occurrences[:count]
        except Exception as e:
            logger.error(f"Error calculating next {count} executions: {str(e)}")
            return []

    def validate_schedule(self, rrule_config: Dict) -> Dict[str, Any]:
        """
        Validate RRule configuration

        Args:
            rrule_config: RRule configuration to validate

        Returns:
            Validation result with details
        """
        try:
            rule = rrule.rrule(**rrule_config)
            next_execution = self.get_next_execution(rrule_config)

            return {
                "is_valid": True,
                "rrule_string": rule.to_text(),
                "next_execution": next_execution.isoformat()
                if next_execution
                else None,
                "frequency": self._get_frequency_name(
                    rrule_config.get("freq", rrule.DAILY)
                ),
            }
        except Exception as e:
            return {
                "is_valid": False,
                "error": str(e),
                "rrule_string": "",
                "next_execution": None,
            }

    def create_cron_expression(self, rrule_config: Dict) -> str:
        """
        Convert RRule configuration to cron expression

        Args:
            rrule_config: RRule configuration dictionary

        Returns:
            Cron expression string
        """
        try:
            freq = rrule_config.get("freq", rrule.DAILY)
            interval = rrule_config.get("interval", 1)

            if freq == rrule.MINUTELY:
                return f"*/{interval} * * * *"
            elif freq == rrule.HOURLY:
                return f"0 */{interval} * * *"
            elif freq == rrule.DAILY:
                return f"0 0 */{interval} * *"
            elif freq == rrule.WEEKLY:
                # For weekly, we need to handle weekdays
                byweekday = rrule_config.get("byweekday")
                if byweekday:
                    if isinstance(byweekday, list):
                        days = ",".join(
                            str(self._weekday_to_cron(day)) for day in byweekday
                        )
                    else:
                        days = str(self._weekday_to_cron(byweekday))
                    return f"0 0 * * {days}"
                else:
                    return f"0 0 * * 0"  # Default to Sunday
            elif freq == rrule.MONTHLY:
                bymonthday = rrule_config.get("bymonthday", 1)
                return f"0 0 {bymonthday} * *"
            elif freq == rrule.YEARLY:
                return "0 0 1 1 *"
            else:
                return "0 0 * * *"  # Default daily

        except Exception as e:
            logger.error(f"Error creating cron expression: {str(e)}")
            return "0 0 * * *"  # Fallback to daily

    def _weekday_to_cron(self, weekday: int) -> int:
        """Convert RRule weekday to cron day (0-6, 0=Sunday)"""
        # RRule uses MO=0, TU=1, ..., SU=6
        # Cron uses 0=Sunday, 1=Monday, ..., 6=Saturday
        return (weekday + 1) % 7

    def _get_frequency_name(self, freq: int) -> str:
        """Get frequency name from RRule frequency constant"""
        freq_map = {
            rrule.MINUTELY: "minutely",
            rrule.HOURLY: "hourly",
            rrule.DAILY: "daily",
            rrule.WEEKLY: "weekly",
            rrule.MONTHLY: "monthly",
            rrule.YEARLY: "yearly",
        }
        return freq_map.get(freq, "unknown")

    def get_schedule_suggestions(self, base_schedule: str) -> List[Dict[str, Any]]:
        """
        Get schedule suggestions based on a base schedule

        Args:
            base_schedule: Base schedule text

        Returns:
            List of schedule suggestions
        """
        suggestions = []
        base_lower = base_schedule.lower()

        # Common variations
        variations = [
            "every minute",
            "every 5 minutes",
            "every 15 minutes",
            "every 30 minutes",
            "every hour",
            "every 2 hours",
            "every 6 hours",
            "every day",
            "every weekday",
            "every week",
            "every month",
        ]

        for variation in variations:
            if variation not in base_lower:
                suggestion_config = self.parse_natural_language_schedule(variation)
                if suggestion_config["is_valid"]:
                    suggestions.append(
                        {
                            "schedule_text": variation,
                            "rrule_string": suggestion_config["rrule_string"],
                            "frequency": suggestion_config["frequency"],
                            "next_execution": suggestion_config["next_execution"],
                        }
                    )

        return suggestions[:5]  # Return top 5 suggestions


# Global scheduler instance
_scheduler = None


def get_scheduler() -> RRuleScheduler:
    """Get or create the global scheduler instance"""
    global _scheduler
    if _scheduler is None:
        _scheduler = RRuleScheduler()
    return _scheduler
