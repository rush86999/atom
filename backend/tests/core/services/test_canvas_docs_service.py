"""
Tests for DocumentationCanvasService

Tests for documentation canvas service including:
- Document creation
- Content updates
- Comment management
- Version control
- Table of contents
"""

import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.canvas_docs_service import (
    DocumentationCanvasService,
    DocumentVersion,
    DocumentComment,
)
from core.models import CanvasAudit


@pytest.fixture
def db_session():
    """Create a test database session."""
    engine = create_engine("sqlite:///:memory:")
    from core.models import Base
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def docs_service(db_session):
    """Create documentation service instance."""
    return DocumentationCanvasService(db_session)


@pytest.fixture
def test_user_id():
    """Test user ID."""
    return "test-user-123"


@pytest.fixture
def test_canvas_id():
    """Test canvas ID."""
    return "test-canvas-123"


class TestDocumentVersion:
    """Tests for DocumentVersion class."""

    def test_document_version_init(self):
        """Test DocumentVersion initialization."""
        version = DocumentVersion(
            version_id="version-1",
            content="Test content",
            author="user-1",
            created_at=datetime.now(),
            changes="Initial version"
        )

        assert version.version_id == "version-1"
        assert version.content == "Test content"
        assert version.author == "user-1"
        assert version.changes == "Initial version"

    def test_document_version_optional_changes(self):
        """Test DocumentVersion with optional changes."""
        version = DocumentVersion(
            version_id="version-2",
            content="Content",
            author="user-2",
            created_at=datetime.now()
        )

        assert version.changes == ""


class TestDocumentComment:
    """Tests for DocumentComment class."""

    def test_document_comment_init(self):
        """Test DocumentComment initialization."""
        comment = DocumentComment(
            comment_id="comment-1",
            content="Test comment",
            author="user-1",
            resolved=False,
            created_at=datetime.now()
        )

        assert comment.comment_id == "comment-1"
        assert comment.content == "Test comment"
        assert comment.resolved is False

    def test_document_comment_with_selection(self):
        """Test DocumentComment with text selection."""
        comment = DocumentComment(
            comment_id="comment-2",
            content="Highlight this",
            author="user-2",
            selection={"start": 0, "end": 10, "text": "Highlight"},
            resolved=False
        )

        assert comment.selection["start"] == 0
        assert comment.selection["end"] == 10


class TestDocumentationCanvasServiceInit:
    """Tests for DocumentationCanvasService initialization."""

    def test_init_with_db(self, db_session):
        """Test service initialization with database session."""
        service = DocumentationCanvasService(db_session)
        assert service.db == db_session


class TestCreateDocumentCanvas:
    """Tests for create_document_canvas method."""

    def test_create_document_basic(self, docs_service, test_user_id):
        """Test basic document creation."""
        result = docs_service.create_document_canvas(
            user_id=test_user_id,
            title="Test Document",
            content="# Test\n\nThis is a test document."
        )

        assert result["success"] is True
        assert result["title"] == "Test Document"
        assert result["content"] == "# Test\n\nThis is a test document."
        assert result["enable_comments"] is True
        assert result["enable_versioning"] is True
        assert "canvas_id" in result
        assert "version_id" in result

    def test_create_document_with_custom_canvas_id(self, docs_service, test_user_id):
        """Test document creation with custom canvas ID."""
        custom_id = "custom-canvas-123"
        result = docs_service.create_document_canvas(
            user_id=test_user_id,
            title="Custom ID Document",
            content="Content",
            canvas_id=custom_id
        )

        assert result["canvas_id"] == custom_id

    def test_create_document_with_agent(self, docs_service, test_user_id):
        """Test document creation by agent."""
        result = docs_service.create_document_canvas(
            user_id=test_user_id,
            title="Agent Document",
            content="Created by agent",
            agent_id="agent-123"
        )

        assert result["success"] is True

    def test_create_document_comments_disabled(self, docs_service, test_user_id):
        """Test document creation with comments disabled."""
        result = docs_service.create_document_canvas(
            user_id=test_user_id,
            title="No Comments Document",
            content="Content",
            enable_comments=False
        )

        assert result["enable_comments"] is False

    def test_create_document_versioning_disabled(self, docs_service, test_user_id):
        """Test document creation with versioning disabled."""
        result = docs_service.create_document_canvas(
            user_id=test_user_id,
            title="No Versioning Document",
            content="Content",
            enable_versioning=False
        )

        assert result["enable_versioning"] is False

    def test_create_document_split_layout(self, docs_service, test_user_id):
        """Test document creation with split layout."""
        result = docs_service.create_document_canvas(
            user_id=test_user_id,
            title="Split Layout Document",
            content="Content",
            layout="split_view"
        )

        assert result["layout"] == "split_view"


class TestUpdateDocumentContent:
    """Tests for update_document_content method."""

    def test_update_document_content(self, docs_service, test_user_id, test_canvas_id):
        """Test updating document content."""
        # Create document first
        docs_service.create_document_canvas(
            user_id=test_user_id,
            title="Original",
            content="Original content",
            canvas_id=test_canvas_id
        )

        # Update content
        result = docs_service.update_document_content(
            canvas_id=test_canvas_id,
            user_id=test_user_id,
            content="Updated content",
            changes="Fixed typo"
        )

        assert result["success"] is True
        assert result["content"] == "Updated content"
        assert "version_id" in result

    def test_update_document_not_found(self, docs_service, test_user_id):
        """Test updating non-existent document."""
        result = docs_service.update_document_content(
            canvas_id="non-existent",
            user_id=test_user_id,
            content="Content"
        )

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_update_document_without_versioning(self, docs_service, test_user_id, test_canvas_id):
        """Test updating document without creating version."""
        # Create document with versioning enabled
        docs_service.create_document_canvas(
            user_id=test_user_id,
            title="Test",
            content="Original",
            canvas_id=test_canvas_id
        )

        # Update without creating version
        result = docs_service.update_document_content(
            canvas_id=test_canvas_id,
            user_id=test_user_id,
            content="Updated",
            create_version=False
        )

        assert result["success"] is True


class TestAddComment:
    """Tests for add_comment method."""

    def test_add_comment(self, docs_service, test_user_id, test_canvas_id):
        """Test adding comment to document."""
        # Create document
        docs_service.create_document_canvas(
            user_id=test_user_id,
            title="Commentable Doc",
            content="Content",
            canvas_id=test_canvas_id
        )

        # Add comment
        result = docs_service.add_comment(
            canvas_id=test_canvas_id,
            user_id=test_user_id,
            content="This is a comment"
        )

        assert result["success"] is True
        assert result["content"] == "This is a comment"
        assert "comment_id" in result

    def test_add_comment_with_selection(self, docs_service, test_user_id, test_canvas_id):
        """Test adding comment with text selection."""
        # Create document
        docs_service.create_document_canvas(
            user_id=test_user_id,
            title="Doc",
            content="Content to select",
            canvas_id=test_canvas_id
        )

        # Add comment with selection
        result = docs_service.add_comment(
            canvas_id=test_canvas_id,
            user_id=test_user_id,
            content="Highlight this",
            selection={"start": 0, "end": 7, "text": "Content"}
        )

        assert result["success"] is True
        assert result["selection"]["text"] == "Content"

    def test_add_comment_comments_disabled(self, docs_service, test_user_id, test_canvas_id):
        """Test adding comment to document with comments disabled."""
        # Create document with comments disabled
        docs_service.create_document_canvas(
            user_id=test_user_id,
            title="No Comments",
            content="Content",
            canvas_id=test_canvas_id,
            enable_comments=False
        )

        # Try to add comment
        result = docs_service.add_comment(
            canvas_id=test_canvas_id,
            user_id=test_user_id,
            content="Should fail"
        )

        assert result["success"] is False
        assert "not enabled" in result["error"].lower()

    def test_add_comment_document_not_found(self, docs_service, test_user_id):
        """Test adding comment to non-existent document."""
        result = docs_service.add_comment(
            canvas_id="non-existent",
            user_id=test_user_id,
            content="Comment"
        )

        assert result["success"] is False


class TestResolveComment:
    """Tests for resolve_comment method."""

    def test_resolve_comment(self, docs_service, test_user_id, test_canvas_id):
        """Test resolving a comment."""
        # Create document and add comment
        docs_service.create_document_canvas(
            user_id=test_user_id,
            title="Doc",
            content="Content",
            canvas_id=test_canvas_id
        )

        add_result = docs_service.add_comment(
            canvas_id=test_canvas_id,
            user_id=test_user_id,
            content="Unresolved comment"
        )
        comment_id = add_result["comment_id"]

        # Resolve comment
        result = docs_service.resolve_comment(
            canvas_id=test_canvas_id,
            comment_id=comment_id,
            user_id=test_user_id
        )

        assert result["success"] is True
        assert result["comment_id"] == comment_id

    def test_resolve_comment_document_not_found(self, docs_service, test_user_id):
        """Test resolving comment on non-existent document."""
        result = docs_service.resolve_comment(
            canvas_id="non-existent",
            comment_id="comment-123",
            user_id=test_user_id
        )

        assert result["success"] is False


class TestGetDocumentVersions:
    """Tests for get_document_versions method."""

    def test_get_document_versions(self, docs_service, test_user_id, test_canvas_id):
        """Test getting version history."""
        # Create document
        docs_service.create_document_canvas(
            user_id=test_user_id,
            title="Versioned Doc",
            content="Original",
            canvas_id=test_canvas_id
        )

        # Update to create versions
        docs_service.update_document_content(
            canvas_id=test_canvas_id,
            user_id=test_user_id,
            content="Version 2",
            changes="First update"
        )

        docs_service.update_document_content(
            canvas_id=test_canvas_id,
            user_id=test_user_id,
            content="Version 3",
            changes="Second update"
        )

        # Get versions
        result = docs_service.get_document_versions(test_canvas_id)

        assert result["success"] is True
        assert result["total"] >= 3  # Initial + 2 updates
        assert len(result["versions"]) >= 3

    def test_get_document_versions_not_found(self, docs_service):
        """Test getting versions for non-existent document."""
        result = docs_service.get_document_versions("non-existent")

        assert result["success"] is False


class TestRestoreVersion:
    """Tests for restore_version method."""

    def test_restore_version(self, docs_service, test_user_id, test_canvas_id):
        """Test restoring a previous version."""
        # Create and update document
        docs_service.create_document_canvas(
            user_id=test_user_id,
            title="Doc",
            content="Original",
            canvas_id=test_canvas_id
        )

        docs_service.update_document_content(
            canvas_id=test_canvas_id,
            user_id=test_user_id,
            content="Modified",
            changes="Change"
        )

        versions_result = docs_service.get_document_versions(test_canvas_id)
        first_version_id = versions_result["versions"][0]["version_id"]

        # Restore first version
        result = docs_service.restore_version(
            canvas_id=test_canvas_id,
            version_id=first_version_id,
            user_id=test_user_id
        )

        assert result["success"] is True
        assert result["content"] == "Original"
        assert "restored_from" in result

    def test_restore_version_not_found(self, docs_service, test_user_id, test_canvas_id):
        """Test restoring non-existent version."""
        docs_service.create_document_canvas(
            user_id=test_user_id,
            title="Doc",
            content="Content",
            canvas_id=test_canvas_id
        )

        result = docs_service.restore_version(
            canvas_id=test_canvas_id,
            version_id="non-existent-version",
            user_id=test_user_id
        )

        assert result["success"] is False


class TestGetTableOfContents:
    """Tests for get_table_of_contents method."""

    def test_get_table_of_contents(self, docs_service, test_user_id, test_canvas_id):
        """Test generating table of contents."""
        content = """
# Main Heading

## Section 1

Content here.

### Subsection 1.1

More content.

## Section 2

Final content.
        """

        docs_service.create_document_canvas(
            user_id=test_user_id,
            title="Structured Doc",
            content=content,
            canvas_id=test_canvas_id
        )

        result = docs_service.get_table_of_contents(test_canvas_id)

        assert result["success"] is True
        assert result["total"] == 3  # #, ##, ##
        assert any(h["title"] == "Main Heading" for h in result["headings"])
        assert any(h["level"] == 1 for h in result["headings"])

    def test_get_table_of_contents_no_headings(self, docs_service, test_user_id, test_canvas_id):
        """Test TOC for document without headings."""
        docs_service.create_document_canvas(
            user_id=test_user_id,
            title="Plain Doc",
            content="Just plain text with no headings.",
            canvas_id=test_canvas_id
        )

        result = docs_service.get_table_of_contents(test_canvas_id)

        assert result["success"] is True
        assert result["total"] == 0

    def test_get_table_of_contents_not_found(self, docs_service):
        """Test TOC for non-existent document."""
        result = docs_service.get_table_of_contents("non-existent")

        assert result["success"] is False


class TestHelperMethods:
    """Tests for helper methods."""

    def test_version_to_dict(self, docs_service):
        """Test _version_to_dict method."""
        version = DocumentVersion(
            version_id="v1",
            content="Content",
            author="user-1",
            created_at=datetime.now(),
            changes="Initial"
        )

        result = docs_service._version_to_dict(version)

        assert result["version_id"] == "v1"
        assert result["content"] == "Content"
        assert result["author"] == "user-1"
        assert "created_at" in result

    def test_comment_to_dict(self, docs_service):
        """Test _comment_to_dict method."""
        comment = DocumentComment(
            comment_id="c1",
            content="Comment",
            author="user-1",
            selection={"start": 0, "end": 5},
            resolved=False
        )

        result = docs_service._comment_to_dict(comment)

        assert result["comment_id"] == "c1"
        assert result["content"] == "Comment"
        assert result["resolved"] is False
