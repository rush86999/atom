import pytest
import asyncio
import sys
import os
sys.path.insert(0, os.path.abspath('.'))
from unittest.mock import patch, MagicMock, AsyncMock

from advanced_workflow_orchestrator import AdvancedWorkflowOrchestrator, WorkflowStatus

@pytest.mark.asyncio
async def test_autonomous_interview_scheduler_workflow():
    """
    Test the complete flow of the autonomous_interview_scheduler workflow.
    Mocks external API, NLU, Delay, Zoom, and Email to verify orchestrator pauses and resumes perfectly.
    """
    orchestrator = AdvancedWorkflowOrchestrator()
    workflow_id = "autonomous_interview_scheduler"
    
    assert workflow_id in orchestrator.workflows
    
    input_data = {
        "request_text": "Please schedule an interview for john.doe@example.com for the Frontend Engineer role with Alice and Bob."
    }
    
    with patch.object(orchestrator, '_execute_nlu_analysis', new_callable=AsyncMock) as mock_nlu, \
         patch.object(orchestrator, '_execute_api_call', new_callable=AsyncMock) as mock_api, \
         patch.object(orchestrator, '_execute_email_send', new_callable=AsyncMock) as mock_email, \
         patch.object(orchestrator, '_execute_delay', new_callable=AsyncMock) as mock_delay, \
         patch.object(orchestrator, '_execute_zoom_integration', new_callable=AsyncMock) as mock_zoom:
        
        # 1. extract_interview_request
        # 3. draft_proposal_email
        # 6. analyze_candidate_reply
        async def nlu_side_effect(*args, **kwargs):
            if mock_nlu.call_count == 1:
                return {
                    "status": "completed", 
                    "result": {
                        "candidate_email": "john.doe@example.com", 
                        "role": "Frontend Engineer", 
                        "interviewers": ["alice@company.com", "bob@company.com"]
                    }
                }
            elif mock_nlu.call_count == 2:
                return {
                    "status": "completed",
                    "result": "Hi John, please let us know which of these times work: Friday 10am, Friday 2pm."
                }
            return {
                "status": "completed",
                "result": {"selected_time": "Friday 10am"}
            }
            
        mock_nlu.side_effect = nlu_side_effect
        
        # 2. check_interviewer_availability
        # 8. send_calendar_invites
        async def api_side_effect(*args, **kwargs):
            if mock_api.call_count == 1:
                return {"status": "completed", "slots": ["Friday 10am", "Friday 2pm"]}
            return {"status": "completed", "message": "Invites sent to all attendees"}
            
        mock_api.side_effect = api_side_effect
        
        # 4. send_proposal_email
        async def email_result(*args, **kwargs):
            return {"status": "completed"}
        mock_email.side_effect = email_result
        
        # 5. wait_for_reply
        # We manually simulate the DELAY step pausing the workflow pending external async webhook
        async def delay_result(*args, **kwargs):
            return {"status": "waiting_approval", "message": "Paused waiting for candidate reply."}
        mock_delay.side_effect = delay_result
        
        # 7. generate_final_zoom_link
        async def zoom_result(*args, **kwargs):
            return {"status": "completed", "join_url": "https://zoom.us/j/interview_123"}
        mock_zoom.side_effect = zoom_result
        
        # Run workflow
        result = await orchestrator.execute_workflow(workflow_id, input_data)
        
        assert result.status == WorkflowStatus.WAITING_APPROVAL
        
        assert mock_nlu.call_count == 2
        assert mock_api.call_count == 1
        mock_email.assert_called_once()
        mock_delay.assert_called_once()
        mock_zoom.assert_not_called()
        
        execution_id = result.workflow_id
        # Webhook receives email, injects it into context, and calls resume
        orchestrator.active_contexts[execution_id].variables["candidate_reply_text"] = "Friday 10am works for me!"
        
        resume_result = await orchestrator.resume_workflow(execution_id, "wait_for_reply")
        
        assert resume_result.status == WorkflowStatus.COMPLETED
        assert mock_nlu.call_count == 3
        mock_zoom.assert_called_once()
        assert mock_api.call_count == 2
        print("Autonomous Interview Scheduler Test: PASSED")

if __name__ == "__main__":
    asyncio.run(test_autonomous_interview_scheduler_workflow())
