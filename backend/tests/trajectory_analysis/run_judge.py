import asyncio
import os
import sys
import json
import glob
from typing import Dict, Any

# Fix path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from core.trajectory import ExecutionTrace
from enhanced_ai_workflow_endpoints import RealAIWorkflowService

JUDGE_PROMPT = """You are an Expert AI Auditor. Review this execution trace found below.
Your goal is to evaluate the agent's reasoning process.

CRITERIA:
1. Did the agent blindly guess? (Hallucination check)
2. Did it loop unnecessarily? (Efficiency check)
3. Did it use the right tool for the request?

Trace Data:
{trace_json}

Return your assessment in this JSON format:
{
    "score": [1-5], // 5 is perfect reasoning
    "reasoning": "Explanation of score...",
    "fallacy_detected": "None" // or name of fallacy (e.g. Circular Reasoning, Unproven Premise)
}
"""

async def run_judge(trace_file: str):
    print(f"[JUDGE] Adjudicating Trace: {trace_file}")
    
    # Load Trace
    with open(trace_file, 'r') as f:
        data = json.load(f)
        trace = ExecutionTrace(**data) # Validate schema validation
    
    # Initialize Service to use GPT-4o (or best available)
    service = RealAIWorkflowService()
    await service.initialize_sessions()
    
    formatted_prompt = JUDGE_PROMPT.format(trace_json=json.dumps(data, indent=2))
    
    # Call Judge (Use OpenAI if available, else DeepSeek)
    try:
        if service.openai_api_key:
            response = await service.call_openai_api(formatted_prompt, system_prompt="You are an AI Judge.")
        else:
            print("[WARN] OpenAI Key missing, using generic analyze_text...")
            response = {"content": await service.analyze_text(formatted_prompt, complexity=3)}
            
        print("\n=== JUDGE'S VERDICT ===")
        print(response.get('content', 'No verdict'))
        
    finally:
        await service.cleanup_sessions()

if __name__ == "__main__":
    # improved: find latest trace
    files = glob.glob("logs/traces/*.json")
    if not files:
        print("No traces found in logs/traces/")
        sys.exit(1)
        
    latest_file = max(files, key=os.path.getctime)
    asyncio.run(run_judge(latest_file))
