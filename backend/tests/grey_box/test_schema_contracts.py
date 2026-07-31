import pytest
from pydantic import ValidationError

# core.messaging_schemas was archived; skip gracefully instead of aborting
# collection of the entire grey_box directory.
pytest.importorskip("core.messaging_schemas", reason="core.messaging_schemas was archived")

from core.messaging_schemas import AgentMessage, TaskRequest


def test_schema_validation_success():
    """Test that valid data passes schema validation"""
    payload = {
        "user_id": "user123",
        "intent": "analyze_data",
        "input_data": {"text": "some data"}
    }
    task = TaskRequest(**payload)
    assert task.user_id == "user123"
    assert task.priority == "medium" # default

def test_schema_validation_missing_field():
    """Test that missing required field raises ValidatorError"""
    payload = {
        # "user_id": "user123", # MISSING
        "intent": "analyze_data",
        "input_data": {}
    }
    with pytest.raises(ValidationError) as excinfo:
        TaskRequest(**payload)
    assert "field required" in str(excinfo.value) or "user_id" in str(excinfo.value)

def test_schema_validation_empty_string():
    """Test custom validator for empty string"""
    payload = {
        "user_id": "", # EMPTY
        "intent": "analyze",
        "input_data": {}
    }
    with pytest.raises(ValidationError) as excinfo:
        TaskRequest(**payload)
    assert "user_id must not be empty" in str(excinfo.value)
