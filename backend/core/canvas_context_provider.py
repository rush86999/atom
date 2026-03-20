"""
Canvas context provider stub module.

This module provides canvas context integration for agents.
Created in Phase 203 to unblock tests blocked by missing module.

TODO: Implement full canvas context provider functionality in future phase.
"""

from typing import Any, Dict, Optional
from dataclasses import dataclass


@dataclass
class CanvasContext:
    """Canvas context data structure."""
    canvas_id: str
    canvas_type: str
    data: Dict[str, Any]
    status: str = "presented"
    timestamp: Optional[str] = None


class CanvasProvider:
    """Canvas provider for managing canvas contexts."""

    def __init__(self):
        self._canvases: Dict[str, CanvasContext] = {}

    def get_canvas(self, canvas_id: str) -> Optional[CanvasContext]:
        """Get canvas by ID."""
        return self._canvases.get(canvas_id)

    def create_canvas(self, canvas_type: str, data: Dict[str, Any]) -> CanvasContext:
        """Create a new canvas context."""
        canvas = CanvasContext(
            canvas_id=f"canvas-{len(self._canvases) + 1}",
            canvas_type=canvas_type,
            data=data
        )
        self._canvases[canvas.canvas_id] = canvas
        return canvas

    def update_canvas(self, canvas_id: str, data: Dict[str, Any]) -> bool:
        """Update existing canvas."""
        canvas = self.get_canvas(canvas_id)
        if canvas:
            canvas.data.update(data)
            return True
        return False


# Global provider instance
_provider: Optional[CanvasProvider] = None


def get_canvas_provider() -> CanvasProvider:
    """Get the global canvas provider instance."""
    global _provider
    if _provider is None:
        _provider = CanvasProvider()
    return _provider


def reset_canvas_provider():
    """Reset the global canvas provider (for testing)."""
    global _provider
    _provider = None
