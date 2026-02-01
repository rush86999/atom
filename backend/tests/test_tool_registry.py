"""
Unit tests for Tool Registry system.

Tests tool discovery, metadata management, and the tool discovery API.
"""

import pytest
from unittest.mock import Mock, patch

from tools.registry import ToolRegistry, ToolMetadata, get_tool_registry


class TestToolMetadata:
    """Test ToolMetadata class."""

    def test_tool_metadata_creation(self):
        """Test creating tool metadata."""
        def dummy_function():
            pass

        metadata = ToolMetadata(
            name="test_tool",
            function=dummy_function,
            version="1.0.0",
            description="A test tool",
            category="test",
            complexity=2,
            maturity_required="INTERN",
            tags=["test", "example"]
        )

        assert metadata.name == "test_tool"
        assert metadata.version == "1.0.0"
        assert metadata.description == "A test tool"
        assert metadata.category == "test"
        assert metadata.complexity == 2
        assert metadata.maturity_required == "INTERN"
        assert "test" in metadata.tags

    def test_tool_metadata_to_dict(self):
        """Test converting tool metadata to dictionary."""
        def dummy_function(user_id: str, data: dict = None):
            """Dummy function for testing."""
            pass

        metadata = ToolMetadata(
            name="test_tool",
            function=dummy_function,
            version="1.0.0",
            description="A test tool",
            category="test",
            complexity=2,
            maturity_required="INTERN",
            parameters={
                "user_id": {"type": "str", "description": "User ID"},
                "data": {"type": "dict", "description": "Data"}
            },
            examples=[
                {
                    "description": "Example usage",
                    "code": "test_tool(user_id='user-1', data={'key': 'value'})"
                }
            ],
            tags=["test"]
        )

        tool_dict = metadata.to_dict()

        assert tool_dict["name"] == "test_tool"
        assert tool_dict["version"] == "1.0.0"
        assert tool_dict["description"] == "A test tool"
        assert tool_dict["category"] == "test"
        assert tool_dict["complexity"] == 2
        assert tool_dict["maturity_required"] == "INTERN"
        assert "user_id" in tool_dict["parameters"]
        assert len(tool_dict["examples"]) == 1
        assert "test" in tool_dict["tags"]
        assert "registered_at" in tool_dict
        assert "function_path" in tool_dict


class TestToolRegistry:
    """Test ToolRegistry class."""

    def test_register_tool(self):
        """Test registering a new tool."""
        registry = ToolRegistry()

        def dummy_tool():
            """A dummy tool."""
            pass

        metadata = registry.register(
            name="dummy_tool",
            function=dummy_tool,
            version="1.0.0",
            description="Dummy tool",
            category="test"
        )

        assert metadata is not None
        assert metadata.name == "dummy_tool"
        assert "dummy_tool" in registry.list_all()

    def test_register_duplicate_tool(self):
        """Test registering a tool twice (should update)."""
        registry = ToolRegistry()

        def dummy_tool():
            pass

        registry.register(name="dummy_tool", function=dummy_tool, version="1.0.0")

        # Register again with new version
        metadata = registry.register(name="dummy_tool", function=dummy_tool, version="2.0.0")

        # Should be updated
        assert metadata.version == "2.0.0"
        assert len(registry.list_all()) == 1  # Still only one tool

    def test_get_tool(self):
        """Test getting tool metadata."""
        registry = ToolRegistry()

        def dummy_tool():
            pass

        registry.register(name="dummy_tool", function=dummy_tool, description="Test")

        metadata = registry.get("dummy_tool")

        assert metadata is not None
        assert metadata.name == "dummy_tool"
        assert metadata.description == "Test"

    def test_get_nonexistent_tool(self):
        """Test getting a tool that doesn't exist."""
        registry = ToolRegistry()
        metadata = registry.get("nonexistent_tool")
        assert metadata is None

    def test_get_function(self):
        """Test getting tool function."""
        registry = ToolRegistry()

        def dummy_tool():
            return "result"

        registry.register(name="dummy_tool", function=dummy_tool)

        func = registry.get_function("dummy_tool")

        assert func is not None
        assert func() == "result"

    def test_list_all(self):
        """Test listing all tools."""
        registry = ToolRegistry()

        def tool1():
            pass

        def tool2():
            pass

        registry.register(name="tool1", function=tool1)
        registry.register(name="tool2", function=tool2)

        tools = registry.list_all()

        assert len(tools) == 2
        assert "tool1" in tools
        assert "tool2" in tools

    def test_list_by_category(self):
        """Test listing tools by category."""
        registry = ToolRegistry()

        def tool1():
            pass

        def tool2():
            pass

        registry.register(name="tool1", function=tool1, category="canvas")
        registry.register(name="tool2", function=tool2, category="browser")

        canvas_tools = registry.list_by_category("canvas")
        browser_tools = registry.list_by_category("browser")

        assert "tool1" in canvas_tools
        assert "tool1" not in browser_tools
        assert "tool2" in browser_tools
        assert "tool2" not in canvas_tools

    def test_list_by_maturity(self):
        """Test listing tools by maturity level."""
        registry = ToolRegistry()

        def tool1():
            pass

        def tool2():
            pass

        def tool3():
            pass

        registry.register(name="tool1", function=tool1, maturity_required="STUDENT")
        registry.register(name="tool2", function=tool2, maturity_required="INTERN")
        registry.register(name="tool3", function=tool3, maturity_required="SUPERVISED")

        # INTERN agents can access STUDENT and INTERN tools
        intern_tools = registry.list_by_maturity("INTERN")

        assert "tool1" in intern_tools  # STUDENT
        assert "tool2" in intern_tools  # INTERN
        assert "tool3" not in intern_tools  # SUPERVISED

    def test_search_tools(self):
        """Test searching tools."""
        registry = ToolRegistry()

        def chart_tool():
            """A chart visualization tool."""
            pass

        def browser_tool():
            """A browser automation tool."""
            pass

        registry.register(
            name="present_chart",
            function=chart_tool,
            description="Present charts to users",
            tags=["canvas", "visualization"]
        )

        registry.register(
            name="browser_navigate",
            function=browser_tool,
            description="Navigate browser",
            tags=["browser", "automation"]
        )

        # Search by name
        results = registry.search("chart")
        assert len(results) == 1
        assert results[0].name == "present_chart"

        # Search by tag
        results = registry.search("automation")
        assert len(results) == 1
        assert results[0].name == "browser_navigate"

        # Search by description
        results = registry.search("present")
        assert len(results) == 1

    def test_get_stats(self):
        """Test getting registry statistics."""
        registry = ToolRegistry()

        def tool1():
            pass

        def tool2():
            pass

        registry.register(name="tool1", function=tool1, category="canvas", complexity=1, maturity_required="STUDENT")
        registry.register(name="tool2", function=tool2, category="browser", complexity=2, maturity_required="INTERN")

        stats = registry.get_stats()

        assert stats["total_tools"] == 2
        assert stats["categories"]["canvas"] == 1
        assert stats["categories"]["browser"] == 1
        assert stats["complexity_distribution"]["LOW"] == 1
        assert stats["complexity_distribution"]["MODERATE"] == 1
        assert stats["maturity_distribution"]["STUDENT"] == 1
        assert stats["maturity_distribution"]["INTERN"] == 1

    def test_export_all(self):
        """Test exporting all tools as dictionaries."""
        registry = ToolRegistry()

        def tool1():
            pass

        registry.register(
            name="tool1",
            function=tool1,
            version="1.0.0",
            description="Test tool",
            category="test"
        )

        exported = registry.export_all()

        assert len(exported) == 1
        assert exported[0]["name"] == "tool1"
        assert exported[0]["version"] == "1.0.0"

    def test_category_indexing(self):
        """Test that tools are properly indexed by category."""
        registry = ToolRegistry()

        def tool1():
            pass

        def tool2():
            pass

        registry.register(name="tool1", function=tool1, category="canvas")
        registry.register(name="tool2", function=tool2, category="canvas")

        assert len(registry.list_by_category("canvas")) == 2
        assert len(registry._categories["canvas"]) == 2


class TestToolRegistryDiscovery:
    """Test automatic tool discovery."""

    def test_discover_tools_from_modules(self):
        """Test discovering tools from specified modules."""
        registry = ToolRegistry()

        # Discover from specific modules
        registry.discover_tools(tool_modules=[])

        # Should at least have registered the tools we manually add
        # (discovery might fail gracefully if modules don't exist)
        assert isinstance(registry.list_all(), list)

    def test_initialize_registry(self):
        """Test initializing the tool registry."""
        registry = ToolRegistry()

        # Initialize with default tools
        registry.initialize()

        # Should have tools registered
        assert len(registry.list_all()) > 0

        # Check for expected tools
        tools = registry.list_all()

        # Should have canvas tools
        assert "present_chart" in tools or "present_markdown" in tools


class TestGlobalRegistry:
    """Test global tool registry instance."""

    def test_get_global_registry(self):
        """Test getting the global registry instance."""
        registry1 = get_tool_registry()
        registry2 = get_tool_registry()

        # Should return the same instance
        assert registry1 is registry2

    def test_global_registry_initialized(self):
        """Test that global registry is initialized."""
        registry = get_tool_registry()

        # Should have tools
        assert len(registry.list_all()) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
