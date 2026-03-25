"""CrossPlatformCorrelation data model for multi-platform bug correlation."""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum


class Platform(str, Enum):
    """Platform types for bug correlation."""
    WEB = "web"
    MOBILE = "mobile"
    DESKTOP = "desktop"


class CrossPlatformCorrelation(BaseModel):
    """
    Cross-platform bug correlation result.

    Represents bugs that manifest across multiple platforms,
    providing similarity scores and remediation suggestions.
    """
    # Correlation metadata
    correlation_id: str = Field(..., description="Unique correlation ID")
    platforms: List[Platform] = Field(..., description="Platforms where bug manifests")
    similarity_score: float = Field(..., description="Cross-platform similarity (0.0-1.0)", ge=0.0, le=1.0)

    # Bug details
    error_signature: str = Field(..., description="Normalized error signature")
    api_endpoint: Optional[str] = Field(None, description="Shared API endpoint if applicable")
    error_messages: Dict[str, str] = Field(..., description="Error message by platform")

    # Bug reports
    bug_reports: List[str] = Field(..., description="Bug report IDs/test names by platform")

    # Remediation
    suggested_action: str = Field(..., description="Suggested remediation action")
    shared_root_cause: bool = Field(default=False, description="Confirmed shared root cause")

    # Metadata
    timestamp: str = Field(..., description="Correlation timestamp")
    temporal_proximity_hours: Optional[float] = Field(None, description="Time difference in hours")

    class Config:
        use_enum_values = True
