"""
Tests for Canvas Context Provider

Tests cover:
- Canvas creation and retrieval
- Canvas updates
- Provider singleton pattern
- Edge cases
"""

import pytest
from core.canvas_context_provider import (
    CanvasContext,
    CanvasProvider,
    get_canvas_provider,
    reset_canvas_provider,
)


class TestCanvasContext:
    """Test CanvasContext dataclass."""

    def test_canvas_context_creation(self):
        """Test creating a canvas context with all fields."""
        context = CanvasContext(
            canvas_id="canvas-1",
            canvas_type="chart",
            data={"title": "Test Chart", "data": [1, 2, 3]},
            status="presented",
            timestamp="2024-01-01T00:00:00Z",
        )

        assert context.canvas_id == "canvas-1"
        assert context.canvas_type == "chart"
        assert context.data == {"title": "Test Chart", "data": [1, 2, 3]}
        assert context.status == "presented"
        assert context.timestamp == "2024-01-01T00:00:00Z"

    def test_canvas_context_defaults(self):
        """Test canvas context with default values."""
        context = CanvasContext(
            canvas_id="canvas-1",
            canvas_type="markdown",
            data={"content": "Hello"},
        )

        assert context.status == "presented"
        assert context.timestamp is None


class TestCanvasProvider:
    """Test CanvasProvider class."""

    def test_provider_initialization(self):
        """Test provider initializes with empty canvas dict."""
        provider = CanvasProvider()

        assert provider._canvases == {}

    def test_create_canvas(self):
        """Test creating a new canvas."""
        provider = CanvasProvider()

        canvas = provider.create_canvas(
            canvas_type="chart",
            data={"title": "Sales", "values": [10, 20, 30]}
        )

        assert canvas.canvas_id == "canvas-1"
        assert canvas.canvas_type == "chart"
        assert canvas.data == {"title": "Sales", "values": [10, 20, 30]}
        assert "canvas-1" in provider._canvases

    def test_create_multiple_canvases(self):
        """Test creating multiple canvases."""
        provider = CanvasProvider()

        canvas1 = provider.create_canvas("chart", {"title": "Chart 1"})
        canvas2 = provider.create_canvas("markdown", {"content": "Hello"})
        canvas3 = provider.create_canvas("form", {"fields": []})

        assert canvas1.canvas_id == "canvas-1"
        assert canvas2.canvas_id == "canvas-2"
        assert canvas3.canvas_id == "canvas-3"
        assert len(provider._canvases) == 3

    def test_get_canvas_exists(self):
        """Test getting an existing canvas."""
        provider = CanvasProvider()

        created = provider.create_canvas("chart", {"title": "Test"})
        retrieved = provider.get_canvas("canvas-1")

        assert retrieved is not None
        assert retrieved.canvas_id == "canvas-1"
        assert retrieved.canvas_type == "chart"
        assert retrieved.data == {"title": "Test"}

    def test_get_canvas_not_exists(self):
        """Test getting a non-existent canvas."""
        provider = CanvasProvider()

        canvas = provider.get_canvas("nonexistent")

        assert canvas is None

    def test_update_canvas_exists(self):
        """Test updating an existing canvas."""
        provider = CanvasProvider()

        provider.create_canvas("chart", {"title": "Original", "value": 10})

        success = provider.update_canvas("canvas-1", {"value": 20, "new_field": "added"})

        assert success is True

        canvas = provider.get_canvas("canvas-1")
        assert canvas.data == {"title": "Original", "value": 20, "new_field": "added"}

    def test_update_canvas_not_exists(self):
        """Test updating a non-existent canvas."""
        provider = CanvasProvider()

        success = provider.update_canvas("nonexistent", {"value": 20})

        assert success is False

    def test_update_canvas_adds_new_fields(self):
        """Test that update adds new fields without removing existing ones."""
        provider = CanvasProvider()

        provider.create_canvas("chart", {"title": "Test", "value": 10})

        provider.update_canvas("canvas-1", {"new_field": "new_value"})

        canvas = provider.get_canvas("canvas-1")
        assert canvas.data == {"title": "Test", "value": 10, "new_field": "new_value"}

    def test_update_canvas_overwrites_existing_fields(self):
        """Test that update overwrites existing fields."""
        provider = CanvasProvider()

        provider.create_canvas("chart", {"title": "Original", "value": 10})

        provider.update_canvas("canvas-1", {"title": "Updated"})

        canvas = provider.get_canvas("canvas-1")
        assert canvas.data == {"title": "Updated", "value": 10}

    def test_multiple_canvases_independent(self):
        """Test that multiple canvases are independent."""
        provider = CanvasProvider()

        provider.create_canvas("chart", {"title": "Chart 1"})
        provider.create_canvas("markdown", {"content": "Markdown 1"})

        provider.update_canvas("canvas-1", {"title": "Updated Chart 1"})

        canvas1 = provider.get_canvas("canvas-1")
        canvas2 = provider.get_canvas("canvas-2")

        assert canvas1.data == {"title": "Updated Chart 1"}
        assert canvas2.data == {"content": "Markdown 1"}

    def test_create_canvas_with_different_types(self):
        """Test creating canvases with different types."""
        provider = CanvasProvider()

        chart = provider.create_canvas("chart", {"data": []})
        markdown = provider.create_canvas("markdown", {"content": "Hello"})
        form = provider.create_canvas("form", {"fields": []})
        sheet = provider.create_canvas("sheet", {"rows": []})

        assert chart.canvas_type == "chart"
        assert markdown.canvas_type == "markdown"
        assert form.canvas_type == "form"
        assert sheet.canvas_type == "sheet"


class TestGlobalCanvasProvider:
    """Test global canvas provider singleton."""

    def test_get_canvas_provider_singleton(self):
        """Test that get_canvas_provider returns same instance."""
        reset_canvas_provider()  # Reset first

        provider1 = get_canvas_provider()
        provider2 = get_canvas_provider()

        assert provider1 is provider2

    def test_get_canvas_provider_initializes_on_first_call(self):
        """Test that provider is initialized on first call."""
        reset_canvas_provider()

        provider = get_canvas_provider()

        assert isinstance(provider, CanvasProvider)
        assert provider._canvases == {}

    def test_global_provider_persists_canvases(self):
        """Test that global provider persists canvases across calls."""
        reset_canvas_provider()

        provider1 = get_canvas_provider()
        provider1.create_canvas("chart", {"title": "Test"})

        provider2 = get_canvas_provider()
        canvas = provider2.get_canvas("canvas-1")

        assert canvas is not None
        assert canvas.data == {"title": "Test"}

    def test_reset_canvas_provider(self):
        """Test resetting the global provider."""
        provider1 = get_canvas_provider()
        provider1.create_canvas("chart", {"title": "Test"})

        reset_canvas_provider()

        provider2 = get_canvas_provider()
        assert provider1 is not provider2
        assert provider2.get_canvas("canvas-1") is None

    def test_global_provider_independence_after_reset(self):
        """Test that provider is independent after reset."""
        reset_canvas_provider()

        provider1 = get_canvas_provider()
        provider1.create_canvas("chart", {"title": "First"})

        reset_canvas_provider()

        provider2 = get_canvas_provider()
        provider2.create_canvas("chart", {"title": "Second"})

        # Second provider should not have first canvas (different instance)
        # But since counter resets, it has its own canvas-1
        canvas = provider2.get_canvas("canvas-1")
        assert canvas is not None
        assert canvas.data == {"title": "Second"}
        # Verify provider1 and provider2 are different instances
        assert provider1 is not provider2
