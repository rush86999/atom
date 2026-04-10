"""
Base Learning Engine

Abstract interface for self-improving agent modules. Both MementoEngine
(skill generation) and AlphaEvolverEngine (skill optimization) implement
this interface, enabling a unified lifecycle:

    analyze_episode → propose_code_change → validate_change
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Protocol, runtime_checkable

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@runtime_checkable
class SandboxProtocol(Protocol):
    """
    Abstract sandbox interface for executing untrusted code.

    Upstream uses ContainerSandbox (Docker).
    SaaS implementations can inject SandboxExecutionService (Fly.io).
    """

    async def execute_raw_python(
        self,
        tenant_id: str,
        code: str,
        input_params: dict[str, Any],
        timeout: int = 60,
        safety_level: str = "MEDIUM_RISK",
        **kwargs,
    ) -> dict[str, Any]:
        """
        Execute raw Python code in an isolated sandbox.

        Returns:
            {
                "status": "success" | "failed",
                "output": str,
                "execution_seconds": float,
                "execution_id": str,
            }
        """
        ...


class BaseLearningEngine(ABC):
    """
    Unified interface for self-improving agent modules.

    Subclasses must implement three core lifecycle methods:
    1. analyze_episode — read and interpret execution data
    2. propose_code_change — generate a code modification
    3. validate_change — execute in sandbox and assess fitness
    """

    def __init__(
        self,
        db: Session,
        llm_service: Any | None = None,
        sandbox: SandboxProtocol | None = None,
    ):
        self.db = db
        self.llm = llm_service
        self.sandbox = sandbox

    @abstractmethod
    async def analyze_episode(self, episode_id: str, **kwargs) -> dict[str, Any]:
        """
        Read and interpret an episode's execution data.

        Returns a structured analysis dict containing:
        - task_description, error_trace, tool_calls (for failures)
        - latency, token_usage, edge_case_signals (for successes)
        """

    @abstractmethod
    async def propose_code_change(
        self, context: dict[str, Any], **kwargs
    ) -> str:
        """
        Generate a code modification proposal via LLM.

        Args:
            context: Analysis output from analyze_episode()

        Returns:
            Generated Python code string
        """

    @abstractmethod
    async def validate_change(
        self, code: str, test_inputs: list[dict[str, Any]], tenant_id: str, **kwargs
    ) -> dict[str, Any]:
        """
        Execute proposed code in sandbox and assess fitness.

        Returns:
            {
                "passed": bool,
                "proxy_signals": dict,
                "execution_result": dict,
            }
        """

    def _get_llm_service(self):
        """Get LLM service with graceful fallback."""
        if self.llm is not None:
            return self.llm

        try:
            from core.llm_service import get_llm_service

            self.llm = get_llm_service()
            return self.llm
        except Exception as e:
            logger.warning(
                f"LLM service unavailable — Auto-Dev features requiring LLM will be skipped: {e}"
            )
            return None

    def _get_sandbox(self):
        """Get sandbox with graceful fallback to ContainerSandbox."""
        if self.sandbox is not None:
            return self.sandbox

        try:
            from core.auto_dev.container_sandbox import ContainerSandbox

            self.sandbox = ContainerSandbox()
            return self.sandbox
        except Exception as e:
            logger.warning(f"Sandbox unavailable — validation will be skipped: {e}")
            return None

    def _strip_markdown_fences(self, code: str) -> str:
        """Strip markdown code fences from LLM output."""
        code = code.strip()
        if code.startswith("```python"):
            code = code[len("```python") :]
        elif code.startswith("```"):
            code = code[3:]
        if code.endswith("```"):
            code = code[:-3]
        return code.strip()
