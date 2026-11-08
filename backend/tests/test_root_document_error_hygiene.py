"""Root guard for the new identity-probe error path, not global log safety."""
import uuid
import api.document_routes as routes
from core.auto_document_ingestion import DocumentParser
from tests.test_document_export import exported


def test_identity_lookup_error_logs_class_without_private_material(
        exported, monkeypatch, caplog):
    monkeypatch.setattr(DocumentParser, '_docling_processor', False)
    sentinel = 'private lookup material must stay private'
    def unavailable(*args, **kwargs):
        raise ValueError(sentinel)
    monkeypatch.setattr(routes, '_resolve_upload_doc_id', unavailable)
    text = 'Fresh source after identity lookup unavailability '+uuid.uuid4().hex
    result = exported.client.post('/api/documents/upload', files={
        'file': ('fresh.txt', text.encode(), 'text/plain')})
    assert result.status_code == 200, result.text
    assert result.json()['id'] == routes._content_doc_key(
        text, workspace_id=exported.workspace,
        tenant_id=exported.user.tenant_id)
    assert sentinel not in caplog.text
    assert sentinel not in result.text
    assert 'error_class=ValueError' in caplog.text
