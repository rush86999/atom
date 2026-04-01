"""
Pydantic v2 schemas for API request/response validation.

All API endpoints should use these schemas for type safety and validation.
"""

from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from enum import Enum

from core.validation import BaseModel as CustomBaseModel, sanitize_string, validated_string


class TenantContext(BaseModel):
    """Tenant context extracted from request."""
    tenant_id: str = Field(..., description="Tenant UUID")
    subdomain: Optional[str] = Field(None, description="Tenant subdomain")


class PaginationParams(BaseModel):
    """Pagination parameters for list endpoints."""
    limit: int = Field(default=50, ge=1, le=100, description="Items per page")
    offset: int = Field(default=0, ge=0, description="Items to skip")


class AgentCreateRequest(CustomBaseModel):
    """Schema for creating a new agent."""
    name: str = Field(..., min_length=1, max_length=100, description="Agent name")
    description: Optional[str] = Field(None, max_length=1000, description="Agent description")
    role: str = Field(..., min_length=1, max_length=50, description="Agent role")
    maturity_level: str = Field(default="student", pattern="^(student|intern|supervised|autonomous)$")
    status: Optional[str] = Field(None, pattern="^(student|intern|supervised|autonomous)$")
    capabilities: Optional[List[str]] = Field(default_factory=list)
    category: Optional[str] = Field(None, max_length=50)
    configuration: Optional[Dict[str, Any]] = Field(default_factory=dict)
    schedule_config: Optional[Dict[str, Any]] = Field(default_factory=dict)

    @field_validator('name', 'description')
    @classmethod
    def sanitize_fields(cls, v: Optional[str]) -> Optional[str]:
        if v:
            return sanitize_string(v, max_length=1000)
        return v


class AgentUpdateRequest(CustomBaseModel):
    """Schema for updating an agent."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    maturity_level: Optional[str] = Field(None, pattern="^(student|intern|supervised|autonomous)$")
    status: Optional[str] = Field(None, pattern="^(student|intern|supervised|autonomous)$")
    capabilities: Optional[List[str]] = Field(None)
    role: Optional[str] = Field(None, max_length=50)
    category: Optional[str] = Field(None, max_length=50)
    configuration: Optional[Dict[str, Any]] = Field(None)
    schedule_config: Optional[Dict[str, Any]] = Field(None)

    @field_validator('name', 'description')
    @classmethod
    def sanitize_fields(cls, v: Optional[str]) -> Optional[str]:
        if v:
            return sanitize_string(v, max_length=1000)
        return v


class CanvasComponentRequest(CustomBaseModel):
    """Schema for canvas component operations."""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    component_type: str = Field(..., min_length=1, max_length=50)
    code: Optional[str] = Field(None, max_length=50000)
    config: Optional[Dict[str, Any]] = Field(default_factory=dict)

    @field_validator('name', 'description')
    @classmethod
    def sanitize_fields(cls, v: Optional[str]) -> Optional[str]:
        if v:
            return sanitize_string(v, max_length=1000)
        return v

    @field_validator('code')
    @classmethod
    def sanitize_code(cls, v: Optional[str]) -> Optional[str]:
        # Code is handled separately but should be checked for length
        if v and len(v) > 50000:
            raise ValueError("Code exceeds maximum length")
        return v


class SkillCreateRequest(CustomBaseModel):
    """Schema for creating a new skill."""
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1, max_length=1000)
    skill_type: str = Field(..., pattern="^(http|python|javascript)$")
    config: Dict[str, Any] = Field(default_factory=dict)

    @field_validator('name', 'description')
    @classmethod
    def sanitize_fields(cls, v: str) -> str:
        return sanitize_string(v, max_length=1000)


class ChatRequest(CustomBaseModel):
    """Schema for chat requests."""
    message: str = Field(..., min_length=1, max_length=10000)
    session_id: Optional[str] = Field(None, max_length=100)
    user_id: str = Field(..., min_length=1, max_length=100)
    conversation_history: Optional[List[Dict[str, str]]] = Field(default_factory=list)

    @field_validator('message')
    @classmethod
    def sanitize_message(cls, v: str) -> str:
        return sanitize_string(v, max_length=10000, allow_html=False)


class FileUploadRequest(CustomBaseModel):
    """Schema for file upload metadata."""
    filename: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(..., min_length=1, max_length=100)
    size: int = Field(..., ge=1, le=100 * 1024 * 1024)  # Max 100MB

    @field_validator('filename')
    @classmethod
    def sanitize_filename(cls, v: str) -> str:
        from core.validation import sanitize_filename
        return sanitize_filename(v)


class ApiResponse(BaseModel):
    """Standard API response wrapper."""
    success: bool
    data: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PaginatedResponse(ApiResponse):
    """Paginated API response."""
    total: int = Field(..., ge=0)
    limit: int = Field(..., ge=1, le=100)
    offset: int = Field(..., ge=0)
    has_more: bool


# Error response schemas
class ErrorResponse(BaseModel):
    """Error response schema."""
    error: str = Field(..., description="Error message")
    code: str = Field(..., description="Error code")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(from_attributes=True)


class ValidationErrorResponse(ErrorResponse):
    """Validation error response."""
    code: str = "VALIDATION_ERROR"
    details: Dict[str, List[str]] = Field(..., description="Field-level validation errors")
