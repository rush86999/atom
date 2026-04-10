"""
Test BaseLearningEngine abstract interface.

Tests cover:
- Abstract interface enforcement
- LLM service fallback
- Sandbox fallback
- Markdown stripping
- SandboxProtocol protocol
"""

import pytest
from unittest.mock import MagicMock, Mock

from core.auto_dev.base_engine import BaseLearningEngine, SandboxProtocol
from core.auto_dev.models import SkillCandidate


# =============================================================================
# Abstract Interface Tests
# =============================================================================

class TestBaseLearningEngineAbstractInterface:
    """Test BaseLearningEngine cannot be instantiated and enforces abstract methods."""

    def test_cannot_instantiate_base_learning_engine(self):
        """Test BaseLearningEngine cannot be instantiated directly."""
        from sqlalchemy.orm import Session

        db = MagicMock(spec=Session)

        with pytest.raises(TypeError):
            # Should raise TypeError: Can't instantiate abstract class
            BaseLearningEngine(db=db)

    def test_concrete_implementation_requires_all_abstract_methods(self):
        """Test concrete implementation must implement all abstract methods."""

        class IncompleteEngine(BaseLearningEngine):
            """Missing validate_change method."""

            async def analyze_episode(self, episode_id: str, **kwargs):
                return {"episode_id": episode_id}

            async def propose_code_change(self, context: dict, **kwargs):
                return "code"

        from sqlalchemy.orm import Session

        db = MagicMock(spec=Session)

        with pytest.raises(TypeError):
            # Should raise TypeError for missing abstract method
            IncompleteEngine(db=db)

    def test_complete_concrete_implementation_works(self):
        """Test complete concrete implementation can be instantiated."""

        class CompleteEngine(BaseLearningEngine):
            """Implements all abstract methods."""

            async def analyze_episode(self, episode_id: str, **kwargs):
                return {"episode_id": episode_id}

            async def propose_code_change(self, context: dict, **kwargs):
                return "def function(): pass"

            async def validate_change(self, code: str, test_inputs: list, tenant_id: str, **kwargs):
                return {"passed": True}

        from sqlalchemy.orm import Session

        db = MagicMock(spec=Session)
        llm = MagicMock()
        sandbox = MagicMock()

        engine = CompleteEngine(db=db, llm_service=llm, sandbox=sandbox)

        assert engine.db == db
        assert engine.llm == llm
        assert engine.sandbox == sandbox


# =============================================================================
# LLM Service Fallback Tests
# =============================================================================

class TestLLMServiceFallback:
    """Test _get_llm_service() with and without LLM available."""

    def test_returns_injected_llm_service(self):
        """Test _get_llm_service() returns injected LLM."""

        class TestEngine(BaseLearningEngine):
            async def analyze_episode(self, episode_id: str, **kwargs):
                return {}

            async def propose_code_change(self, context: dict, **kwargs):
                return "code"

            async def validate_change(self, code: str, test_inputs: list, tenant_id: str, **kwargs):
                return {"passed": True}

        from sqlalchemy.orm import Session

        db = MagicMock(spec=Session)
        llm = MagicMock()
        engine = TestEngine(db=db, llm_service=llm)

        result = engine._get_llm_service()

        assert result == llm

    def test_fallback_to_get_llm_service(self, monkeypatch):
        """Test fallback to get_llm_service() when None."""

        class TestEngine(BaseLearningEngine):
            async def analyze_episode(self, episode_id: str, **kwargs):
                return {}

            async def propose_code_change(self, context: dict, **kwargs):
                return "code"

            async def validate_change(self, code: str, test_inputs: list, tenant_id: str, **kwargs):
                return {"passed": True}

        from sqlalchemy.orm import Session

        db = MagicMock(spec=Session)

        # Mock get_llm_service
        mock_llm = MagicMock()
        mock_get_llm = Mock(return_value=mock_llm)

        # Use monkeypatch on the specific import
        import sys
        original_module = sys.modules.get("core.llm_service")

        class MockLLMService:
            pass

        MockLLMService.get_llm_service = staticmethod(mock_get_llm)
        sys.modules["core.llm_service"] = MockLLMService

        try:
            engine = TestEngine(db=db, llm_service=None)
            result = engine._get_llm_service()

            assert result == mock_llm
        finally:
            if original_module:
                sys.modules["core.llm_service"] = original_module
            else:
                sys.modules.pop("core.llm_service", None)

    def test_graceful_handling_when_llm_unavailable(self, caplog):
        """Test graceful handling when LLM unavailable."""

        class TestEngine(BaseLearningEngine):
            async def analyze_episode(self, episode_id: str, **kwargs):
                return {}

            async def propose_code_change(self, context: dict, **kwargs):
                return "code"

            async def validate_change(self, code: str, test_inputs: list, tenant_id: str, **kwargs):
                return {"passed": True}

        from sqlalchemy.orm import Session

        db = MagicMock(spec=Session)

        # Use monkeypatch to make import fail
        import sys
        original_module = sys.modules.get("core.llm_service")

        def mock_get_llm_service():
            raise ImportError("LLM service not available")

        class MockLLMService:
            get_llm_service = staticmethod(mock_get_llm_service)

        sys.modules["core.llm_service"] = MockLLMService

        try:
            engine = TestEngine(db=db, llm_service=None)
            result = engine._get_llm_service()

            assert result is None
        finally:
            if original_module:
                sys.modules["core.llm_service"] = original_module
            else:
                sys.modules.pop("core.llm_service", None)


# =============================================================================
# Sandbox Fallback Tests
# =============================================================================

class TestSandboxFallback:
    """Test _get_sandbox() with and without sandbox available."""

    def test_returns_injected_sandbox(self):
        """Test _get_sandbox() returns injected sandbox."""

        class TestEngine(BaseLearningEngine):
            async def analyze_episode(self, episode_id: str, **kwargs):
                return {}

            async def propose_code_change(self, context: dict, **kwargs):
                return "code"

            async def validate_change(self, code: str, test_inputs: list, tenant_id: str, **kwargs):
                return {"passed": True}

        from sqlalchemy.orm import Session

        db = MagicMock(spec=Session)
        sandbox = MagicMock()
        engine = TestEngine(db=db, sandbox=sandbox)

        result = engine._get_sandbox()

        assert result == sandbox

    def test_fallback_to_container_sandbox(self):
        """Test fallback to ContainerSandbox when None."""

        class TestEngine(BaseLearningEngine):
            async def analyze_episode(self, episode_id: str, **kwargs):
                return {}

            async def propose_code_change(self, context: dict, **kwargs):
                return "code"

            async def validate_change(self, code: str, test_inputs: list, tenant_id: str, **kwargs):
                return {"passed": True}

        from sqlalchemy.orm import Session

        db = MagicMock(spec=Session)
        engine = TestEngine(db=db, sandbox=None)

        result = engine._get_sandbox()

        # Should return a ContainerSandbox instance
        assert result is not None
        # Check it has execute_raw_python method
        assert hasattr(result, "execute_raw_python")

    def test_graceful_handling_when_sandbox_unavailable(self, caplog):
        """Test graceful handling when sandbox unavailable."""

        class TestEngine(BaseLearningEngine):
            async def analyze_episode(self, episode_id: str, **kwargs):
                return {}

            async def propose_code_change(self, context: dict, **kwargs):
                return "code"

            async def validate_change(self, code: str, test_inputs: list, tenant_id: str, **kwargs):
                return {"passed": True}

        from sqlalchemy.orm import Session

        db = MagicMock(spec=Session)

        # Use monkeypatch to make import fail
        import sys
        original_module = sys.modules.get("core.auto_dev.container_sandbox")

        def mock_container_sandbox():
            raise ImportError("ContainerSandbox not available")

        class MockModule:
            ContainerSandbox = property(lambda self: mock_container_sandbox())

        sys.modules["core.auto_dev.container_sandbox"] = MockModule()

        try:
            engine = TestEngine(db=db, sandbox=None)
            result = engine._get_sandbox()

            assert result is None
        finally:
            if original_module:
                sys.modules["core.auto_dev.container_sandbox"] = original_module
            else:
                sys.modules.pop("core.auto_dev.container_sandbox", None)


# =============================================================================
# Markdown Stripping Tests
# =============================================================================

class TestMarkdownStripping:
    """Test _strip_markdown_fences() removes code fences."""

    def test_strip_python_fences(self):
        """Test _strip_markdown_fences() removes ```python fences."""

        class TestEngine(BaseLearningEngine):
            async def analyze_episode(self, episode_id: str, **kwargs):
                return {}

            async def propose_code_change(self, context: dict, **kwargs):
                return "code"

            async def validate_change(self, code: str, test_inputs: list, tenant_id: str, **kwargs):
                return {"passed": True}

        from sqlalchemy.orm import Session

        db = MagicMock(spec=Session)
        engine = TestEngine(db=db)

        code = """```python
def hello():
    print("world")
```"""

        result = engine._strip_markdown_fences(code)

        assert result == 'def hello():\n    print("world")'
        assert "```" not in result
        assert "python" not in result

    def test_strip_generic_fences(self):
        """Test _strip_markdown_fences() removes ``` fences."""

        class TestEngine(BaseLearningEngine):
            async def analyze_episode(self, episode_id: str, **kwargs):
                return {}

            async def propose_code_change(self, context: dict, **kwargs):
                return "code"

            async def validate_change(self, code: str, test_inputs: list, tenant_id: str, **kwargs):
                return {"passed": True}

        from sqlalchemy.orm import Session

        db = MagicMock(spec=Session)
        engine = TestEngine(db=db)

        code = """```
def hello():
    print("world")
```"""

        result = engine._strip_markdown_fences(code)

        assert result == 'def hello():\n    print("world")'
        assert "```" not in result

    def test_preserves_code_content(self):
        """Test _strip_markdown_fences() preserves code content."""

        class TestEngine(BaseLearningEngine):
            async def analyze_episode(self, episode_id: str, **kwargs):
                return {}

            async def propose_code_change(self, context: dict, **kwargs):
                return "code"

            async def validate_change(self, code: str, test_inputs: list, tenant_id: str, **kwargs):
                return {"passed": True}

        from sqlalchemy.orm import Session

        db = MagicMock(spec=Session)
        engine = TestEngine(db=db)

        code = """```python
def process(data):
    result = []
    for item in data:
        result.append(item * 2)
    return result
```"""

        result = engine._strip_markdown_fences(code)

        assert "def process(data):" in result
        assert "result.append(item * 2)" in result
        assert "return result" in result
        assert "```" not in result

    def test_handles_no_fences(self):
        """Test _strip_markdown_fences() handles code without fences."""

        class TestEngine(BaseLearningEngine):
            async def analyze_episode(self, episode_id: str, **kwargs):
                return {}

            async def propose_code_change(self, context: dict, **kwargs):
                return "code"

            async def validate_change(self, code: str, test_inputs: list, tenant_id: str, **kwargs):
                return {"passed": True}

        from sqlalchemy.orm import Session

        db = MagicMock(spec=Session)
        engine = TestEngine(db=db)

        code = 'def hello():\n    print("world")'

        result = engine._strip_markdown_fences(code)

        assert result == code

    def test_handles_nested_fences(self):
        """Test _strip_markdown_fences() handles nested fences."""

        class TestEngine(BaseLearningEngine):
            async def analyze_episode(self, episode_id: str, **kwargs):
                return {}

            async def propose_code_change(self, context: dict, **kwargs):
                return "code"

            async def validate_change(self, code: str, test_inputs: list, tenant_id: str, **kwargs):
                return {"passed": True}

        from sqlalchemy.orm import Session

        db = MagicMock(spec=Session)
        engine = TestEngine(db=db)

        code = """```python
code = '''this has triple quotes inside'''
```"""

        result = engine._strip_markdown_fences(code)

        assert "```" not in result
        assert "code = '''this has triple quotes inside'''" in result

    def test_handles_leading_trailing_whitespace(self):
        """Test _strip_markdown_fences() handles leading/trailing whitespace."""

        class TestEngine(BaseLearningEngine):
            async def analyze_episode(self, episode_id: str, **kwargs):
                return {}

            async def propose_code_change(self, context: dict, **kwargs):
                return "code"

            async def validate_change(self, code: str, test_inputs: list, tenant_id: str, **kwargs):
                return {"passed": True}

        from sqlalchemy.orm import Session

        db = MagicMock(spec=Session)
        engine = TestEngine(db=db)

        code = """
```python
def hello():
    pass
```
"""

        result = engine._strip_markdown_fences(code)

        assert result.strip() == "def hello():\n    pass"
        assert result == result.strip()


# =============================================================================
# SandboxProtocol Tests
# =============================================================================

class TestSandboxProtocol:
    """Test SandboxProtocol is runtime_checkable and works with duck typing."""

    def test_sandbox_protocol_is_runtime_checkable(self):
        """Test SandboxProtocol is runtime_checkable."""

        # SandboxProtocol should be runtime_checkable
        assert hasattr(SandboxProtocol, "__protocol_attrs__")

    def test_isinstance_with_concrete_implementation(self):
        """Test isinstance() with concrete implementation."""
        from core.auto_dev.container_sandbox import ContainerSandbox

        sandbox = ContainerSandbox()

        # Should be recognized as SandboxProtocol
        assert isinstance(sandbox, SandboxProtocol)

    def test_mock_sandbox_as_protocol(self):
        """Test mock objects can be used as SandboxProtocol."""

        class MockSandbox:
            async def execute_raw_python(
                self,
                tenant_id: str,
                code: str,
                input_params: dict,
                timeout: int = 60,
                safety_level: str = "MEDIUM_RISK",
                **kwargs,
            ) -> dict:
                return {"status": "success", "output": "done"}

        mock = MockSandbox()

        # Should work as SandboxProtocol (duck typing)
        assert hasattr(mock, "execute_raw_python")

    def test_protocol_duck_typing(self):
        """Test protocol duck typing with any object having execute_raw_python."""

        class SomeOtherSandbox:
            async def execute_raw_python(self, **kwargs):
                return {"status": "success"}

        sandbox = SomeOtherSandbox()

        # Has the required method
        assert hasattr(sandbox, "execute_raw_python")

        # Can be used as sandbox
        async def test_func():
            return await sandbox.execute_raw_python(
                tenant_id="test",
                code="print('hello')",
                input_params={},
            )

        import asyncio
        result = asyncio.run(test_func())
        assert result["status"] == "success"


# =============================================================================
# Integration Tests
# =============================================================================

class TestBaseLearningEngineIntegration:
    """Test BaseLearningEngine integration with database and services."""

    def test_engine_with_database_session(self, auto_dev_db_session):
        """Test engine works with database session."""

        class TestEngine(BaseLearningEngine):
            async def analyze_episode(self, episode_id: str, **kwargs):
                # Can use self.db
                candidates = self.db.query(SkillCandidate).all()
                return {"episode_id": episode_id, "existing_candidates": len(candidates)}

            async def propose_code_change(self, context: dict, **kwargs):
                return "code"

            async def validate_change(self, code: str, test_inputs: list, tenant_id: str, **kwargs):
                return {"passed": True}

        engine = TestEngine(db=auto_dev_db_session)

        import asyncio
        result = asyncio.run(engine.analyze_episode("ep-001"))

        assert result["episode_id"] == "ep-001"
        assert "existing_candidates" in result

    def test_engine_with_mock_services(self, mock_auto_dev_llm, mock_sandbox):
        """Test engine works with mock LLM and sandbox."""

        class TestEngine(BaseLearningEngine):
            async def analyze_episode(self, episode_id: str, **kwargs):
                return {"episode_id": episode_id}

            async def propose_code_change(self, context: dict, **kwargs):
                # Can use self._get_llm_service()
                llm = self._get_llm_service()
                if llm:
                    return "code_from_llm"
                return "fallback_code"

            async def validate_change(self, code: str, test_inputs: list, tenant_id: str, **kwargs):
                # Can use self._get_sandbox()
                sandbox = self._get_sandbox()
                if sandbox:
                    return {"passed": True, "sandbox_used": True}
                return {"passed": False, "sandbox_used": False}

        from sqlalchemy.orm import Session

        db = MagicMock(spec=Session)
        engine = TestEngine(db=db, llm_service=mock_auto_dev_llm, sandbox=mock_sandbox)

        import asyncio

        # Test propose_code_change
        code = asyncio.run(engine.propose_code_change({}))
        assert code == "code_from_llm"

        # Test validate_change
        result = asyncio.run(engine.validate_change("code", [], "tenant-001"))
        assert result["passed"] is True
        assert result["sandbox_used"] is True
