import pytest
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from tests.test_employee_business_feedback import feedback_db, fresh_router, _insert_outcome_row, _synthetic_result, _row_by_id

@pytest.mark.parametrize("weak_kind", ["positive", "pending"])
def test_stale_positive_cannot_overwrite_committed_semantic_failure(feedback_db, fresh_router, monkeypatch, weak_kind):
    from sqlalchemy.orm import Query
    from core.employee_routing_feedback import record_attempt_evaluation, record_pending_business_evaluation
    generation = 'verifier-interleaving'
    row_id = _insert_outcome_row(feedback_db, generation)
    result = _synthetic_result(generation)
    read = threading.Event()
    release = threading.Event()
    original = Query.all
    def paused_all(query):
        rows = original(query)
        if threading.current_thread().name.startswith('weak') and rows and any(getattr(r, 'routing_result_id', None) == generation for r in rows):
            read.set()
            assert release.wait(20)
        return rows
    monkeypatch.setattr(Query, 'all', paused_all)
    def evaluate(positive):
        if positive and weak_kind == 'pending':
            return asyncio.run(record_pending_business_evaluation(result, stage='employee_evidence_selection', workspace_id='ws-ctrl', tenant_id='tenant-ctrl'))
        return asyncio.run(record_attempt_evaluation(result, stage='employee_evidence_selection', evaluation='satisfied' if positive else 'failed', failure_kind=None if positive else 'wrong_evidence_selection', workspace_id='ws-ctrl', tenant_id='tenant-ctrl'))
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix='weak') as pool:
        pending = pool.submit(evaluate, True)
        assert read.wait(20)
        try:
            strong = evaluate(False)
            assert strong['status'] == 'annotated', strong
        finally:
            release.set()
        weak = pending.result(timeout=20)
    row = _row_by_id(feedback_db, row_id)
    assert row.success is False, (weak, strong, row.prompt_features)
    assert row.prompt_features.get('business_outcome') == 'failed', (weak, strong, row.prompt_features)
    assert row.prompt_features['verdict'] == 'wrong_evidence_selection', (weak, strong, row.prompt_features)
