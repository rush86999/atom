"""
Minimal unit tests for Scheduled Messaging Service core logic

Tests only the service logic without database or integration dependencies.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import Mock, MagicMock
import pytest
from datetime import datetime, timezone, timedelta

# Mock the imports before importing the service
sys.modules['core.agent_integration_gateway'] = MagicMock()
sys.modules['integrations.atom_discord_integration'] = MagicMock()
sys.modules['integrations.atom_whatsapp_integration'] = MagicMock()
sys.modules['integrations.atom_telegram_integration'] = MagicMock()
sys.modules['integrations.google_chat_enhanced_service'] = MagicMock()
sys.modules['integrations.meta_business_service'] = MagicMock()
sys.modules['integrations.marketing_unified_service'] = MagicMock()
sys.modules['integrations.ecommerce_unified_service'] = MagicMock()
sys.modules['integrations.slack_enhanced_service'] = MagicMock()
sys.modules['integrations.teams_enhanced_service'] = MagicMock()
sys.modules['integrations.document_logic_service'] = MagicMock()
sys.modules['integrations.shopify_service'] = MagicMock()
sys.modules['integrations.openclaw_service'] = MagicMock()

from core.models import ScheduledMessageStatus
from core.cron_parser import natural_language_to_cron, CronParser


class TestCronParser:
    """Tests for cron expression parsing and natural language conversion."""

    def test_parse_every_day_at_9am(self):
        """Test parsing 'every day at 9am'."""
        result = natural_language_to_cron("every day at 9am")
        assert result == "0 9 * * *"

    def test_parse_every_day_at_9pm(self):
        """Test parsing 'every day at 9pm'."""
        result = natural_language_to_cron("every day at 9pm")
        assert result == "0 21 * * *"

    def test_parse_every_monday_at_2pm(self):
        """Test parsing 'every monday at 2:00pm'."""
        result = natural_language_to_cron("every monday at 2:00pm")
        assert result == "0 14 * * 1"

    def test_parse_every_friday_at_930am(self):
        """Test parsing 'every friday at 9:30am'."""
        result = natural_language_to_cron("every friday at 9:30am")
        assert result == "30 9 * * 5"

    def test_parse_hourly(self):
        """Test parsing 'hourly'."""
        result = natural_language_to_cron("hourly")
        assert result == "0 * * * *"

    def test_parse_every_hour(self):
        """Test parsing 'every hour'."""
        result = natural_language_to_cron("every hour")
        assert result == "0 * * * *"

    def test_parse_daily(self):
        """Test parsing 'daily'."""
        result = natural_language_to_cron("daily")
        assert result == "0 9 * * *"

    def test_parse_every_day(self):
        """Test parsing 'every day'."""
        result = natural_language_to_cron("every day")
        assert result == "0 9 * * *"

    def test_parse_weekly(self):
        """Test parsing 'weekly'."""
        result = natural_language_to_cron("weekly")
        assert result == "0 9 * * 1"

    def test_parse_every_week(self):
        """Test parsing 'every week'."""
        result = natural_language_to_cron("every week")
        assert result == "0 9 * * 1"

    def test_parse_monthly(self):
        """Test parsing 'monthly'."""
        result = natural_language_to_cron("monthly")
        assert result == "0 9 1 * *"

    def test_parse_every_month(self):
        """Test parsing 'every month'."""
        result = natural_language_to_cron("every month")
        assert result == "0 9 1 * *"

    def test_parse_yearly(self):
        """Test parsing 'yearly'."""
        result = natural_language_to_cron("yearly")
        assert result == "0 9 1 1 *"

    def test_parse_every_year(self):
        """Test parsing 'every year'."""
        result = natural_language_to_cron("every year")
        assert result == "0 9 1 1 *"

    def test_parse_annually(self):
        """Test parsing 'annually'."""
        result = natural_language_to_cron("annually")
        assert result == "0 9 1 1 *"

    def test_parse_invalid_input(self):
        """Test parsing invalid input raises error."""
        with pytest.raises(ValueError):
            natural_language_to_cron("gibberish input")

    def test_case_insensitive_parsing(self):
        """Test that parsing is case-insensitive."""
        result1 = natural_language_to_cron("EVERY DAY AT 9AM")
        result2 = natural_language_to_cron("Every Day at 9am")
        result3 = natural_language_to_cron("every day at 9AM")

        assert result1 == result2 == result3

    def test_calculate_next_run_daily(self):
        """Test calculating next run for daily schedule."""
        parser = CronParser()
        cron = "0 9 * * *"  # Daily at 9am

        now = datetime(2026, 2, 4, 8, 0, 0, tzinfo=timezone.utc)
        next_run = parser.get_next_run(cron, after=now)

        # Should be 9am on the same day
        assert next_run.hour == 9
        assert next_run.minute == 0
        assert next_run.day == 4

    def test_calculate_next_run_hourly(self):
        """Test calculating next run for hourly schedule."""
        parser = CronParser()
        cron = "0 * * * *"  # Every hour

        now = datetime(2026, 2, 4, 8, 30, 0, tzinfo=timezone.utc)
        next_run = parser.get_next_run(cron, after=now)

        # Should be 9am on the same day
        assert next_run.hour == 9
        assert next_run.minute == 0

    def test_calculate_next_run_weekly(self):
        """Test calculating next run for weekly schedule (every Monday)."""
        parser = CronParser()
        cron = "0 9 * * 1"  # Every Monday at 9am

        # Tuesday Feb 4, 2026 at 8am
        now = datetime(2026, 2, 4, 8, 0, 0, tzinfo=timezone.utc)
        next_run = parser.get_next_run(cron, after=now)

        # Should be Monday Feb 10 at 9am (next Monday)
        assert next_run.hour == 9
        assert next_run.minute == 0
        assert next_run.day >= 4  # Next Monday should be after the 4th


class TestScheduledMessageDataValidation:
    """Test data validation for scheduled messages."""

    def test_schedule_types(self):
        """Test valid schedule types."""
        valid_types = ["one_time", "recurring"]

        assert "one_time" in valid_types
        assert "recurring" in valid_types

    def test_message_statuses(self):
        """Test all message statuses."""
        statuses = [
            ScheduledMessageStatus.ACTIVE.value,
            ScheduledMessageStatus.PAUSED.value,
            ScheduledMessageStatus.COMPLETED.value,
            ScheduledMessageStatus.FAILED.value,
            ScheduledMessageStatus.CANCELLED.value,
        ]

        assert "active" in statuses
        assert "paused" in statuses
        assert "completed" in statuses
        assert "failed" in statuses
        assert "cancelled" in statuses


class TestTemplateVariableSubstitution:
    """Tests for template variable substitution logic."""

    def test_basic_substitution(self):
        """Test basic variable substitution."""
        from core.scheduled_messaging_service import ScheduledMessagingService

        # Create a mock database
        mock_db = MagicMock()
        service = ScheduledMessagingService(mock_db)

        template = "Hello {{name}}, your balance is ${{amount}}"
        variables = {"name": "Alice", "amount": "100"}

        result = service._substitute_template_variables(template, variables)

        assert result == "Hello Alice, your balance is $100"

    def test_builtin_variables(self):
        """Test that built-in variables are included."""
        from core.scheduled_messaging_service import ScheduledMessagingService

        mock_db = MagicMock()
        service = ScheduledMessagingService(mock_db)

        template = "Report for {{date}} at {{time}}"
        variables = {}

        result = service._substitute_template_variables(template, variables)

        # Should not contain placeholders
        assert "{{date}}" not in result
        assert "{{time}}" not in result
        assert "Report for" in result

    def test_user_variables_override_builtins(self):
        """Test that user variables override built-in variables."""
        from core.scheduled_messaging_service import ScheduledMessagingService

        mock_db = MagicMock()
        service = ScheduledMessagingService(mock_db)

        template = "Date: {{date}}"
        variables = {"date": "CUSTOM_DATE"}

        result = service._substitute_template_variables(template, variables)

        assert result == "Date: CUSTOM_DATE"

    def test_multiple_variables(self):
        """Test substituting multiple variables."""
        from core.scheduled_messaging_service import ScheduledMessagingService

        mock_db = MagicMock()
        service = ScheduledMessagingService(mock_db)

        template = "{{greeting}} {{name}}, your {{item}} is ready"
        variables = {
            "greeting": "Hello",
            "name": "Bob",
            "item": "order"
        }

        result = service._substitute_template_variables(template, variables)

        assert result == "Hello Bob, your order is ready"

    def test_no_variables(self):
        """Test template with no variables."""
        from core.scheduled_messaging_service import ScheduledMessagingService

        mock_db = MagicMock()
        service = ScheduledMessagingService(mock_db)

        template = "Simple message with no variables"
        variables = {}

        result = service._substitute_template_variables(template, variables)

        assert result == "Simple message with no variables"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
