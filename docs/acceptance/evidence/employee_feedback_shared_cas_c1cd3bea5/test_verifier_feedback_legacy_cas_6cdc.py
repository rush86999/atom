import pytest
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from tests.test_employee_business_feedback import feedback_db, fresh_router, _insert_outcome_row, _synthetic_result, _row_by_id

@pytest.mark.parametrize("legacy_verdict", ["grounding_ok", "unsupported_figures"])
def test_pending_business_annotation_cannot_erase_legacy_grounding_verdict(feedback_db, fresh_router, monkeypatch, legacy_verdict):
    from sqlalchemy.orm import Query
    from core.learning_llm_router import LearningBasedRouter, RoutingFeedback
    from core.employee_routing_feedback import record_pending_business_evaluation
    generation='legacy-grounding-interleave'
    row_id=_insert_outcome_row(feedback_db,generation)
    if legacy_verdict == 'unsupported_figures':
        from core.models import LLMRoutingFeedback
        with feedback_db['Session']() as db:
            row=db.query(LLMRoutingFeedback).filter_by(id=row_id).one()
            row.quality_satisfied=False;row.user_satisfaction=.1;db.commit()
    read=threading.Event();release=threading.Event();original=Query.all
    def paused_all(query):
        rows=original(query)
        if threading.current_thread().name.startswith('weak') and any(getattr(r,'routing_result_id',None)==generation for r in rows):
            read.set();assert release.wait(20)
        return rows
    monkeypatch.setattr(Query,'all',paused_all)
    def weak():
        return asyncio.run(record_pending_business_evaluation(_synthetic_result(generation),stage='employee_evidence_selection',workspace_id='ws-ctrl',tenant_id='tenant-ctrl'))
    with ThreadPoolExecutor(max_workers=1,thread_name_prefix='weak') as pool:
        pending=pool.submit(weak);assert read.wait(20)
        try:
            writer=LearningBasedRouter.__new__(LearningBasedRouter)
            strong=writer._persist_feedback(RoutingFeedback(routing_result_id=generation,tenant_id='tenant-ctrl',model_id='llama3.1:8b',task_type='general',success=True,quality_satisfied=legacy_verdict!='unsupported_figures',cost_within_budget=True,user_satisfaction=.1 if legacy_verdict=='unsupported_figures' else .9),{'verdict':legacy_verdict})
            assert strong=='annotated'
        finally:release.set()
        result=pending.result(timeout=20)
    row=_row_by_id(feedback_db,row_id)
    assert row.prompt_features.get('verdict')==legacy_verdict,(result,row.prompt_features)

def test_stale_legacy_grounding_cannot_overwrite_committed_business_failure(feedback_db, fresh_router, monkeypatch):
    from sqlalchemy.orm import Query
    from core.learning_llm_router import LearningBasedRouter, RoutingFeedback
    from core.employee_routing_feedback import record_attempt_evaluation
    generation='stale-legacy-interleave'
    row_id=_insert_outcome_row(feedback_db,generation)
    read=threading.Event();release=threading.Event();original=Query.all
    def paused_all(query):
        rows=original(query)
        if threading.current_thread().name.startswith('weak') and any(getattr(r,'routing_result_id',None)==generation for r in rows):
            read.set();assert release.wait(20)
        return rows
    monkeypatch.setattr(Query,'all',paused_all)
    def weak():
        writer=LearningBasedRouter.__new__(LearningBasedRouter)
        return writer._persist_feedback(RoutingFeedback(routing_result_id=generation,tenant_id='tenant-ctrl',model_id='llama3.1:8b',task_type='general',success=True,quality_satisfied=True,cost_within_budget=True,user_satisfaction=.9),{'verdict':'grounding_ok'})
    with ThreadPoolExecutor(max_workers=1,thread_name_prefix='weak') as pool:
        pending=pool.submit(weak);assert read.wait(20)
        try:
            strong=asyncio.run(record_attempt_evaluation(_synthetic_result(generation),stage='employee_evidence_selection',evaluation='failed',failure_kind='wrong_evidence_selection',workspace_id='ws-ctrl',tenant_id='tenant-ctrl'))
            assert strong['status']=='annotated'
        finally:release.set()
        result=pending.result(timeout=20)
    row=_row_by_id(feedback_db,row_id)
    assert row.prompt_features.get('verdict')=='wrong_evidence_selection',(result,row.prompt_features)
    assert row.prompt_features.get('evaluation_revision',0)>=1
