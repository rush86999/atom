"""
BugReport data model for unified bug discovery pipeline.

This module provides the normalized BugReport Pydantic model that all
discovery methods (fuzzing, chaos, property, browser) convert their
results to for unified aggregation, deduplication, and reporting.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class DiscoveryMethod(str, Enum):
    """Discovery method types."""
    FUZZING = "fuzzing"
    CHAOS = "chaos"
    PROPERTY = "property"
    BROWSER = "browser"


class Severity(str, Enum):
    """Bug severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class BugReport(BaseModel):
    """
    Normalized bug report from any discovery method.

    All discovery methods convert their results to BugReport objects
    for unified aggregation, deduplication, severity classification,
    and automated bug filing.
    """
    discovery_method: DiscoveryMethod
    test_name: str
    error_message: str
    error_signature: str = Field(..., description="SHA256 hash for deduplication")
    severity: Severity = Field(default=Severity.LOW)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Optional fields
    stack_trace: Optional[str] = None
    screenshot_path: Optional[str] = None
    log_path: Optional[str] = None
    reproduction_steps: Optional[str] = None

    # Deduplication tracking
    duplicate_count: int = Field(default=1, description="Number of duplicate bugs found")

    class Config:
        """Pydantic config."""
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

    def get_severity_score(self) -> int:
        """Get numeric severity score for sorting (4=critical, 3=high, 2=medium, 1=low)."""
        scores = {Severity.CRITICAL: 4, Severity.HIGH: 3, Severity.MEDIUM: 2, Severity.LOW: 1}
        return scores.get(self.severity, 1)


def generate_error_signature(content: str) -> str:
    """
    Generate SHA256 hash for error deduplication.

    Args:
        content: Content to hash (stack trace, error message, metrics)

    Returns:
        SHA256 hex digest
    """
    import hashlib
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
