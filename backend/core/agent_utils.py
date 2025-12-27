
import re
import json
from typing import Dict, Any, Optional, Tuple

def parse_react_response(llm_output: str) -> Tuple[Optional[str], Optional[Dict[str, Any]], Optional[str]]:
    """
    Parse the LLM output to extract Thought, Action, and Final Answer.
    
    Expected Formats:
    
    Format 1 (JSON Action):
    Thought: I need to search for X.
    Action: {
        "tool": "tool_name",
        "params": { ... }
    }
    
    Format 2 (Final Answer):
    Thought: I have found the info.
    Final Answer: The answer is X.
    
    Returns:
        (thought_text, action_dict, final_answer_text)
    """
    # Normalize
    text = llm_output.strip()
    
    thought = None
    action = None
    final_answer = None
    
    # Extract Thought
    # Extract Thought
    # Lookahead for Action or Final Answer, allowing for whitespace/newlines
    thought_match = re.search(r"Thought:\s*(.*?)(?=\n\s*Action:|\n\s*Final Answer:|$)", text, re.DOTALL | re.IGNORECASE)
    if thought_match:
        thought = thought_match.group(1).strip()
    else:
        # If no explicit "Thought:", treat beginning as thought
        # But be careful if it starts with Action
        if not text.lower().strip().startswith("action:") and not text.lower().strip().startswith("final answer:"):
            # Try to grab everything until Action or Final Answer
            split_match = re.split(r"\n\s*Action:|\n\s*Final Answer:", text, flags=re.IGNORECASE)
            if split_match:
                thought = split_match[0].strip()

    # Extract Final Answer
    final_answer_match = re.search(r"Final Answer:\s*(.*)", text, re.DOTALL | re.IGNORECASE)
    if final_answer_match:
        final_answer = final_answer_match.group(1).strip()
        return thought, None, final_answer

    # Extract Action
    # Look for Action: ... json ...
    action_match = re.search(r"Action:\s*(.*)", text, re.DOTALL | re.IGNORECASE)
    if action_match:
        action_text = action_match.group(1).strip()
        
        # Try to find JSON blob in action text
        # Simple heuristic: find first { and last }
        try:
            json_start = action_text.find("{")
            json_end = action_text.rfind("}")
            
            if json_start != -1 and json_end != -1:
                json_str = action_text[json_start:json_end+1]
                action = json.loads(json_str)
            else:
                # Maybe it wasn't valid JSON, return as is or error?
                # For now, if we can't parse JSON, we treat it as an invalid action
                pass
        except json.JSONDecodeError:
            pass

    return thought, action, final_answer
