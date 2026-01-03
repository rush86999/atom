import asyncio
import os
import sys
import glob
import json
from unittest.mock import MagicMock, patch, AsyncMock

# Fix path
sys.path.append(os.getcwd())

from enhanced_ai_workflow_endpoints import RealAIWorkflowService
from core.trace_validator import TraceValidator
from core.trajectory import ExecutionTrace
from tests.trajectory_analysis.run_judge import run_judge

async def main():
    try:
        print(">>> Starting Phase 2 Verification...")
        
        # Mock BYOK to avoid encryption key errors
        with patch('core.byok_endpoints.get_byok_manager') as mock_byok_get:
            mock_byok_manager = MagicMock()
            mock_byok_manager.get_api_key.return_value = "sk-mock-key"
            mock_byok_get.return_value = mock_byok_manager
            
            service = RealAIWorkflowService()
            await service.initialize_sessions()
            
            # Inject Mock Keys
            service.openai_api_key = service.openai_api_key or "sk-mock-openai"
            service.anthropic_api_key = service.anthropic_api_key or "sk-mock-anthropic"
            service.deepseek_api_key = service.deepseek_api_key or "sk-mock-deepseek"

            # Mock Responses
            mock_response = {
                'content': json.dumps({
                    "intent": "Answer question about France",
                    "workflow_suggestion": {},
                    "answer": "The capital of France is Paris.",
                    "confidence": 0.99
                }),
                'confidence': 0.99,
                'token_usage': {'total_tokens': 50},
                'provider': 'deepseek'
            }
            
            mock_judge_response = {
                 'content': json.dumps({
                    "score": 5,
                    "reasoning": "The agent correctly identified the intent and provided an answer.",
                    "fallacy_detected": "None"
                }),
                 'confidence': 1.0,
                 'provider': 'openai'
            }

            # Apply Class-level patches
            with patch('enhanced_ai_workflow_endpoints.RealAIWorkflowService.call_deepseek_api', new_callable=AsyncMock) as mock_deepseek, \
                 patch('enhanced_ai_workflow_endpoints.RealAIWorkflowService.call_openai_api', new_callable=AsyncMock) as mock_openai, \
                 patch('enhanced_ai_workflow_endpoints.RealAIWorkflowService.analyze_text', new_callable=AsyncMock) as mock_analyze:
                
                mock_deepseek.return_value = mock_response
                mock_openai.return_value = mock_judge_response
                mock_analyze.return_value = json.dumps({"score": 5, "reasoning": "Mock Judge", "fallacy_detected": "None"})
                
                try:
                    # 1. Generate Trace
                    print("\nStep 1: Generating Execution Trace...")
                    query = "What is the capital of France?"
                    
                    try:
                        result = await service.process_with_nlu(query, provider="deepseek")
                    except Exception as e:
                        print(f"[ERROR] NLU Processing Failed: {e}")
                        import traceback
                        traceback.print_exc()
                        return

                    print("NLU Result:", result.get("intent"))
                    
                    # 2. Find Trace
                    trace_id = result.get('trace_id')
                    if not trace_id:
                        print("[FAILURE]: No trace_id returned")
                        return
                    
                    print(f"[OK] Trace ID: {trace_id}")
                    latest_file = f"logs/traces/{trace_id}.json"
                    
                    # 3. Validate
                    print("\nStep 2: Running TRACE Validator...")
                    with open(latest_file, 'r') as f:
                        trace_data = json.load(f)
                        trace = ExecutionTrace(**trace_data)
                    
                    validator = TraceValidator()
                    metrics = validator.analyze_trace(trace)
                    warnings = validator.validate_evidence(trace)
                    
                    print(f"[METRICS] Efficiency={metrics.step_efficiency:.2f}")
                    if warnings: print("[WARN] Warnings:", warnings)
                    else: print("[OK] TRACE Validation Passed")
                        
                    # 4. Judge
                    print("\nStep 3: Summoning Judge...")
                    await run_judge(latest_file)
                    
                finally:
                    await service.cleanup_sessions()
    except Exception:
        print("CRITICAL CHECKPOINT FAILURE")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
