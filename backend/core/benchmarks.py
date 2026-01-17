"""
Curated Quality Scores for AI Models
Normalized 0-100 scale based on MMLU, GSM8K, HumanEval, and LMSYS Chatbot Arena.
Used for "Benchmark-Price-Capability" (BPC) routing logic.
"""

# Quality scores (0-100) - Updated Jan 2026
MODEL_QUALITY_SCORES = {
    # absolute frontier (early 2026)
    "gemini-3-pro": 100,
    "gpt-5.2": 100,
    "gpt-5": 99,
    "o3": 99,
    "claude-4-opus": 99,
    "claude-3.5-opus": 97, # older opus
    "o4-mini": 96,
    "deepseek-r2": 97,
    "deepseek-v3.2-speciale": 99, # User Feedback: Frontier reasoning at low cost
    "qwen-3-max": 96,
    
    # High Reasoning / Complex
    "o3-mini": 94,
    "gpt-4.5": 95,
    "gemini-3-flash": 93,
    "deepseek-v3": 89, # demoted
    "deepseek-v3.2": 89, # demoted
    "qwen-2.5-72b-instruct": 88, # demoted
    "llama-4-70b": 92,
    "llama-3.3-70b-instruct": 89,
    
    # Balanced / Moderate
    "o1": 92, # demoted
    "deepseek-reasoner": 91, # demoted (R1)
    "gpt-4o": 90, # demoted
    "claude-3.5-sonnet": 92, # demoted
    "gpt-4o-mini": 85,
    "gemini-2.0-flash": 86,
    "gemini-1.5-flash": 84,
    
    # Efficiency / Simple
    "deepseek-chat": 80,
    "kimi-k1-5": 79,
    "qwen-3-7b": 82,
}

def get_quality_score(model_id: str) -> int:
    """
    Get the normalized quality score for a model.
    Falls back to heuristics if exact model_id is not in the map.
    """
    # Exact match
    if model_id in MODEL_QUALITY_SCORES:
        return MODEL_QUALITY_SCORES[model_id]
    
    # Partial match
    model_lower = model_id.lower()
    for key, score in MODEL_QUALITY_SCORES.items():
        if key.lower() in model_lower:
            return score
            
    # Heuristics for unknown models
    if "reasoner" in model_lower or "thinking" in model_lower or "-o1" in model_lower:
        return 95
    if "flash" in model_lower or "haiku" in model_lower or "mini" in model_lower:
        return 80
    if "70b" in model_lower or "72b" in model_lower:
        return 88
    if "8b" in model_lower or "7b" in model_lower:
        return 75
        
    return 70  # Default floor for unspecified models
