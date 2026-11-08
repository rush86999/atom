"""Root public document parse probes: real local DOCX parser and durable stores.

Only embeddings and the optional Docling selection are controlled. No model
or remote parser is called; the normal python-docx fallback, upload, index,
SQL mirror and stored-text export paths execute.
"""
import io
import pytest
from docx import Document
from core.auto_document_ingestion import DocumentParser
from core.models import IngestedDocument
from tests.test_document_export import exported, _read


def _docx_bytes(text=None):
    doc = Document()
    if text is not None:
        doc.add_paragraph(text)
        table = doc.add_table(rows=1, cols=1)
        table.cell(0, 0).text = "Verified table-cell content"
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


def _post(ctx, payload, filename):
    return ctx.client.post('/api/documents/upload', files={
        'file': (filename, payload,
                 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')})


def test_real_docx_upload_open_reload_export_positive(exported, monkeypatch):
    monkeypatch.setattr(DocumentParser, '_docling_processor', False)
    uploaded = _post(exported, _docx_bytes('Verified paragraph content'), 'positive.docx')
    assert uploaded.status_code == 200, uploaded.text
    doc_id = uploaded.json()['id']
    first = _read(exported, doc_id)
    assert 'Verified paragraph content' in first['content']
    assert 'Verified table-cell content' in first['content']
    assert _read(exported, doc_id)['content'] == first['content']
    download = exported.client.get(f'/api/documents/{doc_id}/export?format=text')
    assert download.status_code == 200, download.text
    assert download.text == first['content']
    assert download.headers['X-Document-Provenance'] == 'authoritative'
    assert download.headers['X-Document-Source-Version-Kind'] == 'versioned'


@pytest.mark.parametrize('invalid', ['malformed', 'empty'])
def test_docx_without_extracted_content_does_not_become_fresh_evidence(
        exported, monkeypatch, invalid):
    monkeypatch.setattr(DocumentParser, '_docling_processor', False)
    payload = b'not a DOCX archive' if invalid == 'malformed' else _docx_bytes()
    before = exported.session.query(IngestedDocument).count()
    response = _post(exported, payload, invalid+'.docx')
    capture = {'status': response.status_code, 'body': response.json(),
               'expected': 'typed refusal, not a fresh placeholder document'}
    if response.status_code == 200:
        doc_id = response.json()['id']
        downloaded = exported.client.get(f'/api/documents/{doc_id}/export?format=text')
        capture['export_status'] = downloaded.status_code
        capture['export_provenance'] = downloaded.headers.get('X-Document-Provenance')
        capture['export_text'] = downloaded.text
    assert response.status_code in (415, 422), capture
    exported.session.expire_all()
    assert exported.session.query(IngestedDocument).count() == before
