"""Coverage wave 77 — RED tests for core/canvas_docs_service.py.

Real bug (TDD red->green): resolve_comment() returns {"success": True}
and writes a resolution audit row even when the comment_id does not
exist on the document. RED: resolving a nonexistent comment must report
failure and must not append a misleading audit entry.
"""
from unittest.mock import Mock
from datetime import datetime

import pytest

from core.canvas_docs_service import DocumentationCanvasService, DocumentComment, DocumentVersion
from core.models import CanvasAudit


def _make_audit(comments):
    return CanvasAudit(
        id="aud-1",
        canvas_id="doc-1",
        tenant_id="default",
        action_type="create",
        canvas_type="docs",
        user_id="u1",
        details_json={
            "canvas_type": "docs",
            "content": "hi",
            "versions": [],
            "comments": comments,
            "enable_comments": True,
            "enable_versioning": True,
        },
    )


class TestResolveCommentMissing:
    """REAL BUG: resolving a comment that does not exist reports success
    and writes a misleading audit row."""

    def _service(self, audit):
        db = Mock()
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = audit
        return DocumentationCanvasService(db), db

    def test_missing_comment_reports_failure(self):
        audit = _make_audit(comments=[{
            "comment_id": "c-1", "content": "hello", "author": "u1",
            "selection": None, "resolved": False,
            "created_at": "2026-01-01T00:00:00",
        }])
        service, db = self._service(audit)
        result = service.resolve_comment("doc-1", "c-NOPE", "u1")
        assert result["success"] is False  # RED: currently True
        assert "not found" in result["error"].lower()

    def test_missing_comment_writes_no_audit_row(self):
        audit = _make_audit(comments=[])
        service, db = self._service(audit)
        service.resolve_comment("doc-1", "c-NOPE", "u1")
        assert db.add.call_count == 0  # RED: currently 1 bogus audit row
        assert db.commit.call_count == 0


def _doc_service(audits=None, first_audit=None):
    """Build a service whose latest-audit query returns first_audit and
    whose all-audits query returns the audits list."""
    db = Mock()
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = first_audit
    if audits is not None:
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = audits
    return DocumentationCanvasService(db), db


class TestCreateDocumentCanvas:
    def test_create_success(self):
        service, db = _doc_service()
        result = service.create_document_canvas(
            user_id="u1", title="My Doc", content="# Hi", layout="split_view",
            enable_comments=False, enable_versioning=False, agent_id="a1")
        assert result["success"] is True
        assert result["canvas_id"]
        assert result["version_id"]
        assert result["layout"] == "split_view"
        audit = db.add.call_args[0][0]
        assert audit.action_type == "create"
        assert audit.canvas_type == "docs"
        assert audit.tenant_id == "default"
        assert audit.details_json["versions"][0]["changes"] == "Initial version"

    def test_create_with_explicit_canvas_id(self):
        service, db = _doc_service()
        result = service.create_document_canvas(user_id="u1", title="T", content="c", canvas_id="doc-9")
        assert result["canvas_id"] == "doc-9"

    def test_create_error_rolls_back(self):
        db = Mock()
        db.add.side_effect = RuntimeError("boom")
        service = DocumentationCanvasService(db)
        result = service.create_document_canvas(user_id="u1", title="T", content="c")
        assert result["success"] is False
        assert "boom" in result["error"]
        db.rollback.assert_called_once()


class TestUpdateDocumentContent:
    def _audit(self, versions=None, versioning=True, content="old"):
        return CanvasAudit(
            id="aud-1", canvas_id="doc-1", tenant_id="default",
            action_type="create", canvas_type="docs", user_id="u1",
            details_json={
                "canvas_type": "docs", "content": content,
                "versions": versions or [], "enable_versioning": versioning,
                "enable_comments": True,
            },
        )

    def test_update_creates_version(self):
        audit = self._audit()
        service, db = _doc_service(first_audit=audit)
        result = service.update_document_content("doc-1", "u1", "new content", changes="typo fix")
        assert result["success"] is True
        assert result["content"] == "new content"
        assert result["version_id"]
        assert len(audit.details_json["versions"]) == 1
        assert audit.details_json["versions"][0]["changes"] == "typo fix"
        new_audit = db.add.call_args[0][0]
        assert new_audit.action_type == "update_content"

    def test_update_without_version(self):
        audit = self._audit()
        service, db = _doc_service(first_audit=audit)
        result = service.update_document_content("doc-1", "u1", "new", create_version=False)
        assert result["success"] is True
        assert audit.details_json["versions"] == []

    def test_update_versioning_disabled(self):
        audit = self._audit(versioning=False)
        service, db = _doc_service(first_audit=audit)
        result = service.update_document_content("doc-1", "u1", "new")
        assert result["success"] is True
        assert audit.details_json["versions"] == []

    def test_update_document_not_found(self):
        service, db = _doc_service(first_audit=None)
        result = service.update_document_content("doc-1", "u1", "new")
        assert result["success"] is False
        assert "not found" in result["error"]

    def test_update_error_rolls_back(self):
        db = Mock()
        db.query.return_value.filter.return_value.order_by.return_value.first.side_effect = RuntimeError("boom")
        service = DocumentationCanvasService(db)
        result = service.update_document_content("doc-1", "u1", "new")
        assert result["success"] is False
        db.rollback.assert_called_once()


class TestUpdateTransactional:
    def test_transactional_success(self):
        audit = CanvasAudit(
            id="aud-1", canvas_id="doc-1", tenant_id="default",
            action_type="create", canvas_type="docs", user_id="u1",
            details_json={"canvas_type": "docs", "content": "old",
                          "versions": [], "enable_versioning": True,
                          "enable_comments": True},
        )
        service, db = _doc_service(first_audit=audit)
        result = service.update_document_content_transactional("doc-1", "u1", "tx content")
        assert result["success"] is True
        assert result["content"] == "tx content"

    def test_transactional_failure_raises(self):
        service, db = _doc_service(first_audit=None)
        with pytest.raises(ValueError, match="Transactional failure"):
            service.update_document_content_transactional("doc-1", "u1", "x", should_fail=True)

    def test_transactional_inner_error_returns_failure(self):
        # update_document_content swallows DB errors into a failure dict;
        # the transactional wrapper surfaces it without raising.
        db = Mock()
        db.query.return_value.filter.return_value.order_by.return_value.first.side_effect = RuntimeError("inner")
        service = DocumentationCanvasService(db)
        result = service.update_document_content_transactional("doc-1", "u1", "x")
        assert result["success"] is False
        assert "inner" in result["error"]


class TestAddComment:
    def _audit(self, comments=None, enabled=True):
        return CanvasAudit(
            id="aud-1", canvas_id="doc-1", tenant_id="default",
            action_type="create", canvas_type="docs", user_id="u1",
            details_json={"canvas_type": "docs", "content": "c",
                          "versions": [], "enable_comments": enabled,
                          "comments": comments or []},
        )

    def test_add_comment_success(self):
        audit = self._audit()
        service, db = _doc_service(first_audit=audit)
        result = service.add_comment("doc-1", "u1", "nice doc", selection={"start": 0, "end": 4, "text": "nice"})
        assert result["success"] is True
        assert result["comment_id"]
        assert result["selection"] == {"start": 0, "end": 4, "text": "nice"}
        assert audit.details_json["comments"][0]["author"] == "u1"
        new_audit = db.add.call_args[0][0]
        assert new_audit.action_type == "add_comment"

    def test_add_comment_not_found(self):
        service, db = _doc_service(first_audit=None)
        result = service.add_comment("doc-1", "u1", "hi")
        assert result["success"] is False

    def test_add_comment_disabled(self):
        audit = self._audit(enabled=False)
        service, db = _doc_service(first_audit=audit)
        result = service.add_comment("doc-1", "u1", "hi")
        assert result["success"] is False
        assert "not enabled" in result["error"]

    def test_add_comment_error_rolls_back(self):
        db = Mock()
        db.query.return_value.filter.return_value.order_by.return_value.first.side_effect = RuntimeError("boom")
        service = DocumentationCanvasService(db)
        result = service.add_comment("doc-1", "u1", "hi")
        assert result["success"] is False
        db.rollback.assert_called_once()


class TestResolveComment:
    def _audit(self, comments=None):
        return CanvasAudit(
            id="aud-1", canvas_id="doc-1", tenant_id="default",
            action_type="create", canvas_type="docs", user_id="u1",
            details_json={"canvas_type": "docs", "content": "c",
                          "versions": [], "enable_comments": True,
                          "comments": comments or []},
        )

    def test_resolve_existing_comment(self):
        comments = [{"comment_id": "c-1", "content": "hi", "author": "u1",
                     "selection": None, "resolved": False,
                     "created_at": "2026-01-01T00:00:00"}]
        audit = self._audit(comments)
        service, db = _doc_service(first_audit=audit)
        result = service.resolve_comment("doc-1", "c-1", "u1")
        assert result["success"] is True
        assert comments[0]["resolved"] is True
        assert comments[0]["resolved_by"] == "u1"
        assert "resolved_at" in comments[0]
        new_audit = db.add.call_args[0][0]
        assert new_audit.action_type == "resolve_comment"

    def test_resolve_document_not_found(self):
        service, db = _doc_service(first_audit=None)
        result = service.resolve_comment("doc-1", "c-1", "u1")
        assert result["success"] is False

    def test_resolve_error_rolls_back(self):
        db = Mock()
        db.query.return_value.filter.return_value.order_by.return_value.first.side_effect = RuntimeError("boom")
        service = DocumentationCanvasService(db)
        result = service.resolve_comment("doc-1", "c-1", "u1")
        assert result["success"] is False
        db.rollback.assert_called_once()


class TestGetDocumentVersions:
    def test_versions_aggregated_from_latest_audit(self):
        audits = [
            CanvasAudit(id="a1", canvas_id="doc-1", tenant_id="default",
                        action_type="create", canvas_type="docs", user_id="u1",
                        details_json={"canvas_type": "docs", "content": "v1",
                                      "versions": [{"version_id": "v-1", "content": "v1"}]}),
            CanvasAudit(id="a2", canvas_id="doc-1", tenant_id="default",
                        action_type="update_content", canvas_type="docs", user_id="u1",
                        details_json={"canvas_type": "docs", "content": "v2",
                                      "versions": [
                                          {"version_id": "v-1", "content": "v1"},
                                          {"version_id": "v-2", "content": "v2"},
                                      ]}),
        ]
        service, db = _doc_service(audits=audits)
        result = service.get_document_versions("doc-1")
        assert result["success"] is True
        assert result["total"] == 2
        assert result["versions"][-1]["version_id"] == "v-2"

    def test_versions_not_found(self):
        service, db = _doc_service(audits=[])
        result = service.get_document_versions("doc-1")
        assert result["success"] is False

    def test_versions_error(self):
        db = Mock()
        db.query.return_value.filter.return_value.order_by.return_value.all.side_effect = RuntimeError("boom")
        service = DocumentationCanvasService(db)
        result = service.get_document_versions("doc-1")
        assert result["success"] is False


class TestRestoreVersion:
    def _audit(self, versions=None):
        return CanvasAudit(
            id="aud-1", canvas_id="doc-1", tenant_id="default",
            action_type="create", canvas_type="docs", user_id="u1",
            details_json={"canvas_type": "docs", "content": "current",
                          "versions": versions or []},
        )

    def test_restore_success(self):
        versions = [{"version_id": "v-1", "content": "original", "author": "u1"}]
        audit = self._audit(versions)
        service, db = _doc_service(first_audit=audit)
        result = service.restore_version("doc-1", "v-1", "u1")
        assert result["success"] is True
        assert result["content"] == "original"
        assert result["restored_from"] == "v-1"
        assert result["new_version_id"]
        assert len(versions) == 2
        assert versions[-1]["changes"] == "Restored from version v-1"
        new_audit = db.add.call_args[0][0]
        assert new_audit.action_type == "restore_version"

    def test_restore_version_not_found(self):
        audit = self._audit([{"version_id": "v-1", "content": "x", "author": "u1"}])
        service, db = _doc_service(first_audit=audit)
        result = service.restore_version("doc-1", "v-99", "u1")
        assert result["success"] is False
        assert "not found" in result["error"]
        assert db.add.call_count == 0

    def test_restore_document_not_found(self):
        service, db = _doc_service(first_audit=None)
        result = service.restore_version("doc-1", "v-1", "u1")
        assert result["success"] is False

    def test_restore_error_rolls_back(self):
        db = Mock()
        db.query.return_value.filter.return_value.order_by.return_value.first.side_effect = RuntimeError("boom")
        service = DocumentationCanvasService(db)
        result = service.restore_version("doc-1", "v-1", "u1")
        assert result["success"] is False
        db.rollback.assert_called_once()


class TestTableOfContents:
    def _audit(self, content=""):
        return CanvasAudit(
            id="aud-1", canvas_id="doc-1", tenant_id="default",
            action_type="create", canvas_type="docs", user_id="u1",
            details_json={"canvas_type": "docs", "content": content,
                          "versions": []},
        )

    def test_headings_parsed_with_anchors(self):
        content = "# Title One\nsome text\n## Sub/Title\n### Deep dive\n"
        service, db = _doc_service(first_audit=self._audit(content))
        result = service.get_table_of_contents("doc-1")
        assert result["success"] is True
        assert result["total"] == 3
        levels = [h["level"] for h in result["headings"]]
        assert levels == [1, 2, 3]
        anchors = [h["anchor"] for h in result["headings"]]
        assert anchors == ["title-one", "sub-title", "deep-dive"]
        assert result["headings"][0]["position"] == content.index("# Title")

    def test_no_headings(self):
        service, db = _doc_service(first_audit=self._audit("plain text, no headings"))
        result = service.get_table_of_contents("doc-1")
        assert result["success"] is True
        assert result["total"] == 0

    def test_toc_not_found(self):
        service, db = _doc_service(first_audit=None)
        result = service.get_table_of_contents("doc-1")
        assert result["success"] is False

    def test_toc_error(self):
        db = Mock()
        db.query.return_value.filter.return_value.order_by.return_value.first.side_effect = RuntimeError("boom")
        service = DocumentationCanvasService(db)
        result = service.get_table_of_contents("doc-1")
        assert result["success"] is False


class TestSerializeHelpers:
    def test_version_to_dict(self):
        service, _ = _doc_service()
        v = DocumentVersion(version_id="v-1", content="c", author="u1",
                            created_at=datetime(2026, 1, 1), changes="init")
        d = service._version_to_dict(v)
        assert d == {"version_id": "v-1", "content": "c", "author": "u1",
                     "created_at": "2026-01-01T00:00:00", "changes": "init"}

    def test_comment_to_dict(self):
        service, _ = _doc_service()
        c = DocumentComment(comment_id="c-1", content="hi", author="u1",
                            selection={"start": 0}, resolved=True)
        d = service._comment_to_dict(c)
        assert d["comment_id"] == "c-1"
        assert d["resolved"] is True
        assert d["selection"] == {"start": 0}
        assert d["created_at"]

    def test_comment_default_created_at(self):
        service, _ = _doc_service()
        c = DocumentComment(comment_id="c-2", content="hi", author="u1")
        assert c.created_at is not None
