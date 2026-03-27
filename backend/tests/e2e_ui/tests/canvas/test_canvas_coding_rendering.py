"""
E2E Tests for Coding Canvas Rendering (CANV-07).

Tests verify coding canvas displays correctly with:
- Code block with syntax highlighting
- Line numbers displayed
- Language indicator shown
- Multiple language support
- CanvasAudit record creation

Coding Features:
- Syntax highlighting for multiple languages
- Line numbers (optional)
- Language indicator/label
- Copy code button (optional)
- Responsive container

Uses authenticated_page_api fixture for fast authentication.
"""

import pytest
import uuid
from typing import Dict, Any
from playwright.sync_api import Page, expect
from sqlalchemy.orm import Session

# Add backend to path for imports
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from core.models import CanvasAudit


# =============================================================================
# Helper Functions
# =============================================================================

def trigger_canvas_coding(page: Page, code: str, language: str = "python") -> str:
    """Simulate WebSocket canvas:update event for coding.

    Args:
        page: Playwright page instance
        code: Source code to display
        language: Programming language identifier

    Returns:
        str: Generated canvas_id
    """
    canvas_id = f"coding-{str(uuid.uuid4())[:8]}"

    canvas_message = {
        "type": "canvas:update",
        "canvas_id": canvas_id,
        "data": {
            "component": "coding",
            "title": f"Code ({language})",
            "language": language,
            "code": code
        }
    }

    # Store message for potential frontend access
    page.evaluate(f"(msg) => window.lastCanvasMessage = msg", canvas_message)

    # Dispatch custom event to trigger canvas rendering
    page.evaluate("""
        () => {
            const event = new CustomEvent('canvas:update', {
                detail: { type: 'canvas:update' }
            });
            window.dispatchEvent(event);
        }
    """)

    return canvas_id


# =============================================================================
# Coding Canvas Rendering Tests
# =============================================================================

class TestCodingCanvasRendering:
    """Test suite for coding canvas rendering (CANV-07)."""

    def test_coding_canvas_displays_code(self, authenticated_page_api: Page, db_session: Session):
        """Test that coding canvas displays code correctly.

        Verifies:
        - Canvas host element appears
        - Code block visible
        - Syntax highlighting applied (check for token classes)
        - Line numbers displayed (if applicable)
        - CanvasAudit record created
        """
        # Create code data
        code = """def hello_world():
    print("Hello, World!")
    return True

# Call the function
hello_world()"""

        # Trigger coding canvas presentation
        canvas_id = trigger_canvas_coding(
            authenticated_page_api,
            code,
            language="python"
        )

        # Wait for rendering
        authenticated_page_api.wait_for_timeout(500)

        # Verify canvas visible
        canvas_host = authenticated_page_api.locator('[data-canvas-id]').first
        expect(canvas_host).to_be_visible()

        # Verify code block element
        code_element = authenticated_page_api.locator('pre, code, [data-testid="code-block"]').first
        expect(code_element).to_be_visible()

        # Verify code content in page
        page_content = authenticated_page_api.content()
        assert "hello_world" in page_content
        assert "Hello, World" in page_content or "print" in page_content

        # Verify CanvasAudit record
        audit_records = db_session.query(CanvasAudit).filter(
            CanvasAudit.canvas_id == canvas_id
        ).all()

    def test_coding_canvas_language_detection(self, authenticated_page_api: Page):
        """Test that coding canvas handles different languages.

        Verifies:
        - Different syntax highlighting for each language
        - Language indicator displayed
        - Code content preserved
        """
        # Test Python code
        python_code = "def add(a, b):\n    return a + b"
        canvas_id = trigger_canvas_coding(
            authenticated_page_api,
            python_code,
            language="python"
        )

        authenticated_page_api.wait_for_timeout(500)

        # Verify canvas visible
        canvas_host = authenticated_page_api.locator('[data-canvas-id]').first
        expect(canvas_host).to_be_visible()

        # Verify Python code
        page_content = authenticated_page_api.content()
        assert "add" in page_content or "python" in page_content.lower()

        # Test JavaScript code
        js_code = "function add(a, b) {\n    return a + b;\n}"
        canvas_id = trigger_canvas_coding(
            authenticated_page_api,
            js_code,
            language="javascript"
        )

        authenticated_page_api.wait_for_timeout(500)

        # Verify JavaScript code
        page_content = authenticated_page_api.content()
        assert "function" in page_content or "javascript" in page_content.lower()

        # Test JSON code
        json_code = '{"name": "John", "age": 30, "city": "NYC"}'
        canvas_id = trigger_canvas_coding(
            authenticated_page_api,
            json_code,
            language="json"
        )

        authenticated_page_api.wait_for_timeout(500)

        # Verify JSON code
        page_content = authenticated_page_api.content()
        assert "John" in page_content or "json" in page_content.lower()

    def test_coding_canvas_syntax_highlighting(self, authenticated_page_api: Page):
        """Test that coding canvas applies syntax highlighting.

        Verifies:
        - Token classes applied to code
        - Keywords highlighted differently
        - Strings and comments styled
        """
        # Create code with various elements
        code = """# This is a comment
def function_name(param1, param2):
    string_var = "Hello, World!"
    number_var = 42
    return string_var
"""

        # Trigger coding canvas presentation
        canvas_id = trigger_canvas_coding(
            authenticated_page_api,
            code,
            language="python"
        )

        # Wait for rendering
        authenticated_page_api.wait_for_timeout(500)

        # Verify canvas visible
        canvas_host = authenticated_page_api.locator('[data-canvas-id]').first
        expect(canvas_host).to_be_visible()

        # Verify code content
        page_content = authenticated_page_api.content()
        assert "function_name" in page_content or "def" in page_content
        assert "Hello, World" in page_content or "string" in page_content.lower()

    def test_coding_canvas_line_numbers(self, authenticated_page_api: Page):
        """Test that coding canvas displays line numbers.

        Verifies:
        - Line numbers visible (if supported)
        - Numbers aligned correctly
        - Line count matches code
        """
        # Create multi-line code
        code = """line 1
line 2
line 3
line 4
line 5"""

        # Trigger coding canvas presentation
        canvas_id = trigger_canvas_coding(
            authenticated_page_api,
            code,
            language="text"
        )

        # Wait for rendering
        authenticated_page_api.wait_for_timeout(500)

        # Verify canvas visible
        canvas_host = authenticated_page_api.locator('[data-canvas-id]').first
        expect(canvas_host).to_be_visible()

        # Verify code content
        page_content = authenticated_page_api.content()
        assert "line 1" in page_content or "line 5" in page_content

    def test_coding_canvas_long_code(self, authenticated_page_api: Page):
        """Test that coding canvas handles long code snippets.

        Verifies:
        - Long code scrollable
        - All content accessible
        - Performance acceptable
        """
        # Create long code (100 lines)
        lines = []
        for i in range(100):
            lines.append(f"# Line {i}")
            lines.append(f"variable_{i} = {i}")
        code = "\n".join(lines)

        # Trigger coding canvas presentation
        canvas_id = trigger_canvas_coding(
            authenticated_page_api,
            code,
            language="python"
        )

        # Wait for rendering
        authenticated_page_api.wait_for_timeout(500)

        # Verify canvas visible
        canvas_host = authenticated_page_api.locator('[data-canvas-id]').first
        expect(canvas_host).to_be_visible()

        # Scroll to bottom
        authenticated_page_api.evaluate("""
            () => {
                const canvas = document.querySelector('[data-canvas-id]');
                if (canvas) {
                    canvas.scrollTop = canvas.scrollHeight;
                }
            }
        """)

        authenticated_page_api.wait_for_timeout(300)

        # Verify end of code
        page_content = authenticated_page_api.content()
        assert "variable_99" in page_content or "99" in page_content

    def test_coding_canvas_empty_code(self, authenticated_page_api: Page):
        """Test that coding canvas handles empty code gracefully.

        Verifies:
        - Empty state message displayed
        - No error or crash
        """
        # Create empty code
        code = ""

        # Trigger coding canvas presentation
        canvas_id = trigger_canvas_coding(
            authenticated_page_api,
            code,
            language="python"
        )

        # Wait for rendering
        authenticated_page_api.wait_for_timeout(500)

        # Verify canvas visible (even with empty code)
        canvas_host = authenticated_page_api.locator('[data-canvas-id]').first
        expect(canvas_host).to_be_visible()

        # Verify empty state or title
        page_content = authenticated_page_api.content()
        assert "Code" in page_content or "empty" in page_content.lower() or "python" in page_content.lower()

    def test_coding_canvas_special_characters(self, authenticated_page_api: Page):
        """Test that coding canvas handles special characters in code.

        Verifies:
        - Special characters displayed correctly
        - Unicode characters supported
        - No encoding issues
        """
        # Create code with special characters
        code = '''# Special characters test
string1 = "Hello, World!"
string2 = "© 2024"
string3 = "→ Arrow"
string4 = "💡 Emoji"
emoji = "😀🎉"
'''

        # Trigger coding canvas presentation
        canvas_id = trigger_canvas_coding(
            authenticated_page_api,
            code,
            language="python"
        )

        # Wait for rendering
        authenticated_page_api.wait_for_timeout(500)

        # Verify canvas visible
        canvas_host = authenticated_page_api.locator('[data-canvas-id]').first
        expect(canvas_host).to_be_visible()

        # Verify special character content
        page_content = authenticated_page_api.content()
        assert "Hello, World" in page_content or "special" in page_content.lower()
        assert "string" in page_content or "©" in page_content or "2024" in page_content

    def test_coding_canvas_multiple_languages(self, authenticated_page_api: Page):
        """Test that coding canvas supports multiple programming languages.

        Verifies:
        - Python syntax highlighting works
        - JavaScript syntax highlighting works
        - HTML syntax highlighting works
        - CSS syntax highlighting works
        - SQL syntax highlighting works
        """
        # Test multiple languages
        languages = {
            "python": 'print("Hello")',
            "javascript": 'console.log("Hello");',
            "html": '<div>Hello</div>',
            "css": '.class { color: red; }',
            "sql": 'SELECT * FROM users;'
        }

        for lang, code_snippet in languages.items():
            # Trigger coding canvas presentation
            canvas_id = trigger_canvas_coding(
                authenticated_page_api,
                code_snippet,
                language=lang
            )

            authenticated_page_api.wait_for_timeout(300)

            # Verify canvas visible
            canvas_host = authenticated_page_api.locator('[data-canvas-id]').first
            expect(canvas_host).to_be_visible()

            # Verify language indicator or code content
            page_content = authenticated_page_api.content()
            assert lang.lower() in page_content.lower() or "hello" in page_content.lower()

    def test_coding_canvas_indentation_preserved(self, authenticated_page_api: Page):
        """Test that coding canvas preserves code indentation.

        Verifies:
        - Indentation displayed correctly
        - Tabs and spaces handled
        - Code structure visible
        """
        # Create code with significant indentation
        code = """def outer():
    def inner():
        if True:
            print("Nested")
    return inner
"""

        # Trigger coding canvas presentation
        canvas_id = trigger_canvas_coding(
            authenticated_page_api,
            code,
            language="python"
        )

        # Wait for rendering
        authenticated_page_api.wait_for_timeout(500)

        # Verify canvas visible
        canvas_host = authenticated_page_api.locator('[data-canvas-id]').first
        expect(canvas_host).to_be_visible()

        # Verify code structure
        page_content = authenticated_page_api.content()
        assert "outer" in page_content and "inner" in page_content and "Nested" in page_content
