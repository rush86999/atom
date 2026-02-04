from typing import Any, Dict, List
from pydantic import BaseModel

from core.trajectory import ExecutionTrace, TraceStepType


class TraceMetrics(BaseModel):
    step_count: int
    duration_ms: float
    tool_calls: int
    step_efficiency: float
    hallucination_score: float # 0.0 to 1.0 (Low to High Risk)

class TraceValidator:
    def __init__(self):
        self.sensitive_tools = ["knowledge_query", "read_file", "search_web", "query_db"]

    def analyze_trace(self, trace: ExecutionTrace) -> TraceMetrics:
        steps = trace.steps
        tool_calls = [s for s in steps if s.type == TraceStepType.TOOL_CALL]
        
        # 1. Evidence Check (TRACE Framework)
        # If no tool calls but final result is complex, flag potential hallucination.
        # Simple heuristic: If request asks for "facts" or "file" and no tool called.
        hallucination_risk = 0.0
        
        request_lower = trace.request.lower()
        needs_evidence = any(k in request_lower for k in ["fact", "search", "find", "read", "file", "data"])
        
        has_evidence = len(tool_calls) > 0
        
        if needs_evidence and not has_evidence:
            hallucination_risk = 1.0 # High risk: Asked for data but didn't look for it
        
        # 2. Step Efficiency
        # Ideal steps: 1 thought + 1 tool call + 1 result + 1 final answer = 4 steps (very rough)
        # Or: Min necessary tool calls. If 0 tool calls, efficiency is 1.0 (if valid).
        # Let's say efficiency = 1 / (tool_calls + 1) to penalize looping?
        # User formula: Min Steps / Actual Steps.
        # We assume Min Steps = 1 (NLU only) or 2 (NLU + 1 Tool).
        min_steps = 1
        if needs_evidence:
            min_steps = 2
            
        # Calculation
        # Actual steps: We count 'cycles' (Tool Call + Result). 
        # But trace.steps is raw list.
        actual_steps = len(tool_calls) if len(tool_calls) > 0 else 1
        
        step_efficiency = min_steps / actual_steps
        if step_efficiency > 1.0: step_efficiency = 1.0
        
        return TraceMetrics(
            step_count=len(steps),
            duration_ms=trace.duration_ms(),
            tool_calls=len(tool_calls),
            step_efficiency=step_efficiency,
            hallucination_score=hallucination_risk
        )

    def validate_evidence(self, trace: ExecutionTrace) -> List[str]:
        """Return list of warnings based on evidence check"""
        warnings = []
        metrics = self.analyze_trace(trace)
        
        if metrics.hallucination_score > 0.5:
            warnings.append("HighHallucinationRisk: Request implies need for external data but no tool calls recorded.")
            
        if metrics.step_efficiency < 0.5:
            warnings.append(f"LowEfficiency: Agent took {metrics.tool_calls} steps where {metrics.step_efficiency * metrics.tool_calls} was expected.")
            
        return warnings
