#!/usr/bin/env python3
"""
AI-powered natural language editing for workflow automation.
Integrates with BYOK (Bring Your Own Key) system for AI model selection.
"""

import json
import logging
import re
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from core.byok_endpoints import BYOKManager, get_byok_manager

logger = logging.getLogger(__name__)


@dataclass
class WorkflowEditOperation:
    """Represents a single edit operation on a workflow."""
    operation_type: str  # add_node, remove_node, update_node, add_connection, remove_connection, update_condition
    target_id: Optional[str] = None  # ID of node/connection being modified
    data: Optional[Dict[str, Any]] = None  # New data for the operation


@dataclass
class WorkflowEditPlan:
    """Plan containing multiple edit operations."""
    operations: List[WorkflowEditOperation]
    confidence: float
    reasoning: Optional[str] = None


class AINaturalLanguageEditor:
    """AI-powered natural language editor for workflows using BYOK AI models."""

    def __init__(self, byok_manager: Optional[BYOKManager] = None):
        self.byok_manager = byok_manager or get_byok_manager()

    async def parse_workflow_edit_command(
        self,
        command: str,
        workflow_context: Optional[Dict[str, Any]] = None
    ) -> WorkflowEditPlan:
        """
        Parse natural language command into workflow edit operations using AI.

        Args:
            command: Natural language command (e.g., "add a slack step that sends message to #general")
            workflow_context: Optional current workflow definition for context

        Returns:
            WorkflowEditPlan containing operations to perform
        """
        # First try AI parsing with BYOK
        try:
            return await self._ai_parse_command(command, workflow_context)
        except Exception as e:
            logger.warning(f"AI parsing failed: {e}. Falling back to rule-based parsing.")
            return self._rule_based_parse(command, workflow_context)

    async def _ai_parse_command(
        self,
        command: str,
        workflow_context: Optional[Dict[str, Any]] = None
    ) -> WorkflowEditPlan:
        """Parse command using AI via BYOK."""
        # Get optimal AI provider for NLP task
        try:
            provider_id = self.byok_manager.get_optimal_provider(
                task_type="general",  # Use "general" for workflow parsing
                min_reasoning_level=2  # Medium reasoning for workflow parsing
            )
        except ValueError as e:
            raise Exception(f"No suitable AI provider found: {e}")

        # Get provider configuration
        provider = self.byok_manager.providers.get(provider_id)
        if not provider:
            raise Exception(f"Provider {provider_id} not found in BYOK manager")

        # Get API key
        api_key = self.byok_manager.get_api_key(provider_id)
        if not api_key:
            raise Exception(f"No API key for provider {provider_id}")

        # Prepare prompt
        prompt = self._build_ai_prompt(command, workflow_context)
        system_prompt = self._get_system_prompt()

        # Call AI provider
        ai_response = await self._call_ai_provider(provider, api_key, prompt, system_prompt)

        # Parse response
        return self._parse_ai_response(ai_response)

    def _build_ai_prompt(
        self,
        command: str,
        workflow_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Build prompt for AI with command and workflow context."""
        prompt = f"""The user wants to edit a workflow. Here's their command:

"{command}"

"""
        if workflow_context:
            # Add workflow summary
            nodes = workflow_context.get('nodes', [])
            connections = workflow_context.get('connections', [])

            if nodes:
                prompt += "Current workflow nodes:\n"
                for node in nodes:
                    prompt += f"- {node.get('id')}: {node.get('type')} - {node.get('title')}\n"

            if connections:
                prompt += "\nCurrent connections:\n"
                for conn in connections:
                    prompt += f"- {conn.get('id')}: {conn.get('source')} -> {conn.get('target')}"
                    if conn.get('condition'):
                        prompt += f" (condition: {conn.get('condition')})"
                    prompt += "\n"

        prompt += """
Based on the command, generate a list of edit operations to modify the workflow.
Return your response as JSON with this structure:
{
    "operations": [
        {
            "operation_type": "add_node",
            "target_id": "optional_id_if_known",
            "data": {
                "type": "action",
                "title": "Descriptive title",
                "description": "Description",
                "config": {
                    "service": "slack",
                    "action": "send_message",
                    "parameters": {"channel": "#general", "message": "Hello"}
                },
                "position": {"x": 100, "y": 100}
            }
        }
    ],
    "confidence": 0.95,
    "reasoning": "Brief explanation"
}

Available operation types: add_node, remove_node, update_node, add_connection, remove_connection, update_condition
For new nodes, generate a unique target_id like "node_abc123".
If unsure about parameters, provide reasonable defaults.
"""
        return prompt

    def _get_system_prompt(self) -> str:
        """System prompt for AI model."""
        return """You are an expert workflow automation assistant. Convert natural language commands into precise workflow edit operations.
Understand workflow concepts: steps/nodes, connections, conditions, triggers, actions across services (Slack, Email, Asana, etc.).
Be specific and include necessary configuration. Respond with valid JSON."""

    async def _call_ai_provider(
        self,
        provider,
        api_key: str,
        prompt: str,
        system_prompt: str
    ) -> Dict[str, Any]:
        """Call AI provider API. Simplified version using OpenAI-compatible format."""
        import asyncio
        import aiohttp

        # Determine API endpoint based on provider
        provider_id = provider.id.lower()

        if provider_id == "openai":
            url = "https://api.openai.com/v1/chat/completions"
            model = provider.model or "gpt-4"
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        elif provider_id == "anthropic":
            url = "https://api.anthropic.com/v1/messages"
            model = provider.model or "claude-3-haiku-20240307"
            headers = {
                "x-api-key": api_key,
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01"
            }
        elif provider_id == "moonshot":
            url = provider.base_url or "https://api.moonshot.cn/v1/chat/completions"
            model = provider.model or "kimi-k2-thinking"
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        elif provider_id == "deepseek":
            url = "https://api.deepseek.com/v1/chat/completions"
            model = provider.model or "deepseek-chat"
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        else:
            # Generic OpenAI-compatible
            url = provider.base_url or "https://api.openai.com/v1/chat/completions"
            model = provider.model or "gpt-4"
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        # Prepare request data
        if provider_id == "anthropic":
            request_data = {
                "model": model,
                "max_tokens": 1000,
                "messages": [{"role": "user", "content": f"{system_prompt}\n\n{prompt}"}]
            }
        else:
            request_data = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 1000,
                "temperature": 0.3
            }

        # Make API call
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, headers=headers, json=request_data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"AI API error {response.status}: {error_text}")

                result = await response.json()

                # Extract content
                if provider_id == "anthropic":
                    content = result["content"][0]["text"]
                else:
                    content = result["choices"][0]["message"]["content"]

                # Parse JSON from content
                try:
                    # Remove markdown code blocks if present
                    if "```json" in content:
                        content = content.split("```json")[1].split("```")[0].strip()
                    elif "```" in content:
                        content = content.split("```")[1].split("```")[0].strip()

                    parsed = json.loads(content)
                    return parsed
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse JSON from AI response: {content[:200]}")
                    raise ValueError("AI response is not valid JSON")

    def _parse_ai_response(self, ai_response: Dict[str, Any]) -> WorkflowEditPlan:
        """Parse AI response into WorkflowEditPlan."""
        operations = []
        for op_data in ai_response.get("operations", []):
            operation = WorkflowEditOperation(
                operation_type=op_data.get("operation_type"),
                target_id=op_data.get("target_id"),
                data=op_data.get("data")
            )
            operations.append(operation)

        return WorkflowEditPlan(
            operations=operations,
            confidence=ai_response.get("confidence", 0.5),
            reasoning=ai_response.get("reasoning", "")
        )

    def _rule_based_parse(
        self,
        command: str,
        workflow_context: Optional[Dict[str, Any]] = None
    ) -> WorkflowEditPlan:
        """Fallback rule-based parsing (reuses existing regex patterns from workflow_endpoints.py)."""
        operations = []
        command_lower = command.lower()

        # Add step pattern (from workflow_endpoints.py)
        add_step_match = re.search(r'add (?:a |an )?(\w+) step', command_lower)
        if add_step_match:
            service = add_step_match.group(1)
            operation = WorkflowEditOperation(
                operation_type="add_node",
                data={
                    "type": "action",
                    "title": f"{service.capitalize()} Action",
                    "description": f"Added via natural language command: {command}",
                    "config": {
                        "service": service,
                        "action": "default",
                        "parameters": {}
                    },
                    "position": {"x": 100, "y": 100}
                }
            )
            operations.append(operation)

        # Remove step pattern
        remove_step_match = re.search(r'remove step (\w+)', command_lower)
        if remove_step_match:
            step_id = remove_step_match.group(1)
            operation = WorkflowEditOperation(
                operation_type="remove_node",
                target_id=step_id
            )
            operations.append(operation)

        # Update condition pattern
        update_condition_match = re.search(r'update condition (?:of )?connection (\w+) to (.+)', command_lower)
        if update_condition_match:
            connection_id = update_condition_match.group(1)
            new_condition = update_condition_match.group(2)
            operation = WorkflowEditOperation(
                operation_type="update_condition",
                target_id=connection_id,
                data={"condition": new_condition}
            )
            operations.append(operation)

        # Determine confidence based on whether we parsed anything
        confidence = 0.7 if operations else 0.2

        return WorkflowEditPlan(
            operations=operations,
            confidence=confidence,
            reasoning="Parsed using rule-based patterns"
        )

    async def apply_edit_plan(
        self,
        edit_plan: WorkflowEditPlan,
        workflow: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Apply edit plan to workflow definition.
        Returns modified workflow.
        """
        # Make a deep copy to avoid modifying original
        import copy
        modified_workflow = copy.deepcopy(workflow)

        for operation in edit_plan.operations:
            if operation.operation_type == "add_node":
                self._apply_add_node(operation, modified_workflow)
            elif operation.operation_type == "remove_node":
                self._apply_remove_node(operation, modified_workflow)
            elif operation.operation_type == "update_node":
                self._apply_update_node(operation, modified_workflow)
            elif operation.operation_type == "add_connection":
                self._apply_add_connection(operation, modified_workflow)
            elif operation.operation_type == "remove_connection":
                self._apply_remove_connection(operation, modified_workflow)
            elif operation.operation_type == "update_condition":
                self._apply_update_condition(operation, modified_workflow)

        return modified_workflow

    def _apply_add_node(self, operation: WorkflowEditOperation, workflow: Dict[str, Any]):
        """Add a new node to workflow."""
        node_id = operation.target_id or f"node_{str(uuid.uuid4())[:8]}"
        node_data = operation.data or {}

        node = {
            "id": node_id,
            "type": node_data.get("type", "action"),
            "title": node_data.get("title", "New Node"),
            "description": node_data.get("description", ""),
            "position": node_data.get("position", {"x": 100, "y": 100}),
            "config": node_data.get("config", {}),
            "connections": []
        }

        workflow.setdefault("nodes", []).append(node)

    def _apply_remove_node(self, operation: WorkflowEditOperation, workflow: Dict[str, Any]):
        """Remove a node from workflow."""
        if not operation.target_id:
            return

        # Remove node
        workflow["nodes"] = [n for n in workflow.get("nodes", []) if n.get("id") != operation.target_id]

        # Remove connections involving this node
        workflow["connections"] = [
            c for c in workflow.get("connections", [])
            if c.get("source") != operation.target_id and c.get("target") != operation.target_id
        ]

    def _apply_update_node(self, operation: WorkflowEditOperation, workflow: Dict[str, Any]):
        """Update node configuration."""
        if not operation.target_id:
            return

        for node in workflow.get("nodes", []):
            if node.get("id") == operation.target_id:
                if operation.data:
                    node.update(operation.data)
                break

    def _apply_add_connection(self, operation: WorkflowEditOperation, workflow: Dict[str, Any]):
        """Add a connection between nodes."""
        conn_id = operation.target_id or f"conn_{str(uuid.uuid4())[:8]}"
        conn_data = operation.data or {}

        connection = {
            "id": conn_id,
            "source": conn_data.get("source"),
            "target": conn_data.get("target"),
            "condition": conn_data.get("condition")
        }

        # Validate source and target exist
        source_exists = any(n.get("id") == connection["source"] for n in workflow.get("nodes", []))
        target_exists = any(n.get("id") == connection["target"] for n in workflow.get("nodes", []))

        if source_exists and target_exists:
            workflow.setdefault("connections", []).append(connection)
        else:
            logger.warning(f"Cannot add connection {conn_id}: source or target node not found")

    def _apply_remove_connection(self, operation: WorkflowEditOperation, workflow: Dict[str, Any]):
        """Remove a connection."""
        if not operation.target_id:
            return

        workflow["connections"] = [
            c for c in workflow.get("connections", []) if c.get("id") != operation.target_id
        ]

    def _apply_update_condition(self, operation: WorkflowEditOperation, workflow: Dict[str, Any]):
        """Update condition on a connection."""
        if not operation.target_id:
            return

        for conn in workflow.get("connections", []):
            if conn.get("id") == operation.target_id:
                if operation.data and "condition" in operation.data:
                    conn["condition"] = operation.data["condition"]
                break


# Global instance for convenience
_editor_instance = None

async def get_workflow_editor() -> AINaturalLanguageEditor:
    """Get or create global workflow editor instance."""
    global _editor_instance
    if _editor_instance is None:
        _editor_instance = AINaturalLanguageEditor()
    return _editor_instance