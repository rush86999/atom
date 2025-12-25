
import asyncio
import sys
import os
from unittest.mock import MagicMock, patch

# Adjust path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def verify_phase_18():
    print("Verifying Phase 18: Scaling Real Service Execution...")

    # Mock token storage
    with patch("core.workflow_engine.token_storage") as mock_storage:
        mock_storage.get_token.return_value = {"access_token": "test-token", "instance_url": "https://test.salesforce.com"}
        
        # Mock services
        with patch("integrations.hubspot_service.hubspot_service") as mock_hubspot, \
             patch("integrations.salesforce_service.SalesforceService") as MockSfService, \
             patch("integrations.asana_service.asana_service") as mock_asana, \
             patch("integrations.discord_service.discord_service") as mock_discord, \
             patch("integrations.github_service.GitHubService") as MockGithubService, \
             patch("integrations.zoom_service.zoom_service") as mock_zoom, \
             patch("integrations.notion_service.NotionService") as MockNotionService:

            from core.workflow_engine import WorkflowEngine
            engine = WorkflowEngine()

            # 1. HubSpot Verification
            print("\n1. Verifying HubSpot Execution...")
            step = {
                "id": "step1",
                "service": "hubspot",
                "action": "create_contact",
                "parameters": {"email": "test@example.com", "firstname": "Test", "lastname": "User"},
                "connection_id": "conn_hubspot"
            }
            await engine._execute_step(step, step["parameters"])
            mock_hubspot.create_contact.assert_called_with(
                email="test@example.com", 
                first_name="Test", 
                last_name="User", 
                token="test-token"
            )
            print("✓ HubSpot create_contact called with token")

            # 2. Salesforce Verification
            print("\n2. Verifying Salesforce Execution...")
            mock_sf = MagicMock()
            MockSfService.return_value.create_client.return_value = mock_sf
            
            step = {
                "id": "step2",
                "service": "salesforce",
                "action": "create_lead",
                "parameters": {"lastname": "Lead", "company": "Co", "email": "lead@co.com"},
                "connection_id": "conn_sf"
            }
            await engine._execute_step(step, step["parameters"])
            MockSfService.return_value.create_client.assert_called_with("test-token", "https://test.salesforce.com")
            MockSfService.return_value.create_lead.assert_called_with(mock_sf, last_name="Lead", company="Co", email="lead@co.com")
            print("✓ Salesforce create_lead called with authenticated client")

            # 3. Asana Verification
            print("\n3. Verifying Asana Execution...")
            step = {
                "id": "step3",
                "service": "asana",
                "action": "create_task",
                "parameters": {"name": "Test Task", "workspace": "ws_123"},
                "connection_id": "conn_asana"
            }
            await engine._execute_step(step, step["parameters"])
            mock_asana.create_task.assert_called()
            args, _ = mock_asana.create_task.call_args
            assert args[0] == "test-token"
            assert args[1]["name"] == "Test Task"
            print("✓ Asana create_task called with token")

            # 4. Discord Verification
            print("\n4. Verifying Discord Execution...")
            step = {
                "id": "step4",
                "service": "discord",
                "action": "send_message",
                "parameters": {"channel_id": "123", "content": "Hello"},
                "connection_id": "conn_discord"
            }
            await engine._execute_step(step, step["parameters"])
            mock_discord.send_message.assert_called_with("123", "Hello", access_token="test-token", use_bot_token=False)
            print("✓ Discord send_message called with token")

            # 5. GitHub Verification
            print("\n5. Verifying GitHub Execution...")
            step = {
                "id": "step5",
                "service": "github",
                "action": "create_issue",
                "parameters": {"owner": "user", "repo": "repo", "title": "Bub", "body": "fix it"},
                "connection_id": "conn_github"
            }
            await engine._execute_step(step, step["parameters"])
            MockGithubService.assert_called_with(access_token="test-token")
            MockGithubService.return_value.create_issue.assert_called_with("user", "repo", "Bub", "fix it")
            print("✓ GitHub create_issue called with token")

            print("\nPhase 18 Verification Successful!")

if __name__ == "__main__":
    asyncio.run(verify_phase_18())
