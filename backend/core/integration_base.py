"""
Base classes and schemas for Upstream Integration Services.
Simplified from SaaS to focus on functional node execution.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from enum import Enum
from pydantic import BaseModel, Field

class IntegrationErrorCode(str, Enum):
    INVALID_PARAMETERS = "INVALID_PARAMETERS"
    AUTH_EXPIRED = "AUTH_EXPIRED"
    NOT_FOUND = "NOT_FOUND"
    API_ERROR = "API_ERROR"
    TIMEOUT = "TIMEOUT"
    EXECUTION_EXCEPTION = "EXECUTION_EXCEPTION"
    LICENSE_RESTRICTED = "LICENSE_RESTRICTED"

class OperationResult(BaseModel):
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[IntegrationErrorCode] = None
    message: Optional[str] = None
    execution_time_ms: float = 0.0

class IntegrationService(ABC):
    """Abstract base class for all integration services in Upstream."""
    
    def __init__(self, workspace_id: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        self.workspace_id = workspace_id or "default"
        self.config = config or {}

    @abstractmethod
    async def execute_operation(
        self, 
        operation: str, 
        parameters: Dict[str, Any], 
        context: Optional[Dict[str, Any]] = None
    ) -> OperationResult:
        """Execute a specific operation on the integration."""
        pass

    @abstractmethod
    def get_supported_operations(self) -> List[str]:
        """Return list of supported operation names."""
        pass
