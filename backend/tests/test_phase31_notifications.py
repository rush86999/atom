import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.append(os.getcwd())

from core.workflow_notifier import (
    NotificationSettings,
    WorkflowNotifier,
    get_notification_settings,
    set_notification_settings,
)


class TestPhase31Notifications(unittest.IsolatedAsyncioTestCase):

    def test_notification_settings(self):
        print("\n--- Phase 31: Notification Settings Test ---")
        
        # Test default settings
        settings = NotificationSettings()
        self.assertTrue(settings.enabled)
        self.assertTrue(settings.notify_on_success)
        self.assertTrue(settings.notify_on_failure)
        self.assertTrue(settings.slack_enabled)
        print("✅ Default settings work correctly")
        
        # Test custom settings
        custom = NotificationSettings(
            enabled=True,
            slack_channel="#my-alerts",
            slack_mention_users=["U12345"],
            email_enabled=True,
            email_recipients=["test@example.com"]
        )
        
        self.assertEqual(custom.slack_channel, "#my-alerts")
        self.assertIn("U12345", custom.slack_mention_users)
        print("✅ Custom settings work correctly")
        
        # Test store/retrieve
        set_notification_settings("test-workflow", custom)
        retrieved = get_notification_settings("test-workflow")
        self.assertEqual(retrieved.slack_channel, "#my-alerts")
        print("✅ Settings store/retrieve works")

    @patch.object(WorkflowNotifier, "_send_slack", new_callable=AsyncMock)
    async def test_notify_completion(self, mock_send_slack):
        print("\n--- Phase 31: Notify Completion Test ---")
        
        notifier = WorkflowNotifier()
        settings = NotificationSettings(
            enabled=True,
            slack_enabled=True,
            slack_channel="#test-channel"
        )
        
        await notifier.notify_completion(
            workflow_id="wf-123",
            workflow_name="Test Workflow",
            execution_id="exec-456",
            results={"step1": {"status": "success"}},
            settings=settings
        )
        
        # Verify Slack was called
        mock_send_slack.assert_called_once()
        channel, message = mock_send_slack.call_args[0]
        
        self.assertEqual(channel, "#test-channel")
        self.assertIn("Test Workflow", message)
        self.assertIn("Completed", message)
        print(f"✅ Slack notification sent to {channel}")

    @patch.object(WorkflowNotifier, "_send_slack", new_callable=AsyncMock)
    async def test_notify_failure(self, mock_send_slack):
        print("\n--- Phase 31: Notify Failure Test ---")
        
        notifier = WorkflowNotifier()
        settings = NotificationSettings(
            enabled=True,
            slack_enabled=True,
            slack_channel="#errors"
        )
        
        await notifier.notify_failure(
            workflow_id="wf-123",
            workflow_name="Failing Workflow",
            execution_id="exec-789",
            error="Connection timed out",
            settings=settings
        )
        
        mock_send_slack.assert_called_once()
        channel, message = mock_send_slack.call_args[0]
        
        self.assertEqual(channel, "#errors")
        self.assertIn("Failed", message)
        self.assertIn("Connection timed out", message)
        print(f"✅ Failure notification sent to {channel}")

if __name__ == "__main__":
    unittest.main()
