"""
P5 — Blueprint Security: credential sanitizer tests.

Sharing/forking never leaks credentials. These tests cover the
``core.blueprint_sanitizer`` module (recursive denylist stripping) plus the
workflow template EXPORT path, which must strip secrets before a template is
shared.

TDD: written against intended behaviour — they fail before the implementation
lands.
"""
import json
import shutil
import tempfile

import pytest

from core.blueprint_sanitizer import strip_credentials, has_credentials
from core.workflow_template_system import (
    WorkflowTemplateManager,
    TemplateCategory,
    TemplateComplexity,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_template_dir():
    """Create temporary directory for template storage."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def template_manager(temp_template_dir):
    """Template manager instance with temporary directory."""
    return WorkflowTemplateManager(template_dir=temp_template_dir)


@pytest.fixture
def sample_template_data():
    """Sample template data."""
    return {
        "name": "Test Template",
        "description": "Test description",
        "category": TemplateCategory.AUTOMATION,
        "complexity": TemplateComplexity.INTERMEDIATE,
        "tags": ["test"],
        "inputs": [
            {
                "name": "param1",
                "label": "Parameter 1",
                "type": "string",
                "required": False,
            }
        ],
        "steps": [
            {
                "id": "step_1",
                "name": "First Step",
                "description": "Initialize",
                "step_type": "agent_execution",
                "parameters": {},
                "depends_on": [],
            }
        ],
    }


# ============================================================================
# strip_credentials
# ============================================================================

class TestStripCredentials:
    """strip_credentials removes denylisted keys recursively, never mutating
    the input."""

    def test_strips_top_level_secret_key(self):
        obj = {"api_key": "sk-leaked", "name": "kept"}
        out = strip_credentials(obj)
        assert "api_key" not in out
        assert out["name"] == "kept"

    def test_strips_nested_secret_keys(self):
        obj = {
            "auth": {"access_token": "at-1", "refresh_token": "rt-1", "scope": "read"},
        }
        out = strip_credentials(obj)
        assert "access_token" not in out["auth"]
        assert "refresh_token" not in out["auth"]
        assert out["auth"]["scope"] == "read"

    def test_strips_secrets_inside_lists(self):
        obj = {"items": [{"secret": "s-1"}, {"password": "p-1", "keep": True}]}
        out = strip_credentials(obj)
        assert out["items"][0] == {}
        assert "password" not in out["items"][1]
        assert out["items"][1]["keep"] is True

    def test_strips_all_denylisted_key_forms_case_insensitive(self):
        obj = {
            "api_key": "1",
            "API_KEY": "2",
            "ACCESS_TOKEN": "3",
            "refresh_token": "4",
            "client_secret": "5",
            "super_secret_value": "6",
            "Password": "7",
        }
        assert strip_credentials(obj) == {}

    def test_leaves_non_secret_keys(self):
        obj = {
            "name": "x",
            "url": "https://example.com",
            "config": {"timeout": 30, "retries": 2},
        }
        assert strip_credentials(obj) == obj

    def test_returns_deep_copy_input_unchanged(self):
        obj = {"nested": {"api_key": "sk", "keep": [1, 2]}}
        out = strip_credentials(obj)
        assert "api_key" not in out["nested"]
        # Input is never mutated.
        assert "api_key" in obj["nested"]
        assert obj["nested"]["keep"] == [1, 2]
        # Output is a deep copy: mutating it must not affect the input.
        out["nested"]["keep"].append(3)
        assert obj["nested"]["keep"] == [1, 2]

    def test_handles_scalars_and_none(self):
        assert strip_credentials(None) is None
        assert strip_credentials(123) == 123
        assert strip_credentials("plain") == "plain"
        assert strip_credentials([1, "a", {"api_key": "x"}]) == [1, "a", {}]


# ============================================================================
# has_credentials
# ============================================================================

class TestHasCredentials:
    """has_credentials reports whether any denylisted key is present."""

    def test_detects_top_level_secret(self):
        assert has_credentials({"api_key": "x"}) is True

    def test_detects_nested_secret(self):
        assert has_credentials({"nested": {"secret": "y"}}) is True

    def test_detects_secret_inside_list(self):
        assert has_credentials({"items": [{"password": "z"}]}) is True

    def test_false_when_no_credentials(self):
        assert has_credentials({"name": "x", "items": [1, 2]}) is False
        assert has_credentials({}) is False


# ============================================================================
# Template EXPORT path redaction
# ============================================================================

class TestTemplateExportRedaction:
    """export_template must strip credentials from the shared payload."""

    def test_template_export_strips_secrets(self, template_manager, sample_template_data):
        created = template_manager.create_template(sample_template_data)

        # Inject credential-shaped keys into the template's output schema so
        # the export payload contains nested secrets.
        template = template_manager.get_template(created.template_id)
        template.output_schema = {
            "summary": {"text": "hello"},
            "api_key": "sk-leaked",
            "nested": {"access_token": "tok-leaked"},
        }

        exported = template_manager.export_template(created.template_id)

        assert exported["name"] == created.name
        # Non-secret content survives.
        assert exported["output_schema"]["summary"] == {"text": "hello"}
        # Secret keys are gone from the export payload.
        assert "api_key" not in exported["output_schema"]
        assert "access_token" not in exported["output_schema"]["nested"]
        # The export dict carries datetime objects, so serialize with default=str.
        payload = json.dumps(exported, default=str)
        assert "sk-leaked" not in payload
        assert "tok-leaked" not in payload

    def test_template_export_keeps_clean_payloads(self, template_manager, sample_template_data):
        created = template_manager.create_template(sample_template_data)
        exported = template_manager.export_template(created.template_id)
        # A clean template exports unchanged.
        assert exported["name"] == created.name
        assert exported["template_id"] == created.template_id
