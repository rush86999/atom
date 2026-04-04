"""
Intent Classification Service for Meta-Agent Routing (Single-Tenant Version)

Three routing paths:
1. CHAT = Simple queries → LLMService (no task execution)
2. WORKFLOW = Structured complex tasks (blueprints, automatable) → QueenAgent
3. TASK = Long-horizon unstructured complex tasks → FleetAdmiral (dynamic agent recruitment)

Examples:
- CHAT: "Explain how agent maturity works"
- WORKFLOW: "Execute the sales outreach blueprint" (structured steps)
- TASK: "Research competitors and build a Slack integration" (unstructured, long-horizon)

**Single-Tenant Architecture**:
- Uses workspace_id instead of tenant_id
- No multi-tenant isolation

Ported from atom-saas
Changes: Replaced tenant_id with workspace_id, removed multi-tenancy
"""

import json
import logging
import os
from enum import Enum
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from core.llm_service import get_llm_service

logger = logging.getLogger(__name__)


class IntentCategory(str, Enum):
    """Categories for Meta-Agent routing decision"""
    CHAT = "chat"           # Simple query, no execution needed
    WORKFLOW = "workflow"   # Structured complex task with blueprint
    TASK = "task"           # Unstructured long-horizon complex task


@dataclass
class IntentClassification:
    """Result of intent classification"""
    category: IntentCategory
    confidence: float
    reasoning: str
    requires_execution: bool
    suggested_handler: str  # "llm_service", "queen_agent", or "fleet_admiral"
    
    # Additional context for routing
    is_structured: bool = False  # Has clear steps/structure
    is_long_horizon: bool = False  # Requires multiple phases
    requires_agent_recruitment: bool = False  # Needs multiple specialty agents
    blueprint_applicable: bool = False  # Can use workflow blueprint


class IntentClassifier:
    """
    Classifies user requests into CHAT/WORKFLOW/TASK categories
    for appropriate routing in AtomMetaAgent.
    """
    
    # Classification prompts for LLM
    CLASSIFICATION_PROMPT = """You are an intent classifier for the ATOM AI agent platform.

Classify the user's request into one of three categories:

1. **CHAT** - Simple queries that only need an LLM response (no task execution)
   - Examples: "Explain how agent maturity works", "What is the weather?", "Tell me a joke"
   - Characteristics: Informational, no action needed, single-turn response

2. **WORKFLOW** - Structured complex tasks that can be automated with blueprints
   - Examples: "Execute the sales outreach blueprint", "Run the monthly report automation"
   - Characteristics: Has clear steps, repeatable, structured process, automatable

3. **TASK** - Long-horizon unstructured complex tasks requiring dynamic agent recruitment
   - Examples: "Research competitors and build a Slack integration", "Analyze our sales data and create a marketing strategy"
   - Characteristics: Multi-phase, requires reasoning/adaptation, needs multiple specialty agents

Classification Criteria:
- If request needs NO execution → CHAT
- If request has STRUCTURED steps → WORKFLOW
- If request is UNSTRUCTURED + complex → TASK

User Request: "{user_request}"

Respond in JSON format:
{{
    "category": "chat|workflow|task",
    "confidence": 0.0-1.0,
    "reasoning": "Brief explanation",
    "is_structured": true/false,
    "is_long_horizon": true/false,
    "requires_agent_recruitment": true/false,
    "blueprint_applicable": true/false
}}
"""

    def __init__(self, db=None, workspace_id: str = "default"):
        self.db = db
        self.workspace_id = workspace_id
        self.llm = get_llm_service(db=db, workspace_id=workspace_id)

    async def classify_intent(self, user_request: str) -> IntentClassification:
        """
        Classify user request into CHAT/WORKFLOW/TASK category.

        Args:
            user_request: The user's natural language request

        Returns:
            IntentClassification with routing decision
        """
        try:
            # Use LLM for classification
            classification = await self._llm_classify(user_request)
            
            # Map to handler
            handler_map = {
                IntentCategory.CHAT: "llm_service",
                IntentCategory.WORKFLOW: "queen_agent",
                IntentCategory.TASK: "fleet_admiral"
            }
            
            return IntentClassification(
                category=classification["category"],
                confidence=classification["confidence"],
                reasoning=classification["reasoning"],
                requires_execution=classification["category"] != IntentCategory.CHAT,
                suggested_handler=handler_map[classification["category"]],
                is_structured=classification.get("is_structured", False),
                is_long_horizon=classification.get("is_long_horizon", False),
                requires_agent_recruitment=classification.get("requires_agent_recruitment", False),
                blueprint_applicable=classification.get("blueprint_applicable", False)
            )
            
        except Exception as e:
            logger.warning(f"LLM classification failed, using heuristics: {e}")
            # Fallback to heuristic classification
            return self._heuristic_classify(user_request)

    async def _llm_classify(self, user_request: str) -> Dict[str, Any]:
        """Use LLM to classify intent"""
        prompt = self.CLASSIFICATION_PROMPT.format(user_request=user_request)
        
        response = await self.llm.call(
            user_id=self.workspace_id,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1  # Low temperature for consistent classification
        )
        
        # Parse JSON response
        content = response.get("content", "{}")
        try:
            # Extract JSON from response (may have markdown formatting)
            json_str = content
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0]
            
            result = json.loads(json_str.strip())
            
            # Validate and convert category
            category_str = result.get("category", "chat").lower()
            if category_str in ["chat", "general_query", "general"]:
                result["category"] = IntentCategory.CHAT
                result.setdefault("is_structured", False)
                result.setdefault("is_long_horizon", False)
                result.setdefault("requires_agent_recruitment", False)
                result.setdefault("blueprint_applicable", False)
            elif category_str in ["workflow", "automation", "structured"]:
                result["category"] = IntentCategory.WORKFLOW
                result.setdefault("is_structured", True)
                result.setdefault("is_long_horizon", False)
                result.setdefault("requires_agent_recruitment", False)
                result.setdefault("blueprint_applicable", True)
            elif category_str in ["task", "agent_task", "unstructured"]:
                result["category"] = IntentCategory.TASK
                result.setdefault("is_structured", False)
                result.setdefault("is_long_horizon", True)
                result.setdefault("requires_agent_recruitment", True)
                result.setdefault("blueprint_applicable", False)
            else:
                result["category"] = IntentCategory.CHAT  # Default
                result.setdefault("is_structured", False)
                result.setdefault("is_long_horizon", False)
                result.setdefault("requires_agent_recruitment", False)
                result.setdefault("blueprint_applicable", False)

            return result
            
        except (json.JSONDecodeError, KeyError) as parse_err:
            logger.warning(f"Failed to parse LLM response: {parse_err}")
            # Return default classification with all fields
            return {
                "category": IntentCategory.CHAT,
                "confidence": 0.5,
                "reasoning": "Parse error, defaulting to CHAT",
                "is_structured": False,
                "is_long_horizon": False,
                "requires_agent_recruitment": False,
                "blueprint_applicable": False
            }

    def _heuristic_classify(self, user_request: str) -> IntentClassification:
        """
        Fallback heuristic classification when LLM unavailable.
        
        Uses keyword matching and request characteristics.
        """
        request_lower = user_request.lower()
        
        # CHAT indicators
        chat_keywords = [
            "explain", "what is", "how does", "tell me", "describe",
            "define", "what are", "who is", "when is", "where is"
        ]
        
        # WORKFLOW indicators
        workflow_keywords = [
            "execute", "run", "start workflow", "automation", "blueprint",
            "scheduled", "recurring", "repeat", "every day", "every week"
        ]
        
        # TASK indicators - complex unstructured tasks requiring multiple phases
        task_keywords = [
            "research", "analyze", "build", "create integration",
            "multi-step", "complex", "investigate", "explore",
            "strategy", "plan and", "design and"
        ]
        
        # Count matches
        chat_score = sum(1 for kw in chat_keywords if kw in request_lower)
        workflow_score = sum(1 for kw in workflow_keywords if kw in request_lower)
        task_score = sum(1 for kw in task_keywords if kw in request_lower)

        # Determine category
        max_score = max(chat_score, workflow_score, task_score)

        if max_score == 0 or chat_score == max_score:
            # Default to CHAT for simple queries
            return IntentClassification(
                category=IntentCategory.CHAT,
                confidence=0.6,
                reasoning="Heuristic: No strong workflow/task indicators",
                requires_execution=False,
                suggested_handler="llm_service",
                is_structured=False,
                is_long_horizon=False,
                requires_agent_recruitment=False,
                blueprint_applicable=False
            )
        elif workflow_score > task_score:
            return IntentClassification(
                category=IntentCategory.WORKFLOW,
                confidence=0.7,
                reasoning="Heuristic: Workflow keywords detected",
                requires_execution=True,
                suggested_handler="queen_agent",
                is_structured=True,
                is_long_horizon=False,
                requires_agent_recruitment=False,
                blueprint_applicable=True
            )
        else:
            return IntentClassification(
                category=IntentCategory.TASK,
                confidence=0.7,
                reasoning="Heuristic: Task keywords detected",
                requires_execution=True,
                suggested_handler="fleet_admiral",
                is_structured=False,
                is_long_horizon=True,
                requires_agent_recruitment=True,
                blueprint_applicable=False
            )


# Singleton instance helper
_intent_classifier_instance = None

def get_intent_classifier(db=None, workspace_id: str = "default") -> IntentClassifier:
    """Get or create IntentClassifier instance"""
    global _intent_classifier_instance
    if _intent_classifier_instance is None:
        _intent_classifier_instance = IntentClassifier(db, workspace_id)
    return _intent_classifier_instance
