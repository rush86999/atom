"""
E2E Tests for Coding Canvas Rendering (CANV-07).

Tests verify the code canvas renders correctly through the REAL rendering
path (no phantom state injection):

1. A code canvas is created as `Canvas` + `CanvasAudit` rows via
   `canvas_helpers.create_canvas()` (mirroring
   `tools/canvas_tool.present_code()`), with the code stored as a string.
2. Tests navigate to `http://localhost:3001/canvas/{id}`, where `CanvasPanel`
   renders the code in a Monaco editor (`@monaco-editor/react`).

Verified: editor mounts, code content preserved, Monaco token (syntax
highlighting) classes applied, line numbers, long/special/empty content,
multi-language content preservation.

Note: the /canvas/{id} path renders code with Monaco's default language
("javascript" per CanvasPanel) — language-specific highlighting per input
language is not part of this route's contract; content preservation is.
"""

import uuid
from typing import Tuple

from playwright.sync_api import Page, expect
from sqlalchemy.orm import Session

# Add backend to path for imports
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from core.models import CanvasAudit, User
from tests.e2e_ui.tests.canvas_helpers import create_canvas, open_canvas


# =============================================================================
# Helper Functions
# =============================================================================

def open_code_canvas(page: Page, canvas_id: str, expect_content: bool = True) -> None:
    """Navigate to a code canvas and wait for the Monaco editor to mount."""
    open_canvas(page, canvas_id, "code")
    # Monaco loads from CDN on first use — allow generous time. Also wait
    # until the editor actually has rendered content (tokenization/layout
    # complete), so subsequent inner_text reads are race-free.
    page.wait_for_selector(".monaco-editor .view-lines", timeout=30000)
    if expect_content:
        page.wait_for_function(
            """() => {
                const lines = document.querySelectorAll('.monaco-editor .view-lines .view-line');
                return lines.length > 0 && lines[0].textContent.trim().length > 0;
            }""",
            timeout=30000,
        )


def create_code_canvas(db: Session, user: User, code: str, title: str = "Code Canvas") -> str:
    """Create a code canvas whose content is the raw code string."""
    canvas_id = f"e2e-code-{uuid.uuid4()}"
    create_canvas(db, user, canvas_id, "code", title, code)
    return canvas_id


def editor_text(page: Page) -> str:
    """Read the code currently displayed in the Monaco editor, normalizing the
    non-breaking spaces Monaco renders in place of regular spaces."""
    return page.locator(".monaco-editor .view-lines").inner_text().replace("\u00a0", " ")


# =============================================================================
# Coding Canvas Rendering Tests
# =============================================================================

def test_coding_canvas_displays_code(
    authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session
):
    """Test that coding canvas displays code correctly in the Monaco editor.

    Verifies:
    - CanvasPanel container with code type badge
    - Monaco editor mounted with the code text
    - CanvasAudit record created
    """
    user, _ = authenticated_user
    code = """def hello_world():
    print("Hello, World!")
    return True

# Call the function
hello_world()"""
    canvas_id = create_code_canvas(db_session, user, code, "Coding Canvas")

    open_code_canvas(authenticated_page, canvas_id)

    text = editor_text(authenticated_page)
    assert "hello_world" in text, "Code content should be displayed"
    assert "Hello, World!" in text, "Code string content should be preserved"

    audit = db_session.query(CanvasAudit).filter(CanvasAudit.canvas_id == canvas_id).all()
    assert len(audit) >= 1, "CanvasAudit record should exist for the canvas"
    assert audit[0].canvas_type == "code", "Audit row should carry the code type"


def test_coding_canvas_language_detection(
    authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session
):
    """Test that coding canvas preserves content for different languages.

    Each language gets its own canvas (real route renders one canvas per
    page); content must survive the round trip verbatim.
    """
    user, _ = authenticated_user
    samples = [
        ("python", "def add(a, b):\n    return a + b"),
        ("javascript", "function add(a, b) {\n    return a + b;\n}"),
        ("json", '{"name": "John", "age": 30, "city": "NYC"}'),
    ]
    for language, code in samples:
        canvas_id = create_code_canvas(db_session, user, code, f"{language} canvas")
        open_code_canvas(authenticated_page, canvas_id)
        text = editor_text(authenticated_page)
        assert code.splitlines()[0] in text, f"{language} code should render"


def test_coding_canvas_syntax_highlighting(
    authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session
):
    """Test that coding canvas applies Monaco syntax token classes."""
    user, _ = authenticated_user
    code = """# This is a comment
def function_name(param1, param2):
    string_var = "Hello, World!"
    number_var = 42
    return string_var
"""
    canvas_id = create_code_canvas(db_session, user, code)
    open_code_canvas(authenticated_page, canvas_id)

    # Tokenization is async — wait until the token spans (mtk{1..N}) are in
    # the DOM. Note: Monaco token classes are numbered (mtk1, mtk11, mtk22…),
    # so match the class-name prefix, not the bare `.mtk` class.
    authenticated_page.wait_for_function(
        "() => document.querySelectorAll('.monaco-editor .view-lines span[class*=\"mtk\"]').length > 0",
        timeout=30000,
    )
    token_count = authenticated_page.locator(
        '.monaco-editor .view-lines span[class*="mtk"]'
    ).count()
    assert token_count > 0, "Syntax highlighting token spans should be rendered"

    text = editor_text(authenticated_page)
    assert "function_name" in text, "Code content should be preserved"


def test_coding_canvas_line_numbers(
    authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session
):
    """Test that coding canvas displays line numbers in the gutter."""
    user, _ = authenticated_user
    code = "line_one\nline_two\nline_three\nline_four"
    canvas_id = create_code_canvas(db_session, user, code)
    open_code_canvas(authenticated_page, canvas_id)

    line_numbers = authenticated_page.locator(".monaco-editor .margin .line-numbers")
    assert line_numbers.count() >= 4, (
        f"Expected at least 4 line numbers, got {line_numbers.count()}"
    )


def test_coding_canvas_long_code(
    authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session
):
    """Test that coding canvas handles long code (100+ lines) without breaking.

    Monaco virtualizes rendering, so only the visible window is in the DOM —
    the guarantee here is that the editor mounts and renders content.
    """
    user, _ = authenticated_user
    code = "\n".join(f"line_{i}: value = {i}" for i in range(100))
    canvas_id = create_code_canvas(db_session, user, code, "Long Code")
    open_code_canvas(authenticated_page, canvas_id)

    text = editor_text(authenticated_page)
    assert "line_0: value = 0" in text, "First line should render"
    assert "value = " in text, "Long code content should render"


def test_coding_canvas_empty_code(
    authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session
):
    """Test that coding canvas handles empty code gracefully."""
    user, _ = authenticated_user
    canvas_id = create_code_canvas(db_session, user, "", "Empty Code")
    open_code_canvas(authenticated_page, canvas_id, expect_content=False)

    # Editor mounts and the canvas container stays visible (no crash).
    container_text = authenticated_page.locator('[data-testid="canvas-container"]').inner_text().lower()
    assert "code" in container_text, "Type badge should still show for empty code"


def test_coding_canvas_special_characters(
    authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session
):
    """Test that coding canvas handles special/unicode characters."""
    user, _ = authenticated_user
    code = """$ echo "Hello, World!"
✓ Success
⚠ Warning
→ Arrow symbol
© Copyright 2024
💡 Emoji test"""
    canvas_id = create_code_canvas(db_session, user, code)
    open_code_canvas(authenticated_page, canvas_id)

    text = editor_text(authenticated_page)
    assert "✓ Success" in text, "Unicode checkmark should render"
    assert "💡 Emoji test" in text, "Emoji should render"


def test_coding_canvas_multiple_languages(
    authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session
):
    """Test that coding canvas preserves distinct code across canvases."""
    user, _ = authenticated_user
    samples = [
        "def python_only_function():\n    pass",
        "const jsOnly = () => 42;",
        '{"jsonOnly": true}',
    ]
    for i, code in enumerate(samples):
        canvas_id = create_code_canvas(db_session, user, code, f"Multi {i}")
        open_code_canvas(authenticated_page, canvas_id)
        text = editor_text(authenticated_page)
        assert code.splitlines()[0] in text, f"Sample {i} content should render"


def test_coding_canvas_indentation_preserved(
    authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session
):
    """Test that coding canvas preserves indentation (whitespace)."""
    user, _ = authenticated_user
    code = "def outer():\n    if True:\n        return 42\n    else:\n        return 0"
    canvas_id = create_code_canvas(db_session, user, code)
    open_code_canvas(authenticated_page, canvas_id)

    text = editor_text(authenticated_page)
    assert "        return 42" in text, "4-space (double) indentation should be preserved"
    assert "    return 0" in text, "Indentation should be preserved"
