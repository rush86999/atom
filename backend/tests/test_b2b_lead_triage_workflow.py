import pytest
import asyncio
import sys
import os
sys.path.insert(0, os.path.abspath('.'))
from unittest.mock import patch, MagicMock, AsyncMock

from advanced_workflow_orchestrator import AdvancedWorkflowOrchestrator, WorkflowStatus

@pytest.mark.asyncio
async def test_b2b_lead_triage_workflow_execution():
    """
    Test the complete flow of the b2b_lead_triage workflow.
    Mocks external NLU, Zoom, Zoho, and Governance to verify orchestration logic.
    """
    orchestrator = AdvancedWorkflowOrchestrator()
    workflow_id = "b2b_lead_triage"
    
    assert workflow_id in orchestrator.workflows
    
    input_data = {
        "email_subject": "Inquiry about Atom",
        "email_body": "Hi, we are interested in Atom. Do you support SAML SSO integration?",
        "from_email": "cto@example-startup.com"
    }
    
    # We will patch the individual _execute_* methods to simulate their effects without hitting real services.
    with patch.object(orchestrator, '_execute_nlu_analysis', new_callable=AsyncMock) as mock_nlu, \
         patch.object(orchestrator, '_execute_zoho_crm_integration', new_callable=AsyncMock) as mock_zoho, \
         patch.object(orchestrator, '_execute_conditional_logic', new_callable=AsyncMock) as mock_cond, \
         patch.object(orchestrator, '_execute_notion_search', new_callable=AsyncMock) as mock_notion, \
         patch.object(orchestrator, '_execute_zoom_integration', new_callable=AsyncMock) as mock_zoom, \
         patch.object(orchestrator, '_execute_approval_required_step', new_callable=AsyncMock) as mock_approval, \
         patch.object(orchestrator, '_execute_email_send', new_callable=AsyncMock) as mock_email:
        
        # 1. analyze_inbound_email
        async def nlu_side_effect(*args, **kwargs):
            if mock_nlu.call_count == 1:
                return {
                    "status": "completed", 
                    "result": {
                        "is_technical": True, 
                        "company_name": "Example Startup", 
                        "sender_name": "CTO", 
                        "tech_query": "Do you support SAML SSO integration?"
                    }
                }
            return {
                "status": "completed",
                "result": "Hello CTO, yes we support SAML SSO. Here is the link to discuss further: https://zoom.us/mock"
            }
            
        mock_nlu.side_effect = nlu_side_effect
        
        # 2. update_zoho_crm
        async def zoho_result(*args, **kwargs):
            return {"status": "completed", "result": {"id": "mock_lead_123"}}
        mock_zoho.side_effect = zoho_result
        
        # 3. check_technical
        async def cond_result(*args, **kwargs):
            return {"status": "completed", "next_steps": ["engineering_notion_search"]}
        mock_cond.side_effect = cond_result
        
        # 4. engineering_notion_search
        async def notion_result(*args, **kwargs):
            return {"status": "completed", "result": "Yes, Atom supports SAML SSO via Okta and Azure AD."}
        mock_notion.side_effect = notion_result
        
        # 5. generate_zoom_link
        async def zoom_result(*args, **kwargs):
            return {"status": "completed", "join_url": "https://zoom.us/j/mock_meeting"}
        mock_zoom.side_effect = zoom_result
        
        # 7. governance_check
        # Assume Student agent, requires approval handler
        async def approval_result(*args, **kwargs):
            if mock_approval.call_count == 1:
                return {
                    "status": "waiting_approval",
                    "hitl_action_id": "mock_hitl_999",
                    "message": "Requires human approval"
                }
            return {"status": "completed", "message": "Approved"}
        mock_approval.side_effect = approval_result
        
        # Execute workflow
        result = await orchestrator.execute_workflow(workflow_id, input_data)
        
        # Because governance_check returns 'waiting_approval', the orchestrator will set status to WAITING_APPROVAL
        assert result.status == WorkflowStatus.WAITING_APPROVAL
        
        # Verify the NLU step was called
        assert mock_nlu.call_count == 2
        mock_zoho.assert_called_once()
        mock_notion.assert_called_once()
        mock_zoom.assert_called_once()
        mock_approval.assert_called_once()
        mock_email.assert_not_called() # Email send shouldn't happen yet because it paused at approval
        
        execution_id = result.workflow_id
        
        # Mock Email Send success
        async def email_result(*args, **kwargs):
            return {"status": "completed"}
        mock_email.side_effect = email_result
        
        # Now simulate admin approval hitl resolution
        resume_result = await orchestrator.resume_workflow(execution_id, "governance_check")
        
        assert resume_result.status == WorkflowStatus.COMPLETED
        mock_email.assert_called_once()
        print("B2B Lead Triage Test: PASSED")

if __name__ == "__main__":
    asyncio.run(test_b2b_lead_triage_workflow_execution())
