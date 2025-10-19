"""
NLU Bridge Service for TypeScript NLU Integration

This service provides a bridge between the Python backend and the TypeScript NLU system,
allowing workflow automation to properly go through the existing NLU agents.
"""

import asyncio
import aiohttp
import json
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class NLUAnalysisResult:
    """Result from TypeScript NLU analysis"""

    is_workflow_request: bool
    trigger: Optional[Dict[str, Any]]
    actions: List[Dict[str, Any]]
    primary_goal: Optional[str]
    extracted_parameters: Dict[str, Any]
    confidence: float


class NLUBridgeService:
    """
    Bridge service to connect Python workflow system with TypeScript NLU agents
    """

    def __init__(self, frontend_base_url: str = "http://localhost:3000"):
        self.frontend_base_url = frontend_base_url
        self.session = None

    async def initialize(self):
        """Initialize the HTTP session"""
        if self.session is None:
            self.session = aiohttp.ClientSession()

    async def close(self):
        """Close the HTTP session"""
        if self.session:
            await self.session.close()
            self.session = None

    async def analyze_workflow_request(
        self, user_input: str, user_id: str = "default"
    ) -> Optional[NLUAnalysisResult]:
        """
        Analyze a natural language workflow request using TypeScript NLU system

        Args:
            user_input: The natural language workflow request
            user_id: User identifier for context

        Returns:
            NLUAnalysisResult if successful, None if analysis fails
        """
        await self.initialize()

        try:
            # First, try to call the TypeScript NLU system via API
            nlu_result = await self._call_typescript_nlu(user_input, user_id)
            if nlu_result:
                return nlu_result

            # Fallback: Direct simulation of workflow agent logic
            logger.warning("TypeScript NLU API unavailable, using fallback simulation")
            return await self._simulate_workflow_agent_analysis(user_input)

        except Exception as e:
            logger.error(f"Error analyzing workflow request: {str(e)}")
            return None

    async def _call_typescript_nlu(
        self, user_input: str, user_id: str
    ) -> Optional[NLUAnalysisResult]:
        """
        Call the TypeScript NLU system via API endpoint

        This method attempts to call the existing TypeScript NLU agents
        through the frontend API endpoints.
        """
        try:
            # Try the NLU API endpoint
            async with self.session.post(
                f"{self.frontend_base_url}/api/agent/nlu",
                json={"message": user_input, "userId": user_id},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._parse_nlu_response(data)
                else:
                    logger.warning(f"NLU API returned status {response.status}")
                    return None

        except aiohttp.ClientError as e:
            logger.warning(f"NLU API unavailable: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error calling NLU API: {str(e)}")
            return None

    def _parse_nlu_response(
        self, nlu_data: Dict[str, Any]
    ) -> Optional[NLUAnalysisResult]:
        """
        Parse the response from TypeScript NLU system

        This method adapts the TypeScript NLU response format to our Python workflow system
        """
        try:
            # Extract workflow-specific information from NLU response
            raw_responses = nlu_data.get("rawSubAgentResponses", {})
            workflow_response = raw_responses.get("workflow", {})

            # Check if this is a workflow request
            is_workflow_request = workflow_response.get("isWorkflowRequest", False)

            if not is_workflow_request:
                return NLUAnalysisResult(
                    is_workflow_request=False,
                    trigger=None,
                    actions=[],
                    primary_goal=nlu_data.get("primaryGoal"),
                    extracted_parameters=nlu_data.get("extractedParameters", {}),
                    confidence=nlu_data.get("primaryGoalConfidence", 0.0),
                )

            # Extract workflow components
            trigger = workflow_response.get("trigger")
            actions = workflow_response.get("actions", [])

            return NLUAnalysisResult(
                is_workflow_request=True,
                trigger=trigger,
                actions=actions,
                primary_goal=nlu_data.get("primaryGoal"),
                extracted_parameters=nlu_data.get("extractedParameters", {}),
                confidence=nlu_data.get("primaryGoalConfidence", 0.0),
            )

        except Exception as e:
            logger.error(f"Error parsing NLU response: {str(e)}")
            return None

    async def _simulate_workflow_agent_analysis(
        self, user_input: str
    ) -> NLUAnalysisResult:
        """
        Simulate the TypeScript workflow agent analysis as fallback

        This provides basic workflow intent detection when the TypeScript NLU system
        is not available, but should be replaced with actual NLU calls in production.
        """
        # Simple pattern matching for common workflow phrases
        workflow_phrases = [
            "when",
            "if",
            "automatically",
            "workflow",
            "automation",
            "schedule",
            "trigger",
            "send",
            "create",
            "notify",
        ]

        user_input_lower = user_input.lower()
        is_workflow_like = any(
            phrase in user_input_lower for phrase in workflow_phrases
        )

        if not is_workflow_like:
            return NLUAnalysisResult(
                is_workflow_request=False,
                trigger=None,
                actions=[],
                primary_goal="General assistance",
                extracted_parameters={},
                confidence=0.3,
            )

        # Basic workflow intent detection
        trigger, actions = self._extract_basic_workflow_components(user_input)

        return NLUAnalysisResult(
            is_workflow_request=True,
            trigger=trigger,
            actions=actions,
            primary_goal="Create automated workflow",
            extracted_parameters={"user_input": user_input},
            confidence=0.7,
        )

    def _extract_basic_workflow_components(self, user_input: str) -> tuple:
        """
        Extract basic workflow components from natural language input

        This is a simplified version that should be replaced by the actual
        TypeScript workflow agent analysis.
        """
        trigger = None
        actions = []

        # Very basic trigger detection
        if "email" in user_input.lower():
            if "new" in user_input.lower() or "receive" in user_input.lower():
                trigger = {"service": "gmail", "event": "new_email"}

        elif "task" in user_input.lower() or "asana" in user_input.lower():
            if "new" in user_input.lower() or "create" in user_input.lower():
                trigger = {"service": "asana", "event": "new_task"}

        # Basic action detection
        if "send email" in user_input.lower() or "email" in user_input.lower():
            actions.append(
                {
                    "service": "email",
                    "action": "send_email",
                    "parameters": {
                        "subject": "Automated email",
                        "body": "Workflow triggered",
                    },
                }
            )

        if "create task" in user_input.lower() or "task" in user_input.lower():
            actions.append(
                {
                    "service": "asana",
                    "action": "create_task",
                    "parameters": {
                        "title": "Automated task",
                        "description": "Created by workflow",
                    },
                }
            )

        if "calendar" in user_input.lower() or "event" in user_input.lower():
            actions.append(
                {
                    "service": "calendar",
                    "action": "create_event",
                    "parameters": {
                        "title": "Automated event",
                        "description": "Created by workflow",
                    },
                }
            )

        return trigger, actions

    async def generate_workflow_from_nlu_analysis(
        self, nlu_result: NLUAnalysisResult
    ) -> Dict[str, Any]:
        """
        Generate a workflow definition from NLU analysis results

        This converts the NLU analysis into a workflow definition that can be
        executed by the workflow engine.
        """
        if not nlu_result.is_workflow_request:
            raise ValueError("NLU analysis does not indicate a workflow request")

        workflow_steps = []

        # Add trigger step if available
        if nlu_result.trigger:
            workflow_steps.append(
                {
                    "id": "trigger",
                    "type": "trigger",
                    "service": nlu_result.trigger.get("service"),
                    "event": nlu_result.trigger.get("event"),
                    "parameters": nlu_result.trigger.get("parameters", {}),
                }
            )

        # Add action steps
        for i, action in enumerate(nlu_result.actions):
            workflow_steps.append(
                {
                    "id": f"action_{i}",
                    "type": "action",
                    "service": action.get("service"),
                    "action": action.get("action"),
                    "parameters": action.get("parameters", {}),
                }
            )

        workflow_definition = {
            "name": f"Generated from: {nlu_result.primary_goal or 'Workflow'}",
            "description": f"Automatically generated workflow from user request",
            "trigger": nlu_result.trigger,
            "steps": workflow_steps,
            "enabled": True,
            "metadata": {
                "generated_by": "nlu_bridge",
                "confidence": nlu_result.confidence,
                "extracted_parameters": nlu_result.extracted_parameters,
            },
        }

        return workflow_definition


# Global instance for easy access
_nlu_bridge_service = None


async def get_nlu_bridge_service() -> NLUBridgeService:
    """Get or create the global NLU bridge service instance"""
    global _nlu_bridge_service
    if _nlu_bridge_service is None:
        _nlu_bridge_service = NLUBridgeService()
        await _nlu_bridge_service.initialize()
    return _nlu_bridge_service


async def close_nlu_bridge_service():
    """Close the global NLU bridge service"""
    global _nlu_bridge_service
    if _nlu_bridge_service:
        await _nlu_bridge_service.close()
        _nlu_bridge_service = None
