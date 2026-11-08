"""Root scoped identity probe using the real workspace handler factory."""
import json
import uuid
import api.document_routes as routes
import core.lancedb_handler as storage
from core.auto_document_ingestion import DocumentParser
from core.models import IngestedDocument, User
from tests.test_document_export import exported
from tests.test_root_document_parse_honesty import _docx_bytes


def test_identical_docx_in_two_real_workspace_stores_preserves_both_sources(
        exported, monkeypatch, tmp_path):
    monkeypatch.setattr(DocumentParser, '_docling_processor', False)
    monkeypatch.setenv('LANCEDB_URI_BASE', str(tmp_path/'scoped-stores'))
    monkeypatch.setenv('ATOM_OFFICE_DIR', str(tmp_path/'office'))
    monkeypatch.setattr(storage, '_workspace_handlers', {})
    monkeypatch.setattr(routes, 'get_lancedb_handler', storage.get_lancedb_handler)
    a = exported.user
    b = User(id='doc-peer-'+uuid.uuid4().hex,
             email='doc-peer-'+uuid.uuid4().hex+'@example.invalid',
             first_name='Peer', last_name='Team', role='member', status='active',
             is_active=True, tenant_id=a.tenant_id,
             workspace_id='doc-peer-workspace-'+uuid.uuid4().hex)
    exported.session.add(b)
    exported.session.commit()
    content = 'Same actual DOCX content '+uuid.uuid4().hex
    payload = _docx_bytes(content)
    def upload(name):
        return exported.client.post('/api/documents/upload', files={
            'file': (name, payload,
                     'application/vnd.openxmlformats-officedocument.wordprocessingml.document')})
    first = upload('team-a.docx')
    assert first.status_code == 200, first.text
    a_id = first.json()['id']
    exported.session.expire_all()
    a_row = exported.session.get(IngestedDocument, a_id)
    before = (a_row.id, a_row.workspace_id, a_row.tenant_id,
              a_row.file_name, a_row.file_path, a_row.source_content_hash)
    a_export = exported.client.get(f'/api/documents/{a_id}/export?format=text')
    assert a_export.status_code == 200, a_export.text
    exported.client.app.dependency_overrides[routes.get_current_user] = lambda: b
    second = upload('team-b.docx')
    assert second.status_code == 200, second.text
    b_id = second.json()['id']
    b_export = exported.client.get(f'/api/documents/{b_id}/export?format=text')
    exported.session.expire_all()
    current_a = exported.session.get(IngestedDocument, a_id)
    after = (current_a.id, current_a.workspace_id, current_a.tenant_id,
             current_a.file_name, current_a.file_path, current_a.source_content_hash)
    capture = {'a_id':a_id, 'b_id':b_id, 'b_upload':second.status_code,
               'b_export':b_export.status_code,
               'peer_record_unchanged':before==after,
               'distinct_physical_handlers':
                   storage.get_lancedb_handler(a.workspace_id).db_path !=
                   storage.get_lancedb_handler(b.workspace_id).db_path}
    print('ROOT_DOCUMENT_SCOPE_CAPTURE '+json.dumps(capture, sort_keys=True))
    assert b_export.status_code == 200, capture
    assert a_id != b_id, capture
    assert before == after, capture
    assert content in b_export.text
    assert b_export.headers['X-Document-Provenance'] == 'authoritative'
    assert exported.client.get(f'/api/documents/{a_id}').status_code == 404
    exported.client.app.dependency_overrides[routes.get_current_user] = lambda: a
    assert exported.client.get(f'/api/documents/{a_id}/export?format=text').status_code == 200
    assert exported.client.get(f'/api/documents/{b_id}').status_code == 404
