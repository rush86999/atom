# -*- coding: utf-8 -*-
"""Coverage wave 91 — core/schemas (Pydantic v2 API schemas).

Pure in-memory pydantic validation — zero LLM spend, no network, no DB.

- TenantContext / PaginationParams: required fields, bounds (limit 1..100).
- AgentCreateRequest / AgentUpdateRequest / CanvasComponentRequest /
  SkillCreateRequest / ChatRequest / FileUploadRequest: valid payloads,
  sanitization (HTML strip, whitespace strip), defaults, extra=forbid,
  SQL-injection detection (core.validation CustomBaseModel), pattern
  enforcement, length limits, sanitize_filename path traversal.
- ApiResponse / PaginatedResponse: default UTC timestamp, field bounds.
- ErrorResponse: from_attributes config; ValidationErrorResponse default code.
"""
from datetime import timezone

import pytest
from pydantic import ValidationError

from core import schemas
from core.schemas import (
    AgentCreateRequest,
    AgentUpdateRequest,
    ApiResponse,
    CanvasComponentRequest,
    ChatRequest,
    ErrorResponse,
    FileUploadRequest,
    PaginatedResponse,
    PaginationParams,
    SkillCreateRequest,
    TenantContext,
    ValidationErrorResponse,
)


# ============================================================================
# TenantContext / PaginationParams
# ============================================================================

def test_tenant_context_required_and_optional():
    tc = TenantContext(tenant_id="t-1")
    assert tc.tenant_id == "t-1"
    assert tc.subdomain is None

    tc2 = TenantContext(tenant_id="t-1", subdomain="acme")
    assert tc2.subdomain == "acme"

    with pytest.raises(ValidationError):
        TenantContext()


def test_pagination_params_bounds():
    p = PaginationParams()
    assert p.limit == 50
    assert p.offset == 0

    p2 = PaginationParams(limit=100, offset=5)
    assert p2.limit == 100
    assert p2.offset == 5

    with pytest.raises(ValidationError):
        PaginationParams(limit=0)
    with pytest.raises(ValidationError):
        PaginationParams(limit=101)
    with pytest.raises(ValidationError):
        PaginationParams(offset=-1)


# ============================================================================
# AgentCreateRequest
# ============================================================================

def test_agent_create_valid_and_defaults():
    req = AgentCreateRequest(name="Support Agent", role="assistant")
    assert req.name == "Support Agent"
    assert req.maturity_level == "student"
    assert req.status is None
    assert req.capabilities == []
    assert req.configuration == {}
    assert req.schedule_config == {}
    assert req.description is None


def test_agent_create_sanitizes_and_forbids_extra():
    req = AgentCreateRequest(name="  <b>Agent</b>  ", role="r")
    assert req.name == "Agent"  # tags + whitespace stripped by sanitize_string

    with pytest.raises(ValidationError):
        AgentCreateRequest(name="x", role="r", unexpected_field=1)


def test_agent_create_sql_injection_rejected():
    from core.validation import ValidationError as CoreValidationError

    with pytest.raises(CoreValidationError):
        AgentCreateRequest(name="Robert'); DROP TABLE users;--", role="r")


def test_agent_create_constraints():
    with pytest.raises(ValidationError):
        AgentCreateRequest(name="", role="r")  # min_length 1
    with pytest.raises(ValidationError):
        AgentCreateRequest(name="x" * 101, role="r")  # max_length 100
    with pytest.raises(ValidationError):
        AgentCreateRequest(name="x", role="r", maturity_level="skynet")
    with pytest.raises(ValidationError):
        AgentCreateRequest(name="x")  # role required


# ============================================================================
# AgentUpdateRequest
# ============================================================================

def test_agent_update_all_optional_and_sanitized():
    req = AgentUpdateRequest()
    assert req.name is None

    req2 = AgentUpdateRequest(
        name="<b>renamed</b>", description="  desc  ",
        maturity_level="autonomous", capabilities=["a", "b"],
    )
    assert req2.name == "renamed"
    assert req2.description == "desc"
    assert req2.maturity_level == "autonomous"
    assert req2.capabilities == ["a", "b"]


def test_agent_update_invalid():
    with pytest.raises(ValidationError):
        AgentUpdateRequest(maturity_level="nope")
    with pytest.raises(ValidationError):
        AgentUpdateRequest(extra="x")
    with pytest.raises(ValidationError):
        AgentUpdateRequest(name="")  # min_length 1 when provided


# ============================================================================
# CanvasComponentRequest
# ============================================================================

def test_canvas_component_valid():
    req = CanvasComponentRequest(name="Chart", component_type="chart")
    assert req.name == "Chart"
    assert req.config == {}
    assert req.code is None


def test_canvas_component_sanitize_and_code_validation():
    req = CanvasComponentRequest(name="<em>Pie</em>", component_type="chart",
                                 code="<script>x()</script>")
    assert req.name == "Pie"
    assert req.code == "<script>x()</script>"  # code passes through untouched

    with pytest.raises(ValidationError):
        CanvasComponentRequest(name="c", component_type="t", code="x" * 50001)

    with pytest.raises(ValidationError):
        CanvasComponentRequest(name="c")  # component_type required

    with pytest.raises(ValidationError):
        CanvasComponentRequest(name="c", component_type="t", extra=1)


# ============================================================================
# SkillCreateRequest
# ============================================================================

def test_skill_create_valid_and_sanitized():
    req = SkillCreateRequest(name="  <i>web</i>  ", description=" d ", skill_type="python")
    assert req.name == "web"
    assert req.description == "d"
    assert req.config == {}


def test_skill_create_invalid():
    with pytest.raises(ValidationError):
        SkillCreateRequest(name="s", description="d", skill_type="ruby")
    with pytest.raises(ValidationError):
        SkillCreateRequest(name="s", skill_type="http")  # description required
    with pytest.raises(ValidationError):
        SkillCreateRequest(name="", description="d", skill_type="http")


# ============================================================================
# ChatRequest
# ============================================================================

def test_chat_request_valid_and_sanitized():
    req = ChatRequest(message="  hi <script>alert(1)</script>  ", user_id="u1")
    assert req.message == "hi alert(1)"  # allow_html=False strips tags, then .strip()
    assert req.session_id is None
    assert req.conversation_history == []


def test_chat_request_invalid():
    with pytest.raises(ValidationError):
        ChatRequest(message="", user_id="u1")
    with pytest.raises(ValidationError):
        ChatRequest(message="x" * 10001, user_id="u1")
    with pytest.raises(ValidationError):
        ChatRequest(message="hi", user_id="")  # min_length 1
    with pytest.raises(ValidationError):
        ChatRequest(message="hi")  # user_id required


# ============================================================================
# FileUploadRequest
# ============================================================================

def test_file_upload_valid_and_sanitized_filename():
    # ".." traversal is rejected by the base model validator before
    # sanitize_filename runs; sanitize_filename still strips path components
    # (forward/back slashes) and dangerous chars on valid input.
    req = FileUploadRequest(
        filename=r"dir\report<>.pdf", content_type="text/plain", size=1024
    )
    assert req.filename == "report.pdf"

    req2 = FileUploadRequest(filename="report.pdf", content_type="application/pdf",
                             size=100 * 1024 * 1024)
    assert req2.filename == "report.pdf"

    from core.validation import ValidationError as CoreValidationError

    with pytest.raises(CoreValidationError):
        FileUploadRequest(filename="../../etc/passwd", content_type="t", size=1)


def test_file_upload_invalid():
    with pytest.raises(ValidationError):
        FileUploadRequest(filename="f", content_type="t", size=0)
    with pytest.raises(ValidationError):
        FileUploadRequest(filename="f", content_type="t", size=100 * 1024 * 1024 + 1)
    with pytest.raises(ValidationError):
        FileUploadRequest(filename="", content_type="t", size=1)


# ============================================================================
# ApiResponse / PaginatedResponse
# ============================================================================

def test_api_response_defaults():
    resp = ApiResponse(success=True)
    assert resp.data is None
    assert resp.error is None
    assert resp.message is None
    assert resp.timestamp.tzinfo == timezone.utc


def test_paginated_response():
    resp = PaginatedResponse(success=True, total=10, limit=50, offset=0, has_more=True)
    assert resp.total == 10
    assert resp.has_more is True

    with pytest.raises(ValidationError):
        PaginatedResponse(success=True, total=-1, limit=50, offset=0, has_more=False)
    with pytest.raises(ValidationError):
        PaginatedResponse(success=True, total=1, limit=0, offset=0, has_more=False)
    with pytest.raises(ValidationError):
        PaginatedResponse(success=True, total=1, limit=50, offset=-1, has_more=False)


# ============================================================================
# ErrorResponse / ValidationErrorResponse
# ============================================================================

def test_error_response_and_from_attributes():
    resp = ErrorResponse(error="bad", code="E1")
    assert resp.details is None
    assert resp.timestamp.tzinfo == timezone.utc

    from types import SimpleNamespace

    attrs = ErrorResponse.model_validate(
        SimpleNamespace(error="attr-err", code="E2", details={"k": 1})
    )
    assert attrs.error == "attr-err"
    assert attrs.details == {"k": 1}


def test_validation_error_response_default_code():
    resp = ValidationErrorResponse(error="bad", details={"name": ["too short"]})
    assert resp.code == "VALIDATION_ERROR"
    assert resp.details == {"name": ["too short"]}

    with pytest.raises(ValidationError):
        ValidationErrorResponse(error="bad")  # details required


def test_empty_strings_hit_sanitizer_falsy_branch():
    req = AgentCreateRequest(name="x", role="r", description="")
    assert req.description == ""

    req2 = AgentUpdateRequest(description="")
    assert req2.description == ""

    req3 = CanvasComponentRequest(name="c", component_type="t", description="", code="")
    assert req3.description == ""
    assert req3.code == ""
