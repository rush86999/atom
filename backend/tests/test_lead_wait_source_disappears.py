"""Accepted source disappearance/read failure cannot leave stale dependent work ready."""
import os
import pytest
from tests.test_assignment_routes import route_env
from tests.test_task_wait_two_fact_events import _fixtures, _install_transport, _questions, _reconciliations, _applied_artifacts, _start


@pytest.mark.parametrize('failure', ['removed', 'unreadable'])
def test_accepted_invoice_unavailable_before_consumption_stays_unresolved(route_env, tmp_path, monkeypatch, failure):
    monkeypatch.setenv('ATOM_ASSIGNMENT_OUTPUT_DIR', str(tmp_path/'artifacts'))
    po, invoice, receiving = _fixtures(tmp_path)
    _install_transport(monkeypatch)
    client, lifecycle = route_env['client'], route_env['lifecycle']
    run = _start(client, po)
    accepted = client.post(f'/api/assignments/{run}/sources', json={'source':{'path':str(invoice)}, 'reason':'authorized invoice'})
    assert accepted.status_code == 200, accepted.text
    assert _questions(lifecycle, run)[0]['inputs']['missing'] == ['receiving']
    if failure == 'removed':
        invoice.unlink()
    else:
        import core.assignment_executor as executor
        real_hash = executor._sha256_file
        def denied_hash(path):
            if os.fspath(path) == os.fspath(invoice):
                raise PermissionError('controlled source became unreadable')
            return real_hash(path)
        monkeypatch.setattr(executor, '_sha256_file', denied_hash)
    answer = client.post(f'/api/assignments/{run}/sources', json={'source':{'path':str(receiving)}, 'reason':'authorized receiving'})
    final = lifecycle.get_assignment(run)
    assert final['status'] != 'completed', (failure, answer.status_code, final['status'])
    assert not _reconciliations(final), 'unavailable accepted source certified a cached reconciliation'
    assert not _applied_artifacts(final), 'unavailable accepted source published a final artifact'


def test_removed_authoritative_upload_cannot_use_cached_invoice(route_env, tmp_path, monkeypatch):
    import hashlib
    from core.models import IngestedDocument
    monkeypatch.setenv('ATOM_ASSIGNMENT_OUTPUT_DIR', str(tmp_path/'artifacts'))
    po, invoice, receiving = _fixtures(tmp_path)
    _install_transport(monkeypatch)
    doc = IngestedDocument(id='lead-invoice-upload', workspace_id='ws-1', tenant_id='tenant-1', file_name=invoice.name, file_path=str(invoice), file_type='json', integration_id='upload', external_id='lead-upload', source_content_hash=hashlib.sha256(invoice.read_bytes()).hexdigest(), freshness_status='fresh')
    route_env['db'].add(doc)
    route_env['db'].commit()
    client, lifecycle = route_env['client'], route_env['lifecycle']
    run = _start(client, po)
    accepted = client.post(f'/api/assignments/{run}/sources', json={'source':{'document_id':doc.id, 'source_version':doc.source_content_hash}, 'reason':'authorized uploaded invoice'})
    assert accepted.status_code == 200, accepted.text
    assert _questions(lifecycle, run)[0]['inputs']['missing'] == ['receiving']
    route_env['db'].delete(doc)
    route_env['db'].commit()
    answer = client.post(f'/api/assignments/{run}/sources', json={'source':{'path':str(receiving)}, 'reason':'authorized receiving'})
    final = lifecycle.get_assignment(run)
    assert final['status'] != 'completed', (answer.status_code, final['status'])
    assert not _reconciliations(final), 'removed upload authority certified a cached invoice'
    assert not _applied_artifacts(final)
