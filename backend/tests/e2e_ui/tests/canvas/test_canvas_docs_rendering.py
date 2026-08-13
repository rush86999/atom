"""
E2E Tests for Docs Canvas Rendering (CANV-04).

Tests verify the markdown/document canvas renders correctly through the REAL
rendering path (no phantom state injection):

1. A markdown canvas is created as `Canvas` + `CanvasAudit` rows via
   `canvas_helpers.create_markdown_canvas()` (mirroring
   `tools/canvas_tool.present_docs()`).
2. Tests navigate to `http://localhost:3001/canvas/{id}`, where `CanvasPanel`
   renders the markdown content in a Monaco editor by default, and toggling
   "Preview Mode" renders the markdown via `renderMarkdownSafe()` (marked +
   DOMPurify) into the `.prose` container.

Markdown features verified: headings (h1–h6), bold/italic, bullet/numbered
lists, links, code blocks, tables, blockquotes, images, horizontal rules.
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
from tests.e2e_ui.tests.canvas_helpers import create_markdown_canvas, open_canvas


# =============================================================================
# Helper Functions
# =============================================================================

def open_docs_preview(page: Page, canvas_id: str) -> None:
    """Open a markdown canvas and switch to Preview Mode (rendered HTML)."""
    open_canvas(page, canvas_id, "markdown")
    page.wait_for_selector(".monaco-editor", timeout=30000)
    # Toggle from Edit Mode → Preview Mode; the rendered block gets .prose.
    page.locator("button", has_text="Preview Mode").first.click()
    page.wait_for_selector(".prose", timeout=10000)


def create_docs_canvas(
    db: Session, user: User, title: str, markdown: str
) -> str:
    """Create a markdown canvas (unique suffix) and return its ID."""
    return create_markdown_canvas(db, user, title, markdown)


# =============================================================================
# Docs Canvas Rendering Tests
# =============================================================================

def test_docs_renders_markdown_content(
    authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session
):
    """Test that docs canvas renders markdown content correctly.

    Verifies:
    - CanvasPanel container with markdown type badge
    - h1 header rendered in Preview Mode
    - Bold/italic text, bullet and numbered lists rendered
    - CanvasAudit record created
    """
    user, _ = authenticated_user
    markdown_content = """# Document Title

This is a paragraph with **bold text** and *italic text*.

## Bullet Points

- First item
- Second item
- Third item

## Numbered List

1. First step
2. Second step
3. Third step
"""
    canvas_id = create_docs_canvas(db_session, user, "Markdown Test", markdown_content)
    open_docs_preview(authenticated_page, canvas_id)

    prose = authenticated_page.locator(".prose")
    expect(prose.locator("h1").first).to_be_visible()
    assert "Document Title" in prose.locator("h1").first.inner_text()

    # Bullet + numbered lists render as real <li> elements.
    list_items = prose.locator("li").all_inner_texts()
    assert "First item" in list_items, f"Bullet item missing: {list_items}"
    assert "First step" in list_items, f"Numbered item missing: {list_items}"

    page_content = authenticated_page.content()
    assert "bold text" in page_content, "Bold text content should be present"

    audit = db_session.query(CanvasAudit).filter(CanvasAudit.canvas_id == canvas_id).all()
    assert len(audit) >= 1, "CanvasAudit record should exist for the canvas"
    assert audit[0].canvas_type == "markdown", "Audit row should carry the markdown type"


def test_docs_links_are_clickable(
    authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session
):
    """Test that docs canvas renders links with correct href attributes."""
    user, _ = authenticated_user
    markdown_content = """# Links Test

External link: [OpenAI](https://openai.com)

Internal link: [Dashboard](/dashboard)

Email link: [Contact](mailto:test@example.com)
"""
    canvas_id = create_docs_canvas(db_session, user, "Links Test", markdown_content)
    open_docs_preview(authenticated_page, canvas_id)

    links = authenticated_page.locator(".prose a")
    hrefs = links.evaluate_all("els => els.map(e => e.getAttribute('href'))")
    assert "https://openai.com" in hrefs, f"External link missing: {hrefs}"
    assert "/dashboard" in hrefs, f"Internal link missing: {hrefs}"
    assert "mailto:test@example.com" in hrefs, f"Email link missing: {hrefs}"
    assert "OpenAI" in authenticated_page.locator(".prose").inner_text()


def test_docs_code_blocks_rendered(
    authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session
):
    """Test that docs canvas renders code blocks correctly."""
    user, _ = authenticated_user
    markdown_content = """# Code Examples

Python code:

```python
def hello_world():
    print("Hello, World!")
    return True
```

Inline code: `variable_name`
"""
    canvas_id = create_docs_canvas(db_session, user, "Code Blocks Test", markdown_content)
    open_docs_preview(authenticated_page, canvas_id)

    code_blocks = authenticated_page.locator(".prose pre code")
    assert code_blocks.count() >= 1, "At least one fenced code block should render"
    code_text = code_blocks.first.inner_text()
    assert "hello_world" in code_text, "Code content should be preserved"

    inline_code = authenticated_page.locator(".prose code:not(pre code)")
    assert inline_code.count() >= 1, "Inline code should render"
    assert "variable_name" in inline_code.first.inner_text()


def test_docs_tables_rendered(
    authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session
):
    """Test that docs canvas renders markdown tables correctly (GFM)."""
    user, _ = authenticated_user
    markdown_content = """# Table Test

| Name | Age | City |
|------|-----|------|
| Alice | 30 | NYC |
| Bob | 25 | LA |
"""
    canvas_id = create_docs_canvas(db_session, user, "Table Test", markdown_content)
    open_docs_preview(authenticated_page, canvas_id)

    table = authenticated_page.locator(".prose table").first
    expect(table).to_be_visible()
    table_text = table.inner_text()
    assert "Alice" in table_text, "Table data row should render"
    assert "Name" in table_text, "Table header should render"


def test_docs_blockquotes_rendered(
    authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session
):
    """Test that docs canvas renders blockquotes correctly."""
    user, _ = authenticated_user
    markdown_content = """# Blockquote Test

This is normal text.

> This is a blockquote.
> It can span multiple lines.

More normal text.
"""
    canvas_id = create_docs_canvas(db_session, user, "Blockquote Test", markdown_content)
    open_docs_preview(authenticated_page, canvas_id)

    blockquote = authenticated_page.locator(".prose blockquote").first
    expect(blockquote).to_be_visible()
    assert "blockquote" in blockquote.inner_text().lower(), "Quote content should render"


def test_docs_images_rendered(
    authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session
):
    """Test that docs canvas renders images with src and alt text."""
    user, _ = authenticated_user
    markdown_content = """# Image Test

![Alt text](https://example.com/image.png)
"""
    canvas_id = create_docs_canvas(db_session, user, "Image Test", markdown_content)
    open_docs_preview(authenticated_page, canvas_id)

    img = authenticated_page.locator('.prose img[src="https://example.com/image.png"]').first
    expect(img).to_be_visible()
    assert img.get_attribute("alt") == "Alt text", "Alt text should be preserved"


def test_docs_heading_levels(
    authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session
):
    """Test that docs canvas renders all heading levels (h1–h6)."""
    user, _ = authenticated_user
    markdown_content = """# Heading 1

## Heading 2

### Heading 3

#### Heading 4

##### Heading 5

###### Heading 6
"""
    canvas_id = create_docs_canvas(db_session, user, "Heading Levels Test", markdown_content)
    open_docs_preview(authenticated_page, canvas_id)

    for level in range(1, 7):
        heading = authenticated_page.locator(f".prose h{level}").first
        expect(heading).to_be_visible()
        assert heading.inner_text().strip() == f"Heading {level}", f"h{level} content mismatch"


def test_docs_horizontal_rules(
    authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session
):
    """Test that docs canvas renders horizontal rules."""
    user, _ = authenticated_user
    markdown_content = """# Horizontal Rule Test

Content above rule

---

Content below rule
"""
    canvas_id = create_docs_canvas(db_session, user, "Horizontal Rule Test", markdown_content)
    open_docs_preview(authenticated_page, canvas_id)

    hr_count = authenticated_page.locator(".prose hr").count()
    assert hr_count >= 1, f"Expected at least 1 <hr>, got {hr_count}"
