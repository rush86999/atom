#!/usr/bin/env python3
"""
Natural Language Time Expression Parser for ATOM
Converts human-readable time expressions into cron expressions or interval specifications
"""

from datetime import datetime, timedelta
import logging
import re
from typing import Any, Dict, Optional
from enhanced_ai_workflow_endpoints import RealAIWorkflowService

logger = logging.getLogger(__name__)

# Common time expression patterns
TIME_PATTERNS = {
    # Daily patterns
    r"(?:daily|every day)(?:\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?)?": {
        "type": "cron",
        "template": lambda h, m: f"{m or 0} {h} * * *"
    },
    
    # Hourly patterns
    r"every\s+(\d+)\s+hours?": {
        "type": "interval",
        "converter": lambda n: int(n) * 60
    },
    
    # Minute patterns
    r"every\s+(\d+)\s+minutes?": {
        "type": "interval", 
        "converter": lambda n: int(n)
    },
    
    # Weekday patterns
    r"(?:every\s+)?weekdays?(?:\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?)?": {
        "type": "cron",
        "template": lambda h, m: f"{m or 0} {h} * * 1-5"
    },
    
    # Weekend patterns
    r"(?:every\s+)?weekends?(?:\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?)?": {
        "type": "cron",
        "template": lambda h, m: f"{m or 0} {h} * * 0,6"
    },
    
    # Specific day patterns
    r"(?:every\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)s?(?:\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?)?": {
        "type": "cron",
        "day_map": {
            "monday": 1, "tuesday": 2, "wednesday": 3,
            "thursday": 4, "friday": 5, "saturday": 6, "sunday": 0
        },
        "template": lambda day, h, m: f"{m or 0} {h} * * {day}"
    },
    
    # Monthly patterns
    r"(?:on\s+the\s+)?first\s+day\s+of\s+(?:each|every|the)\s+month(?:\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?)?": {
        "type": "cron",
        "template": lambda h, m: f"{m or 0} {h} 1 * *"
    },
    
    r"(?:on\s+the\s+)?last\s+day\s+of\s+(?:each|every|the)\s+month(?:\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?)?": {
        "type": "cron",
        "template": lambda h, m: f"{m or 0} {h} L * *"  # Note: Some cron implementations support L for last day
    },
}


def normalize_time_12h_to_24h(hour: int, minute: int, period: Optional[str]) -> tuple:
    """Convert 12-hour time to 24-hour time"""
    if not period:
        return hour, minute
    
    period = period.lower()
    if period == "pm" and hour != 12:
        hour += 12
    elif period == "am" and hour == 12:
        hour = 0
    
    return hour, minute


def parse_with_patterns(expression: str) -> Optional[Dict[str, Any]]:
    """Try to parse using predefined patterns (fast path)"""
    expression = expression.lower().strip()
    
    for pattern, config in TIME_PATTERNS.items():
        match = re.search(pattern, expression)
        if match:
            groups = match.groups()
            
            if config["type"] == "interval":
                # Extract interval value
                interval_minutes = config["converter"](groups[0])
                return {
                    "schedule_type": "interval",
                    "interval_minutes": interval_minutes,
                    "human_readable": f"Every {interval_minutes} minutes" if interval_minutes < 60 else f"Every {interval_minutes // 60} hours",
                    "matched_text": match.group(0)
                }
            
            elif config["type"] == "cron":
                # Extract time components
                hour = 9  # Default to 9am
                minute = 0
                
                # Check if pattern has day mapping (for specific days)
                if "day_map" in config and groups[0]:
                    day_name = groups[0].lower()
                    day_num = config["day_map"][day_name]
                    
                    # Get time if specified
                    if len(groups) > 1 and groups[1]:
                        hour = int(groups[1])
                        minute = int(groups[2]) if groups[2] else 0
                        period = groups[3] if len(groups) > 3 else None
                        hour, minute = normalize_time_12h_to_24h(hour, minute, period)
                    
                    cron_expr = config["template"](day_num, hour, minute)
                    return {
                        "schedule_type": "cron",
                        "cron_expression": cron_expr,
                        "human_readable": f"Every {day_name.capitalize()} at {hour:02d}:{minute:02d}",
                        "matched_text": match.group(0)
                    }
                
                # Regular time-based patterns
                if groups[0] if isinstance(groups[0], int) else (groups[0] and groups[0].isdigit()):
                    hour = int(groups[0])
                    minute = int(groups[1]) if len(groups) > 1 and groups[1] else 0
                    period = groups[2] if len(groups) > 2 else None
                    hour, minute = normalize_time_12h_to_24h(hour, minute, period)
                
                cron_expr = config["template"](hour, minute)
                
                # Generate human readable
                if "weekday" in expression:
                    readable = f"Every weekday at {hour:02d}:{minute:02d}"
                elif "weekend" in expression:
                    readable = f"Every weekend at {hour:02d}:{minute:02d}"
                elif "daily" in expression or "every day" in expression:
                    readable = f"Every day at {hour:02d}:{minute:02d}"
                elif "first day" in expression:
                    readable = f"First day of each month at {hour:02d}:{minute:02d}"
                elif "last day" in expression:
                    readable = f"Last day of each month at {hour:02d}:{minute:02d}"
                else:
                    readable = f"At {hour:02d}:{minute:02d}"
                
                return {
                    "schedule_type": "cron",
                    "cron_expression": cron_expr,
                    "human_readable": readable,
                    "matched_text": match.group(0)
                }
    
    return None


async def parse_with_llm(expression: str, ai_service: RealAIWorkflowService) -> Optional[Dict[str, Any]]:
    """Use LLM to parse complex time expressions (slow path fallback)"""
    try:
        system_prompt = """You are a time expression parser. Convert natural language time expressions into scheduling formats.

Return a JSON object with:
{
    "schedule_type": "cron" | "interval" | "date",
    "cron_expression": "minute hour day month weekday" (if cron, use standard cron format),
    "interval_minutes": number (if interval),
    "run_date": "YYYY-MM-DD HH:MM:SS" (if specific date),
    "human_readable": "English description"
}

Examples:
- "every weekday at 9am" → {"schedule_type": "cron", "cron_expression": "0 9 * * 1-5", "human_readable": "Every weekday at 09:00"}
- "every 2 hours" → {"schedule_type": "interval", "interval_minutes": 120, "human_readable": "Every 2 hours"}
- "December 25 at 10am" → {"schedule_type": "date", "run_date": "2025-12-25 10:00:00", "human_readable": "December 25, 2025 at 10:00"}

IMPORTANT: Use 24-hour format. Monday=1, Sunday=0 in cron.
"""
        
        result = await ai_service.process_with_nlu(
            f"Parse this time expression: {expression}",
            provider="deepseek",
            system_prompt=system_prompt
        )
        
        # The result should contain the parsed schedule info
        if result and isinstance(result, dict):
            # Check if it has the expected fields
            if "schedule_type" in result:
                return result
            
        logger.warning(f"LLM parsing failed to return valid schedule format for: {expression}")
        return None
        
    except Exception as e:
        logger.error(f"LLM parsing failed for '{expression}': {e}")
        return None


async def parse_time_expression(
    expression: str,
    ai_service: RealAIWorkflowService
) -> Optional[Dict[str, Any]]:
    """
    Parse a natural language time expression into a schedule specification.
    
    Args:
        expression: Natural language time expression (e.g., "every weekday at 9am")
        ai_service: AI service instance for LLM fallback
    
    Returns:
        Dictionary with:
        - schedule_type: "cron", "interval", or "date"
        - cron_expression: Cron string (if cron type)
        - interval_minutes: Number of minutes (if interval type)
        - run_date: ISO datetime string (if date type)
        - human_readable: Human-friendly description
        
        Returns None if parsing fails
    """
    # Try pattern matching first (fast)
    result = parse_with_patterns(expression)
    if result:
        logger.info(f"Parsed '{expression}' using patterns: {result['human_readable']}")
        return result
    
    # Fall back to LLM (slow but handles complex cases)
    logger.info(f"Pattern matching failed for '{expression}', trying LLM...")
    result = await parse_with_llm(expression, ai_service)
    if result:
        logger.info(f"Parsed '{expression}' using LLM: {result.get('human_readable')}")
        return result
    
    logger.warning(f"Could not parse time expression: {expression}")
    return None
