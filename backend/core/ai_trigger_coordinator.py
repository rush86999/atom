"""
AI Universal Trigger Coordinator
Automatically evaluates ingested data and triggers specialty agents as needed.
This is distinct from user-defined workflow triggers - it's AI-driven.
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class DataCategory(Enum):
    """Categories of ingested data for agent matching"""
    FINANCE = "finance"
    SALES = "sales"
    OPERATIONS = "operations"
    HR = "hr"
    MARKETING = "marketing"
    LEGAL = "legal"
    SUPPORT = "support"
    GENERAL = "general"


class TriggerDecision(Enum):
    """Decision outcome from AI coordinator"""
    TRIGGER_AGENT = "trigger_agent"
    NO_ACTION = "no_action"
    QUEUE_FOR_REVIEW = "queue_for_review"


class AITriggerCoordinator:
    """
    Central AI coordinator that evaluates all ingested data
    and decides if specialty agents should be triggered.
    """
    
    # Keywords for category detection (simple heuristic, can be replaced with AI)
    CATEGORY_KEYWORDS = {
        DataCategory.FINANCE: [
            "invoice", "payment", "expense", "budget", "payroll", "tax", 
            "reconciliation", "ledger", "accounting", "revenue", "cost"
        ],
        DataCategory.SALES: [
            "lead", "opportunity", "deal", "pipeline", "prospect", "quote",
            "proposal", "contract", "customer", "crm", "revenue"
        ],
        DataCategory.OPERATIONS: [
            "inventory", "shipping", "order", "warehouse", "logistics",
            "supply chain", "vendor", "procurement", "stock"
        ],
        DataCategory.HR: [
            "employee", "onboarding", "leave", "payroll", "benefits",
            "hiring", "candidate", "performance", "review"
        ],
        DataCategory.MARKETING: [
            "campaign", "audience", "content", "social media", "email marketing",
            "analytics", "conversion", "engagement", "brand"
        ],
        DataCategory.LEGAL: [
            "contract", "agreement", "compliance", "regulation", "policy",
            "terms", "license", "nda", "legal"
        ],
        DataCategory.SUPPORT: [
            "ticket", "issue", "bug", "support", "help", "complaint",
            "resolution", "customer service"
        ]
    }
    
    # Map categories to specialty agent templates
    CATEGORY_TO_AGENT = {
        DataCategory.FINANCE: "finance_analyst",
        DataCategory.SALES: "sales_assistant",
        DataCategory.OPERATIONS: "ops_coordinator",
        DataCategory.HR: "hr_assistant",
        DataCategory.MARKETING: "marketing_analyst",
        DataCategory.LEGAL: None,  # No default agent yet
        DataCategory.SUPPORT: None,  # Could map to support agent
        DataCategory.GENERAL: None
    }
    
    def __init__(self, workspace_id: str = "default", user_id: str = None):
        self.workspace_id = workspace_id
        self.user_id = user_id
        self._enabled = None  # Lazy load from settings
    
    async def is_enabled(self) -> bool:
        """Check if AI auto-trigger is enabled for this user/workspace"""
        if self._enabled is not None:
            return self._enabled
        
        try:
            from core.user_preference_service import UserPreferenceService
            from core.database import SessionLocal
            
            with SessionLocal() as db:
                service = UserPreferenceService(db)
                pref = service.get_preference(
                    user_id=self.user_id or "system",
                    workspace_id=self.workspace_id,
                    key="ai_auto_trigger_enabled",
                    default=True
                )
                self._enabled = pref if isinstance(pref, bool) else True
                return self._enabled
        except Exception as e:
            logger.warning(f"Could not check AI trigger setting: {e}")
            return True  # Default to enabled
    
    async def evaluate_data(
        self, 
        data: Dict[str, Any], 
        source: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Evaluate ingested data and decide if an agent should be triggered.
        Uses Atom's memory (World Model) including agent experiences to make decisions.
        
        Args:
            data: The ingested data (could be document text, event payload, etc.)
            source: Source of the data (e.g., "gmail", "document_upload", "webhook")
            metadata: Additional context
            
        Returns:
            {
                "decision": TriggerDecision,
                "agent_template": str or None,
                "category": DataCategory,
                "confidence": float,
                "reasoning": str
            }
        """
        # 1. Check if feature is enabled
        if not await self.is_enabled():
            return {
                "decision": TriggerDecision.NO_ACTION.value,
                "agent_template": None,
                "category": DataCategory.GENERAL.value,
                "confidence": 0.0,
                "reasoning": "AI auto-trigger is disabled in user settings"
            }
        
        # 2. Extract text content for analysis
        text_content = self._extract_text(data)
        
        # 3. Classify the data category
        category, confidence = self._classify_category(text_content)
        
        # 4. Query World Model for relevant agent experiences
        memory_insights = await self._query_memory_for_insights(text_content, category)
        
        # 5. Adjust confidence based on memory insights
        confidence = self._adjust_confidence_with_memory(confidence, memory_insights)
        
        # 6. Decide on action (now memory-informed)
        decision, agent_template, reasoning = self._make_decision(
            category, confidence, source, metadata, memory_insights
        )
        
        result = {
            "decision": decision.value,
            "agent_template": agent_template,
            "category": category.value,
            "confidence": confidence,
            "reasoning": reasoning,
            "source": source,
            "memory_used": bool(memory_insights.get("experiences")),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # 7. If triggering, actually trigger the agent
        if decision == TriggerDecision.TRIGGER_AGENT and agent_template:
            await self._trigger_agent(agent_template, data, metadata, memory_insights)
        
        return result
    
    async def _query_memory_for_insights(
        self, 
        text_content: str, 
        category: DataCategory
    ) -> Dict[str, Any]:
        """
        Query Atom's World Model for relevant experiences and knowledge.
        Uses agent experiences to inform trigger decisions.
        """
        try:
            from core.agent_world_model import WorldModelService
            from core.models import AgentRegistry
            
            wm_service = WorldModelService(self.workspace_id)
            
            # Create a mock agent registry for the category to query experiences
            mock_agent = AgentRegistry(
                id=f"trigger_coordinator_{category.value}",
                name="Trigger Coordinator",
                category=category.value.capitalize()
            )
            
            # Query for similar past experiences
            memory_context = await wm_service.recall_experiences(
                agent=mock_agent,
                current_task_description=text_content[:500]
            )
            
            # Analyze experiences for success patterns
            experiences = memory_context.get("experiences", [])
            successful_experiences = [e for e in experiences if e.outcome == "Success"]
            failed_experiences = [e for e in experiences if e.outcome == "Failure"]
            
            return {
                "experiences": experiences,
                "success_count": len(successful_experiences),
                "failure_count": len(failed_experiences),
                "knowledge": memory_context.get("knowledge", []),
                "has_similar_history": len(experiences) > 0
            }
            
        except Exception as e:
            logger.warning(f"Failed to query World Model: {e}")
            return {"experiences": [], "success_count": 0, "failure_count": 0, "knowledge": []}
    
    def _adjust_confidence_with_memory(
        self, 
        base_confidence: float, 
        memory_insights: Dict[str, Any]
    ) -> float:
        """
        Adjust confidence score based on memory insights.
        Boost confidence if similar successful experiences exist.
        """
        adjusted = base_confidence
        
        # Boost if we have successful experience history
        if memory_insights.get("success_count", 0) > 0:
            boost = min(0.15, memory_insights["success_count"] * 0.05)
            adjusted += boost
            logger.debug(f"Confidence boosted by {boost:.2f} due to {memory_insights['success_count']} successful experiences")
        
        # Reduce if high failure rate
        if memory_insights.get("failure_count", 0) > memory_insights.get("success_count", 0):
            reduction = 0.1
            adjusted -= reduction
            logger.debug(f"Confidence reduced by {reduction:.2f} due to high failure rate")
        
        # Cap at 1.0
        return min(max(adjusted, 0.0), 1.0)
    
    def _extract_text(self, data: Dict[str, Any]) -> str:
        """Extract text content from various data formats"""
        if isinstance(data, str):
            return data
        
        # Try common text fields
        text_fields = ["text", "content", "body", "message", "description", "subject"]
        for field in text_fields:
            if field in data and isinstance(data[field], str):
                return data[field]
        
        # Fallback to string representation
        return str(data)
    
    def _classify_category(self, text: str) -> Tuple[DataCategory, float]:
        """
        Classify the text into a data category.
        Uses keyword matching (can be upgraded to AI classification).
        """
        text_lower = text.lower()
        
        category_scores = {}
        for category, keywords in self.CATEGORY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > 0:
                category_scores[category] = score
        
        if not category_scores:
            return DataCategory.GENERAL, 0.0
        
        # Find best match
        best_category = max(category_scores, key=category_scores.get)
        max_score = category_scores[best_category]
        
        # Normalize confidence (max 1.0)
        confidence = min(max_score / 3.0, 1.0)  # 3+ keywords = 100% confidence
        
        return best_category, confidence
    
    def _make_decision(
        self, 
        category: DataCategory, 
        confidence: float,
        source: str,
        metadata: Optional[Dict],
        memory_insights: Dict[str, Any] = None
    ) -> Tuple[TriggerDecision, Optional[str], str]:
        """
        Make the trigger decision based on classification and memory insights.
        """
        memory_insights = memory_insights or {}
        
        # Low confidence = no action
        if confidence < 0.3:
            return (
                TriggerDecision.NO_ACTION, 
                None, 
                f"Low confidence ({confidence:.2f}) for category {category.value}"
            )
        
        # Get agent template for this category
        agent_template = self.CATEGORY_TO_AGENT.get(category)
        
        if not agent_template:
            return (
                TriggerDecision.NO_ACTION,
                None,
                f"No agent template configured for category {category.value}"
            )
        
        # Medium confidence = queue for review (optional, can be strict)
        # BUT if we have successful memory history, boost to trigger
        if confidence < 0.5:
            if memory_insights.get("success_count", 0) > 2:
                return (
                    TriggerDecision.TRIGGER_AGENT,
                    agent_template,
                    f"Medium confidence ({confidence:.2f}) but strong success history ({memory_insights['success_count']} successes). Triggering {agent_template}."
                )
            return (
                TriggerDecision.QUEUE_FOR_REVIEW,
                agent_template,
                f"Medium confidence ({confidence:.2f}). Agent {agent_template} suggested but requires review."
            )
        
        # High confidence = trigger
        mem_note = f" (memory-informed: {memory_insights.get('success_count', 0)} successes)" if memory_insights.get("has_similar_history") else ""
        return (
            TriggerDecision.TRIGGER_AGENT,
            agent_template,
            f"High confidence ({confidence:.2f}). Triggering {agent_template} for {category.value} data.{mem_note}"
        )
    
    async def _trigger_agent(
        self, 
        agent_template: str, 
        data: Dict[str, Any],
        metadata: Optional[Dict],
        memory_insights: Dict[str, Any] = None
    ):
        """
        Actually trigger the specialty agent.
        Uses Atom Meta-Agent to spawn and execute.
        """
        try:
            from core.atom_meta_agent import get_atom_agent, AgentTriggerMode
            
            atom = get_atom_agent(self.workspace_id)
            
            # Spawn the agent
            agent = await atom.spawn_agent(agent_template, persist=False)
            
            # Build request from data
            text_content = self._extract_text(data)[:500]
            request = f"Auto-triggered by data ingestion. Process: {text_content}"
            
            # Execute
            result = await atom.execute(
                request=request,
                context={
                    "auto_triggered": True,
                    "source_data": data,
                    "metadata": metadata
                },
                trigger_mode=AgentTriggerMode.DATA_EVENT
            )
            
            logger.info(f"AI Coordinator triggered agent {agent_template}: {result.get('final_output', 'OK')}")
            
        except Exception as e:
            logger.error(f"Failed to trigger agent {agent_template}: {e}")


# ==================== INTEGRATION HOOKS ====================

async def on_data_ingested(
    data: Dict[str, Any],
    source: str,
    workspace_id: str = "default",
    user_id: str = None,
    metadata: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Hook to be called after any data ingestion.
    Evaluates data and triggers agents as needed.
    """
    coordinator = AITriggerCoordinator(workspace_id, user_id)
    return await coordinator.evaluate_data(data, source, metadata)


# Singleton for easy access
_coordinator_instance: Optional[AITriggerCoordinator] = None

def get_ai_trigger_coordinator(workspace_id: str = "default") -> AITriggerCoordinator:
    global _coordinator_instance
    if _coordinator_instance is None or _coordinator_instance.workspace_id != workspace_id:
        _coordinator_instance = AITriggerCoordinator(workspace_id)
    return _coordinator_instance
