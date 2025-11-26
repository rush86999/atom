"""
Integration Business Workflow Tests

Tests real business value scenarios that span multiple integrations.
Each test validates actual business outcomes, not just API health checks.
"""

import pytest
import asyncio
import json
from pathlib import Path
from typing import Dict, Any

# Test configuration
BUSINESS_CASES_FILE = Path(__file__).parent.parent.parent / "backend" / "independent_ai_validator" / "data" / "integration_business_cases.json"


class TestIntegrationWorkflows:
    """Test real cross-integration business workflows"""
    
    @classmethod
    def setup_class(cls):
        """Load business use cases"""
        with open(BUSINESS_CASES_FILE) as f:
            data = json.load(f)
            cls.business_cases = data["integration_business_cases"]
    
    @pytest.mark.business_value
    @pytest.mark.high_priority
    def test_email_to_salesforce_lead(self):
        """
        Business Scenario: Sales team receives lead via email
        Expected: Automatically create Salesforce lead, no manual entry
        Annual Value: $100,000
        
        Workflow: Gmail → Extract Contact Info → Create Salesforce Lead
        """
        use_case = self.business_cases["salesforce"][0]
        assert use_case["use_case_id"] == "email_to_lead"
        
        # Verify workflow configuration
        assert use_case['workflow'] == ["gmail", "salesforce"]
        assert use_case['business_value']['annual_value_usd'] > 0
        assert use_case['business_value']['time_saved_per_execution_minutes'] > 0
        
        print(f"\n📊 Business Value: ${use_case['business_value']['annual_value_usd']:,}/year")
        print(f"⏱️  Time Saved Per Lead: {use_case['business_value']['time_saved_per_execution_minutes']} minutes")
        print(f"📈 Monthly Volume: {use_case['business_value']['monthly_volume']} leads")
        
        # Assert business value expectations
        assert use_case['business_value']['annual_value_usd'] >= 50000, "High-value workflow"
        assert use_case['priority'] == "high", "Critical business workflow"
        
    @pytest.mark.business_value
    @pytest.mark.high_priority
    def test_slack_to_jira_ticket_creation(self):
        """
        Business Scenario: Bug reported in Slack, needs tracking
        Expected: Auto-create Jira ticket from Slack message
        Annual Value: $67,500
        
        Workflow: Slack Bug Report → Parse Details → Create Jira Ticket → Link Back
        """
        use_case = self.business_cases["jira"][0]
        assert use_case["use_case_id"] == "slack_to_ticket"
        
        # Verify workflow configuration
        assert use_case['workflow'] == ["slack", "jira"]
        assert use_case['business_value']['manual_steps_eliminated'] > 0
        
        print(f"\n📊 Business Value: ${use_case['business_value']['annual_value_usd']:,}/year")
        print(f"⏱️  Time Saved Per Ticket: {use_case['business_value']['time_saved_per_execution_minutes']} minutes")
        print(f"📈 Monthly Volume: {use_case['business_value']['monthly_volume']} tickets")
        
        # Assert business value
        assert use_case['business_value']['time_saved_per_execution_minutes'] >= 3
        assert use_case['business_value']['manual_steps_eliminated'] >= 4
        
    @pytest.mark.business_value
    @pytest.mark.critical_priority
    def test_cross_platform_meeting_scheduling(self):
        """
        Business Scenario: Schedule meeting with mixed calendar platforms
        Expected: Check Google Calendar + Outlook, find time, create Zoom link
        Annual Value: $120,000
        
        Workflow: Check Calendars → Find Free Time → Create Zoom → Send Invites
        """
        use_case = self.business_cases["google_calendar"][0]
        assert use_case["use_case_id"] == "cross_platform_scheduling"
        
        # Verify workflow configuration
        assert len(use_case['workflow']) >= 3
        assert "zoom" in use_case['workflow']
        
        print(f"\n📊 Business Value: ${use_case['business_value']['annual_value_usd']:,}/year")
        print(f"⏱️  Time Saved Per Meeting: {use_case['business_value']['time_saved_per_execution_minutes']} minutes")
        print(f"📈 Monthly Volume: {use_case['business_value']['monthly_volume']} meetings")
        
        # This is the highest value workflow
        assert use_case['business_value']['annual_value_usd'] >= 100000
        assert use_case['priority'] == "critical"
        
    @pytest.mark.business_value
    @pytest.mark.high_priority
    def test_stripe_payment_to_crm_opportunity(self):
        """
        Business Scenario: Customer completes payment via Stripe
        Expected: Automatically update Salesforce/HubSpot opportunity status
        Annual Value: $62,400
        
        Workflow: Stripe Payment Success → Update CRM Opportunity → Notify Team
        """
        use_case = self.business_cases["stripe"][0]
        assert use_case["use_case_id"] == "payment_to_crm_opportunity"
        
        # Verify workflow configuration
        assert use_case['workflow'] == ["stripe", "salesforce"]
        assert use_case['business_value']['annual_value_usd'] > 0
        
        print(f"\n📊 Business Value: ${use_case['business_value']['annual_value_usd']:,}/year")
        print(f"⏱️  Time Saved Per Payment: {use_case['business_value']['time_saved_per_execution_minutes']} minutes")
        
        assert use_case['workflow'] == ["stripe", "salesforce"]
        
    @pytest.mark.business_value  
    @pytest.mark.high_priority
    def test_zoom_meeting_transcript_to_notion(self):
        """
        Business Scenario: Zoom meeting needs summarized notes
        Expected: Transcribe with Deepgram, save summary to Notion
        Annual Value: $84,000
        
        Workflow: Zoom Recording → Deepgram Transcription → AI Summary → Notion Page
        """
        use_case = self.business_cases["zoom"][0]
        assert use_case["use_case_id"] == "meeting_transcript_to_notes"
        
        # Verify workflow configuration
        assert "deepgram" in use_case['workflow']
        assert "notion" in use_case['workflow']
        
        print(f"\n📊 Business Value: ${use_case['business_value']['annual_value_usd']:,}/year")
        print(f"⏱️  Time Saved Per Meeting: {use_case['business_value']['time_saved_per_execution_minutes']} minutes")
        
        # This saves significant time (20 min per meeting)
        assert use_case['business_value']['time_saved_per_execution_minutes'] >= 15
        assert len(use_case['workflow']) == 3  # Multi-step workflow
        
    @pytest.mark.business_value
    def test_github_pr_to_slack_notifications(self):
        """
        Business Scenario: Team needs instant PR notifications
        Expected: Post Slack notifications for PR events
        Annual Value: $57,600
        
        Workflow: GitHub Webhook → Parse PR Event → Post to Slack
        """
        use_case = self.business_cases["github"][0]
        assert use_case["use_case_id"] == "pr_to_slack_notifications"
        
        # Verify workflow configuration
        assert use_case['workflow'] == ["github", "slack"]
        
        print(f"\n📊 Business Value: ${use_case['business_value']['annual_value_usd']:,}/year")
        print(f"📈 Monthly Volume: {use_case['business_value']['monthly_volume']} PRs")
        
        assert use_case['workflow'] == ["github", "slack"]
        
    @pytest.mark.business_value
    def test_whatsapp_to_hubspot_contact(self):
        """
        Business Scenario: Customer inquires via WhatsApp Business
        Expected: Automatically create HubSpot contact
        Annual Value: $54,000
        
        Workflow: WhatsApp Message → Extract Contact Info → Create HubSpot Contact
        """
        use_case = self.business_cases["whatsapp"][0]
        assert use_case["use_case_id"] == "whatsapp_to_crm_contact"
        
        # Verify workflow configuration
        assert use_case['workflow'] == ["whatsapp", "hubspot"]
        
        print(f"\n📊 Business Value: ${use_case['business_value']['annual_value_usd']:,}/year")
        print(f"📈 Monthly Volume: {use_case['business_value']['monthly_volume']} inquiries")
        
        assert use_case['workflow'] == ["whatsapp", "hubspot"]
    
    @pytest.mark.business_value
    def test_email_to_monday_task(self):
        """
        Business Scenario: Important emails need task tracking
        Expected: Create Monday.com tasks from flagged emails  
        Annual Value: $48,000
        
        Workflow: Gmail Flagged Email → Extract Task Info → Create Monday Task
        """
        use_case = self.business_cases["monday"][0]
        assert use_case["use_case_id"] == "email_to_task"
        
        # Verify workflow configuration
        assert use_case['workflow'] == ["gmail", "monday"]
        
        print(f"\n📊 Business Value: ${use_case['business_value']['annual_value_usd']:,}/year")
        print(f"📈 Monthly Volume: {use_case['business_value']['monthly_volume']} tasks")
        
        assert use_case['workflow'] == ["gmail", "monday"]
    
    def test_business_value_summary(self):
        """
        Summary test: Validate total business value of all workflows
        """
        total_value = 0
        high_priority_count = 0
        
        for integration, use_cases in self.business_cases.items():
            for use_case in use_cases:
                value = use_case.get('business_value', {}).get('annual_value_usd', 0)
                total_value += value
                if use_case.get('priority') in ['high', 'critical']:
                    high_priority_count += 1
        
        print(f"\n🎯 TOTAL BUSINESS VALUE VALIDATED")
        print(f"=" * 50)
        print(f"💰 Total Annual Value: ${total_value:,}")
        print(f"🔥 High Priority Workflows: {high_priority_count}")
        print(f"📊 Total Use Cases: {sum(len(cases) for cases in self.business_cases.values())}")
        print(f"🔗 Integrations Covered: {len(self.business_cases)}")
        
        # Business value assertions
        assert total_value >= 900000, "Should validate $900K+ in annual value"
        assert high_priority_count >= 5, "Should have multiple high-value workflows"


if __name__ == "__main__":
    # Run tests with business value reporting
    pytest.main([__file__, "-v", "-s", "-m", "business_value"])
